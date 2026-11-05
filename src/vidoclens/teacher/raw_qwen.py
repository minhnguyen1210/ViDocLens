"""Qwen single-question raw text inference using the same verified NF4 loader."""

import time

from vidoclens.contracts.local_teacher import LocalGeneration
from vidoclens.teacher.local_qwen import QwenLocalBackend, greedy_generate


class QwenRawBackend(QwenLocalBackend):
    def generate(self, request, image):
        import torch
        from PIL import Image, ImageOps
        from transformers import GenerationConfig

        from vidoclens.teacher.raw_labels import request_text

        if self.model is None:
            self._load()
        torch.manual_seed(self.config.seed)
        with Image.open(image) as source:
            rgb = ImageOps.exif_transpose(source).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": request_text(request)}],
            }
        ]
        prompt = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(text=[prompt], images=[rgb], return_tensors="pt").to("cuda:0")
        inputs.pop("token_type_ids", None)
        tokens = inputs.input_ids.shape[1]
        pixels = int(inputs.image_grid_thw[0].prod()) * self.processor.image_processor.patch_size**2
        if tokens > self.config.max_input_tokens or pixels > self.config.max_image_pixels:
            raise ValueError("raw labeling token/pixel cap exceeded; no truncation")
        decoding = GenerationConfig(
            max_new_tokens=self.config.max_new_tokens,
            do_sample=False,
            num_beams=1,
            eos_token_id=self.model.generation_config.eos_token_id,
            pad_token_id=self.model.generation_config.pad_token_id,
            bos_token_id=self.model.generation_config.bos_token_id,
            use_cache=True,
        )
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        with torch.inference_mode():
            output = greedy_generate(self.model, inputs, decoding)
        torch.cuda.synchronize()
        seconds = time.perf_counter() - started
        ids = output[0, tokens:]
        raw = self.processor.decode(
            ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        eos = decoding.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        truncated = len(ids) >= self.config.max_new_tokens and (
            not len(ids) or ids[-1].item() not in eos
        )
        return LocalGeneration(
            raw_text=raw,
            status="incomplete" if truncated else "completed",
            input_tokens=tokens,
            output_tokens=len(ids),
            generation_seconds=seconds,
            peak_reserved_bytes=torch.cuda.max_memory_reserved(),
        )
