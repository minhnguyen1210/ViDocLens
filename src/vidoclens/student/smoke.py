"""Offline NF4 GPU feasibility runner. Not a serving backend or benchmark."""

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from vidoclens.common.pilot import (
    checked_image,
    environment,
    load_pilot,
    percentile,
    sha256,
    snapshot_sources,
    write_json,
)


def run(args: argparse.Namespace) -> None:
    # Import heavy optional dependencies only in this explicitly invoked ML process.
    import bitsandbytes as bnb
    import psutil
    import torch
    import torchvision
    from PIL import Image, ImageOps
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration

    data = load_pilot(args.root, args.manifest, args.image_inventory)
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot_sources(args.output, Path(__file__))
    write_json(args.output / "environment.json", environment())
    write_json(args.output / "pilot_manifest.json", data.model_dump())
    assert torch.cuda.is_available(), "CUDA unavailable; CPU fallback is forbidden"
    assert torch.__version__ == "2.8.0+cu126", torch.__version__
    assert torchvision.__version__ == "0.23.0+cu126", torchvision.__version__
    assert torch.version.cuda == "12.6", torch.version.cuda
    assert torch.cuda.is_bf16_supported(), "BF16 not supported on this device"
    torch.manual_seed(42)
    torch.set_num_threads(4)
    x = torch.randn(256, 256, device="cuda")
    assert torch.isfinite(x @ x.T).all().item()
    del x
    torch.cuda.synchronize()

    download = json.loads((args.model / "download_manifest.json").read_text(encoding="utf-8"))
    model_hash = sha256(args.model / "model.safetensors")
    if model_hash != "7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0":
        raise ValueError("unexpected Phase 0 student weights")
    start = time.perf_counter()
    processor = AutoProcessor.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=False
    )
    # Qwen3-VL expresses pixel-area bounds through the image processor's size.
    processor.image_processor.size = {"shortest_edge": 4096, "longest_edge": 262144}
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        args.model,
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
    ).eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - start
    quantized = [m for m in model.modules() if isinstance(m, bnb.nn.Linear4bit)]
    assert quantized, "NF4 modules missing"
    assert all(m.weight.device.type == "cuda" for m in quantized)
    assert all(m.weight.quant_state.quant_type == "nf4" for m in quantized)
    assert all(m.weight.quant_state.nested for m in quantized)
    devices = Counter(str(p.device) for p in model.parameters())
    assert all(p.device.type == "cuda" for p in model.parameters()), devices
    profile = {
        "model_revision": args.model.name,
        "model_sha256": model_hash,
        "download_manifest_sha256": sha256(args.model / "download_manifest.json"),
        "source_model_id": download.get("model_id", "Qwen/Qwen3-VL-2B-Instruct"),
        "manifest_sha256": sha256(args.manifest),
        "runner_sha256": sha256(Path(__file__)),
        "cold_load_seconds": load_seconds,
        "quantized_linear_modules": len(quantized),
        "double_quantization_verified": True,
        "parameter_devices": dict(devices),
        "parameter_dtypes": dict(Counter(str(p.dtype) for p in model.parameters())),
        "torch_cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "compute_dtype": "bfloat16",
        "attention": "sdpa",
        "batch_size": 1,
        "max_image_pixels": 262144,
        "min_image_pixels": 4096,
        "max_new_tokens": 128,
        "do_sample": False,
        "seed": 42,
        "load_allocated_bytes": torch.cuda.memory_allocated(),
        "load_reserved_bytes": torch.cuda.memory_reserved(),
        "load_rss_bytes": psutil.Process().memory_info().rss,
        "prompt_policy": "one image and unchanged question_raw only; no system prompt or gold",
        "image_transform": "EXIF transpose then RGB; processor resize; no deskew/enhancement",
        "accuracy_evaluated": False,
    }
    write_json(args.output / "profile.json", profile)

    def generate(row):
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        overall_start = time.perf_counter()
        with Image.open(checked_image(args.root, row)) as original:
            if original.size != (row.width, row.height):
                raise ValueError("manifest dimensions mismatch")
            image = ImageOps.exif_transpose(original).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": row.question_raw},
                ],
            }
        ]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[image], return_tensors="pt").to("cuda:0")
        grid = inputs.image_grid_thw[0].tolist()
        processed_pixels = int(grid[1] * grid[2] * processor.image_processor.patch_size**2)
        assert processed_pixels <= 262144, "pixel cap not respected"
        torch.cuda.synchronize()
        generation_start = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=128, do_sample=False)
        torch.cuda.synchronize()
        generation_seconds = time.perf_counter() - generation_start
        generated = output[0, inputs.input_ids.shape[1] :]
        answer = processor.decode(
            generated, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        result = {
            "qid": row.qid,
            "document_id": row.document_id,
            "status": "ok" if answer.strip() else "empty",
            "answer_raw": answer,
            "output_tokens": len(generated),
            "input_tokens": inputs.input_ids.shape[1],
            "image_grid_thw": grid,
            "image_tokens": int(inputs.image_grid_thw.prod().item() // 4),
            "processed_pixels": processed_pixels,
            "original_dimensions": [row.width, row.height],
            "generation_seconds": generation_seconds,
            "total_seconds": time.perf_counter() - overall_start,
            "hit_output_limit": len(generated) >= 128,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "rss_bytes": psutil.Process().memory_info().rss,
        }
        del inputs, output, generated
        return result

    write_json(args.output / "warmup.json", generate(data.pilot[0]))
    results = []
    for index, row in enumerate(data.pilot):
        try:
            result = generate(row)
        except Exception as error:
            result = {
                "qid": row.qid,
                "status": "error",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        results.append(result)
        write_json(args.output / f"sample_{index:02d}.json", result)
        print(f"student {index + 1}/{len(data.pilot)}: {result['status']}", flush=True)
    ok = [r for r in results if r["status"] == "ok"]
    summary = {
        "status": "pass" if len(ok) == len(results) else "fail",
        "samples": len(results),
        "successful_generations": len(ok),
        "warmup_excluded": True,
        "truncated_samples": sum(r.get("hit_output_limit", False) for r in results),
        "accuracy_evaluated": False,
        "training_tested": False,
    }
    if ok:
        summary.update(
            {
                "generation_p50_seconds": percentile([r["generation_seconds"] for r in ok], 0.5),
                "generation_p95_seconds": percentile([r["generation_seconds"] for r in ok], 0.95),
                "total_p50_seconds": percentile([r["total_seconds"] for r in ok], 0.5),
                "total_p95_seconds": percentile([r["total_seconds"] for r in ok], 0.95),
                "peak_allocated_bytes": max(r["peak_allocated_bytes"] for r in ok),
                "peak_reserved_bytes": max(r["peak_reserved_bytes"] for r in ok),
            }
        )
    write_json(args.output / "student_smoke.json", summary)
    print(json.dumps(summary), flush=True)
    if summary["status"] != "pass":
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "manifest", "image-inventory", "model", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
