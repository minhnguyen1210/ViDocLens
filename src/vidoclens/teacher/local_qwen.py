"""Opt-in Qwen3-VL NF4 adapter. Local files only; GPU validation belongs on the PC."""

import importlib.metadata
import platform
import time
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import LocalGeneration, LocalModelSnapshot
from vidoclens.filtering.io import read_model, revalidate


def snapshot_files(root):
    root = root.resolve(strict=True)
    files = {}
    allowed = {
        ".json",
        ".safetensors",
        ".txt",
        ".model",
        ".tiktoken",
        ".md",
        ".jinja",
        ".vocab",
        ".merges",
    }
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("model snapshot must be a self-contained directory, no symlinks")
        if path.is_file():
            if path.suffix.lower() not in allowed or any(
                p.startswith(".") for p in path.relative_to(root).parts
            ):
                raise ValueError(
                    "unexpected file in model snapshot; use a dedicated model directory"
                )
            files[path.relative_to(root).as_posix()] = sha256(path)
    if "config.json" not in files or not any(p.endswith(".safetensors") for p in files):
        raise ValueError("snapshot needs config.json and safetensors weights")
    return files


def validate_snapshot(root, manifest_path, config):
    if manifest_path.resolve().is_relative_to(root.resolve()):
        raise ValueError("snapshot manifest must live outside the hashed model directory")
    if sha256(manifest_path) != config.snapshot_manifest_sha256:
        raise ValueError("snapshot manifest hash mismatch")
    manifest = read_model(manifest_path, LocalModelSnapshot)
    if (manifest.model_id, manifest.model_revision) != (config.model_id, config.model_revision):
        raise ValueError("snapshot model identity mismatch")
    if snapshot_files(root) != manifest.files:
        raise ValueError("model snapshot content mismatch")


def runtime_environment():
    # Stable identity: no timestamp, PID, changing free VRAM or secrets in cache key.
    import torch

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("local Qwen labels require a CUDA BF16 host; no CPU fallback")
    packages = {
        name: importlib.metadata.version(name)
        for name in ("torch", "transformers", "accelerate", "bitsandbytes", "Pillow", "pydantic")
    }
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "capability": list(torch.cuda.get_device_capability(0)),
    }


def greedy_generate(model, inputs, decoding):
    # Transformers >=4.50 otherwise replaces explicit global-default values (including
    # do_sample=False) with bundled model defaults. kwargs have the highest priority.
    return model.generate(
        **inputs,
        generation_config=decoding,
        use_model_defaults=False,
        do_sample=False,
        num_beams=1,
    )


class QwenLocalBackend:
    fixture_only = False

    def __init__(self, model_path: Path, config):
        self.path, self.config = model_path, revalidate(config)
        self.model = self.processor = None

    def _load(self):
        import bitsandbytes as bnb
        import torch
        from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration

        runtime_environment()
        torch.set_num_threads(4)
        processor = AutoProcessor.from_pretrained(
            self.path, local_files_only=True, trust_remote_code=False
        )
        processor.image_processor.size = {
            "shortest_edge": self.config.min_image_pixels,
            "longest_edge": self.config.max_image_pixels,
        }
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            self.path,
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
            device_map={"": "cuda:0"},
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            ),
        ).eval()
        quantized = [m for m in model.modules() if isinstance(m, bnb.nn.Linear4bit)]
        if not quantized or any(p.device.type != "cuda" for p in model.parameters()):
            raise RuntimeError("expected GPU NF4 model without CPU/disk offload")
        if any(
            m.weight.quant_state.quant_type != "nf4" or not m.weight.quant_state.nested
            for m in quantized
        ):
            raise RuntimeError("NF4 double quantization was not applied")
        self.processor, self.model = processor, model

    def generate(self, request, image):
        import torch
        from PIL import Image, ImageOps
        from transformers import GenerationConfig

        from vidoclens.teacher.local_labels import request_text

        if self.model is None:
            self._load()
        # Fixed per-request seed, independent of cache hits/resume ordering.
        torch.manual_seed(self.config.seed)
        with Image.open(image) as original:
            rgb = ImageOps.exif_transpose(original).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": request_text(request, self.config)},
                ],
            }
        ]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(text=[text], images=[rgb], return_tensors="pt").to("cuda:0")
        inputs.pop("token_type_ids", None)
        tokens = inputs.input_ids.shape[1]
        grid = inputs.image_grid_thw[0].tolist()
        pixels = int(grid[1] * grid[2] * self.processor.image_processor.patch_size**2)
        if tokens > self.config.max_input_tokens or pixels > self.config.max_image_pixels:
            raise ValueError("local request exceeds token/pixel cap; no silent truncation")
        # Reset bundled decoding knobs to explicit greedy generation defaults.
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
        start = time.perf_counter()
        with torch.inference_mode():
            output = greedy_generate(self.model, inputs, decoding)
        torch.cuda.synchronize()
        seconds = time.perf_counter() - start
        generated = output[0, tokens:]
        raw = self.processor.decode(
            generated, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        eos = decoding.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        truncated = len(generated) >= self.config.max_new_tokens and (
            not len(generated) or generated[-1].item() not in eos
        )
        return LocalGeneration(
            raw_text=raw,
            status="incomplete" if truncated else "completed",
            input_tokens=tokens,
            output_tokens=len(generated),
            generation_seconds=seconds,
            peak_reserved_bytes=torch.cuda.max_memory_reserved(),
        )
