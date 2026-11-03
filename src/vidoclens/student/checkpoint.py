"""Hashed local adapter/processor/optimizer/RNG checkpoints at update boundaries."""

import json
import random
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.student.data import safe_path


def rng_state():
    import numpy as np
    import torch

    n = np.random.get_state()
    return {
        "python": random.getstate(),
        "torch": torch.get_rng_state(),
        "cuda": torch.cuda.get_rng_state_all(),
        "numpy": (n[0], n[1].tolist(), n[2], n[3], n[4]),
    }


def restore_rng(state):
    import numpy as np
    import torch

    random.setstate(state["python"])
    torch.set_rng_state(state["torch"])
    torch.cuda.set_rng_state_all(state["cuda"])
    n = state["numpy"]
    np.random.set_state((n[0], np.asarray(n[1], dtype="uint32"), n[2], n[3], n[4]))


def save_checkpoint(path, model, processor, optimizer, scheduler, metadata):
    import torch

    temporary = path.with_name(path.name + ".partial")
    temporary.mkdir(parents=True, exist_ok=False)
    state = rng_state()
    model.save_pretrained(temporary / "adapter", safe_serialization=True)
    processor.save_pretrained(temporary / "processor")
    torch.save(
        {"optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(), "rng": state},
        temporary / "training_state.pt",
    )
    files = {
        p.relative_to(temporary).as_posix(): sha256(p)
        for p in sorted(temporary.rglob("*"))
        if p.is_file()
    }
    write_json(
        temporary / "checkpoint.json",
        metadata | {"files": files, "complete": True, "accumulation_pending": 0},
    )
    temporary.rename(path)
    restore_rng(state)


def validate_checkpoint(path: Path, plan_path: Path):
    meta = json.loads((path / "checkpoint.json").read_text(encoding="utf-8"))
    if (
        not meta["complete"]
        or meta["accumulation_pending"] != 0
        or meta["plan_sha256"] != sha256(plan_path / "manifest.json")
    ):
        raise ValueError("checkpoint incomplete or belongs to another plan")
    required = {
        "training_state.pt",
        "adapter/adapter_model.safetensors",
        "adapter/adapter_config.json",
    }
    if not required <= meta["files"].keys():
        raise ValueError("checkpoint missing resume files")
    for name, checksum in meta["files"].items():
        if sha256(safe_path(path, name)) != checksum:
            raise ValueError("checkpoint hash mismatch")
    return meta
