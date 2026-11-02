"""Explicit download of pinned official OCR models; run only with dataset/model authorization."""

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

MODELS = {
    "PP-OCRv5_server_det": "ca867c897ecbca8873081573a802ad70d499cb94",
    "latin_PP-OCRv5_mobile_rec": "ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for model, revision in MODELS.items():
        target = args.output / model / revision
        target.mkdir(parents=True, exist_ok=False)
        api = (
            f"https://huggingface.co/api/models/PaddlePaddle/{model}/tree/{revision}?recursive=true"
        )
        with urllib.request.urlopen(api, timeout=60) as response:
            files = json.load(response)
        records = []
        for item in files:
            name = item["path"]
            if name == ".gitattributes":
                continue
            if name not in {
                "README.md",
                "config.json",
                "inference.json",
                "inference.pdiparams",
                "inference.yml",
            }:
                raise ValueError("unexpected upstream file")
            size = item["size"]
            if size > 300 * 1024**2:
                raise ValueError("model exceeds pilot download size cap")
            url = f"https://huggingface.co/PaddlePaddle/{model}/resolve/{revision}/{name}"
            digest = hashlib.sha256()
            written = 0
            partial = target / (name + ".part")
            with urllib.request.urlopen(url, timeout=120) as response, partial.open("xb") as stream:
                while block := response.read(1024 * 1024):
                    written += len(block)
                    if written > size:
                        raise ValueError("unexpected download size")
                    digest.update(block)
                    stream.write(block)
            assert written == size
            expected = item.get("lfs", {}).get("oid")
            if expected and digest.hexdigest() != expected:
                raise ValueError("upstream LFS hash mismatch")
            partial.rename(target / name)
            records.append(
                {
                    "file": name,
                    "bytes": written,
                    "sha256": digest.hexdigest(),
                    "url": url,
                    "lfs_verified": bool(expected),
                }
            )
        manifest = {
            "model_id": f"PaddlePaddle/{model}",
            "revision": revision,
            "downloaded_utc": datetime.now(UTC).isoformat(),
            "files": records,
        }
        (target / "download_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"{model}: {len(records)} files, {sum(r['bytes'] for r in records)} bytes verified",
            flush=True,
        )


if __name__ == "__main__":
    main()
