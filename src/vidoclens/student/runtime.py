"""Offline-only pinned Qwen3-VL NF4 runtime with explicit language-only LoRA."""

import importlib.metadata
import os
import random
import time
from collections import Counter

from vidoclens.common.pilot import sha256


def seed_all(seed):
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_runtime(root, config, *, training=False, adapter=None, processor_path=None, seed=42):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    import bitsandbytes as bnb
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration

    expected = {
        "torch": "2.8.0+cu126",
        "transformers": "4.57.1",
        "peft": "0.17.1",
        "accelerate": "1.10.1",
        "bitsandbytes": "0.48.1",
    }
    versions = {k: importlib.metadata.version(k) for k in expected}
    if versions != expected or not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("pinned CUDA/BF16 environment unavailable; no CPU fallback")
    torch.set_num_threads(4)
    seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(config.deterministic_algorithms)
    torch.backends.cudnn.deterministic = config.deterministic_algorithms
    if config.attention_backend == "math":
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        torch.backends.cuda.enable_cudnn_sdp(False)
        torch.backends.cuda.enable_math_sdp(True)
    model_path = root / "artifacts/models/Qwen3-VL-2B-Instruct" / config.revision
    if sha256(model_path / "model.safetensors") != config.weights_sha256:
        raise ValueError("base weights checksum mismatch")
    processor = AutoProcessor.from_pretrained(
        processor_path or model_path, local_files_only=True, trust_remote_code=False
    )
    processor.image_processor.size = {
        "shortest_edge": config.min_image_pixels,
        "longest_edge": config.max_image_pixels,
    }
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path,
        local_files_only=True,
        trust_remote_code=False,
        device_map={"": "cuda:0"},
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        ),
    )
    modules = [
        name
        for name, module in model.named_modules()
        if name.startswith("model.language_model.layers.")
        and name.rsplit(".", 1)[-1] in {"q_proj", "k_proj", "v_proj", "o_proj"}
        and isinstance(module, bnb.nn.Linear4bit)
    ]
    if len(modules) != model.config.text_config.num_hidden_layers * 4:
        raise ValueError("language attention target enumeration incomplete")
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=training,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    if adapter is not None:
        model = PeftModel.from_pretrained(
            model, adapter, is_trainable=training, local_files_only=True
        )
    elif training:
        model = get_peft_model(
            model,
            LoraConfig(
                r=config.lora_rank,
                lora_alpha=config.lora_alpha,
                lora_dropout=config.lora_dropout,
                target_modules=modules,
                bias="none",
                task_type="CAUSAL_LM",
            ),
        )
    trainable = [name for name, p in model.named_parameters() if p.requires_grad]
    if training and (
        not trainable or any("lora_" not in n or ".language_model." not in n for n in trainable)
    ):
        raise ValueError("unexpected trainable parameter; vision/base must be frozen")
    if any(p.device.type != "cuda" for p in model.parameters()):
        raise ValueError("unexpected CPU offload")
    model.config.use_cache = not training
    model.train(training)
    torch.cuda.synchronize()
    profile = {
        "versions": versions,
        "gpu": torch.cuda.get_device_name(0),
        "cuda": torch.version.cuda,
        "model_id": config.model_id,
        "revision": config.revision,
        "weights_sha256": config.weights_sha256,
        "target_modules": modules,
        "trainable_names": trainable,
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "parameter_dtypes": dict(Counter(str(p.dtype) for p in model.parameters())),
        "quantized_modules": sum(isinstance(m, bnb.nn.Linear4bit) for m in model.modules()),
        "cold_load_seconds": time.perf_counter() - start,
        "load_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "load_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "precision": "NF4 double quant; nonquantized base fp32 via PEFT; bf16 autocast/compute",
        "attention": "sdpa",
        "attention_backend": config.attention_backend,
        "deterministic_algorithms": config.deterministic_algorithms,
        "gradient_checkpointing_use_reentrant": False,
    }
    return model, processor, profile


def loss_step(model, inputs):
    import torch
    import torch.nn.functional as F

    from vidoclens.student.collator import causal_targets

    labels = inputs.pop("labels")[0].tolist()
    positions, targets = causal_targets(labels)
    inputs = inputs.to("cuda")
    with torch.autocast("cuda", dtype=torch.bfloat16):
        output = model(
            **inputs, logits_to_keep=torch.tensor(positions, device="cuda"), use_cache=False
        )
        loss = F.cross_entropy(output.logits[0].float(), torch.tensor(targets, device="cuda"))
    return loss


def generate(model, inputs, processor, max_new_tokens):
    import torch

    inputs = inputs.to("cuda")
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        outputs = model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False, use_cache=True
        )
    ids = outputs[0, inputs.input_ids.shape[1] :].tolist()
    return processor.decode(ids, skip_special_tokens=True, clean_up_tokenization_spaces=False), ids
