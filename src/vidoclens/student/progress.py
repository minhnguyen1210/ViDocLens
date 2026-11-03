"""Atomic mutable progress, separate from immutable completed evidence writers."""

import json
import os
import uuid


def write_progress(path, report):
    if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("complete"):
        raise ValueError("completed run reports are immutable")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
