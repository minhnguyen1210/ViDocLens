"""Explicit, public, revision-pinned teacher download with upstream byte verification."""

import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

MODEL = "Qwen/Qwen3-VL-4B-Instruct"
REVISION = "ebb281ec70b05090aa6165b016eac8ec08e71b17"


def verify(path, entry):
    if not path.is_file() or path.stat().st_size != entry["size"]:
        return False
    algorithm = "sha256" if entry.get("lfs") else "sha1"
    checksum = hashlib.new(algorithm)
    if algorithm == "sha1":
        checksum.update(f"blob {entry['size']}\0".encode())
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            checksum.update(chunk)
    expected = entry["lfs"]["oid"] if entry.get("lfs") else entry["oid"]
    return checksum.hexdigest() == expected


def main():
    root = Path(__file__).resolve().parents[1]
    evidence = root / "artifacts/phase4/teacher_download_v1"
    target = root / "artifacts/models/Qwen3-VL-4B-Instruct" / REVISION
    evidence.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/api/models/{MODEL}/tree/{REVISION}?recursive=true"
    with urllib.request.urlopen(url, timeout=60) as response:
        entries = json.load(response)
    entries = [e for e in entries if e["type"] == "file" and e["path"] != ".gitattributes"]
    if sum(e["size"] for e in entries) > 10_000_000_000 or any(
        Path(e["path"]).name != e["path"]
        or Path(e["path"]).suffix not in {".json", ".txt", ".md", ".safetensors"}
        for e in entries
    ):
        raise ValueError("unexpected model paths or download size")
    (evidence / "upstream_tree.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    # Read the publisher's license declaration before downloading the weights.
    with urllib.request.urlopen(
        f"https://huggingface.co/{MODEL}/resolve/{REVISION}/README.md", timeout=60
    ) as response:
        card = response.read()
    if b"license: apache-2.0" not in card:
        raise ValueError("publisher license declaration changed")
    for entry in entries:
        path = target / entry["path"]
        if verify(path, entry):
            print(json.dumps({"file": path.name, "status": "verified_existing"}), flush=True)
            continue
        if path.exists():
            raise ValueError(f"existing file differs from upstream: {path.name}")
        partial = evidence / (path.name + ".partial")
        for attempt in range(3):
            offset = partial.stat().st_size if partial.exists() else 0
            if offset == entry["size"]:
                break
            request = urllib.request.Request(
                f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{path.name}?download=true",
                headers={"Range": f"bytes={offset}-"} if offset else {},
            )
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    if offset and (
                        response.status != 206
                        or not response.headers.get("Content-Range", "").startswith(
                            f"bytes {offset}-"
                        )
                    ):
                        raise ValueError("server did not honor resume range")
                    last = time.monotonic()
                    with partial.open("ab" if offset else "wb") as stream:
                        while chunk := response.read(8 * 1024 * 1024):
                            stream.write(chunk)
                            if stream.tell() > entry["size"]:
                                raise ValueError("download exceeds upstream size")
                            if time.monotonic() - last >= 20:
                                print(
                                    json.dumps(
                                        {
                                            "file": path.name,
                                            "bytes": stream.tell(),
                                            "total": entry["size"],
                                        }
                                    ),
                                    flush=True,
                                )
                                last = time.monotonic()
                break
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise
        if not verify(partial, entry):
            raise ValueError(f"download checksum mismatch: {path.name}")
        partial.rename(path)
        print(json.dumps({"file": path.name, "status": "verified"}), flush=True)
    manifest = {
        "model_id": MODEL,
        "revision": REVISION,
        "complete": True,
        "verified_utc": datetime.now(UTC).isoformat(),
        "source_url": url,
        "license_evidence": "publisher revision-pinned card declares apache-2.0; no LICENSE file",
        "files": {e["path"]: e for e in entries},
    }
    (evidence / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"complete": True, "bytes": sum(e["size"] for e in entries)}), flush=True)


if __name__ == "__main__":
    main()
