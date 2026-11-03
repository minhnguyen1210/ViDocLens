"""Verified assistant-only labels and causal positions; torch is optional at import."""

from collections import OrderedDict

from vidoclens.common.pilot import sha256
from vidoclens.student.data import safe_path


def answer_labels(full_ids, prefix_ids, eos_id, forbidden_ids, max_length):
    """Mask expanded image/user/system tokens; supervise raw answer and its EOS only."""
    n = len(prefix_ids)
    if not n or len(full_ids) > max_length or full_ids[:n] != prefix_ids:
        raise ValueError("truncation, missing prefix or chat-template boundary drift")
    tail = full_ids[n:]
    if eos_id not in tail:
        raise ValueError("assistant EOS missing")
    end = n + tail.index(eos_id)
    if end == n or any(t in forbidden_ids for t in full_ids[n:end]):
        raise ValueError("empty target or special token in gold answer")
    return [-100] * n + full_ids[n : end + 1] + [-100] * (len(full_ids) - end - 1)


def causal_targets(labels):
    positions = [i - 1 for i, value in enumerate(labels) if value != -100]
    if not positions or min(positions) < 0:
        raise ValueError("no valid next-token supervision")
    return positions, [labels[i + 1] for i in positions]


def messages(row, prompt, answer=None):
    result = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": [{"type": "image"}, {"type": "text", "text": row.question.question_raw}],
        },
    ]
    if answer is not None:
        result.append({"role": "assistant", "content": answer})
    return result


class StudentCollator:
    def __init__(self, root, processor, config, prompt):
        self.root, self.processor, self.config, self.prompt = root, processor, config, prompt
        self.images = OrderedDict()
        self.checked = set()
        self.eos_id = processor.tokenizer.convert_tokens_to_ids("<|im_end|>")
        self.forbidden = set(processor.tokenizer.all_special_ids) - {self.eos_id}

    def image(self, row):
        from PIL import Image, ImageOps

        path = safe_path(self.root, row.image_path)
        if row.image_sha256 not in self.checked:
            if sha256(path) != row.image_sha256:
                raise ValueError("student image checksum mismatch")
            self.checked.add(row.image_sha256)
        if row.image_sha256 not in self.images:
            with Image.open(path) as image:
                self.images[row.image_sha256] = ImageOps.exif_transpose(image).convert("RGB")
            if len(self.images) > 16:
                self.images.popitem(last=False)
        return self.images[row.image_sha256]

    def __call__(self, row, answer=None):
        import torch

        p = self.processor
        prefix = p.apply_chat_template(
            messages(row, self.prompt), tokenize=False, add_generation_prompt=True
        )
        # Both passes expand exactly the same image grid. Never estimate prefix token count.
        inputs = p(text=[prefix], images=[self.image(row)], return_tensors="pt")
        prefix_ids = inputs.input_ids[0].tolist()
        if answer is not None:
            full = p.apply_chat_template(
                messages(row, self.prompt, answer), tokenize=False, add_generation_prompt=False
            )
            inputs = p(text=[full], images=[self.image(row)], return_tensors="pt")
            labels = answer_labels(
                inputs.input_ids[0].tolist(),
                prefix_ids,
                self.eos_id,
                self.forbidden,
                self.config.max_sequence_length,
            )
            inputs["labels"] = torch.tensor([labels], dtype=torch.long)
        if inputs.input_ids.shape[1] > self.config.max_sequence_length:
            raise ValueError("sequence exceeds frozen profile; truncation is forbidden")
        pixels = int(inputs.image_grid_thw[0].prod()) * p.image_processor.patch_size**2
        if pixels > self.config.max_image_pixels:
            raise ValueError("processor exceeded image cap")
        return inputs
