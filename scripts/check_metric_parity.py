"""Execute reviewed, SHA-pinned upstream scorer files offline against a deterministic suite."""

import argparse
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.eval.compatible import PROTOCOL, compatible_scores

EXPECTED = {
    "accuracy.py": "4a8ec38e0cd8cf77cfd429e9bb025dc59693c17d5e40ea9a025b5977fe52a3f2",
    "f1.py": "032d27687af92728c76d0239529782c3c416647690a5b79b4427459f028171cf",
    "anls_metric.py": "9f62584caeeb1452e2589a200c41e20d987d60eb05c589793ba018d6d1db24a2",
    "base_executor.py": "fbaa0f2fccea7a4b03a581a1f0876b8a369ba387af23593aae4c744b72df5ca3",
    "LiGT_VQADataset.py": "bbe02916525f3373e8b30c0c3923708a22c833f8d42c66ef192fb3a9fe855b38",
    "anls-0.0.2-py3-none-any.whl": (
        "f6273fc31188784cd3f6ac083412f70be095ab531847580a88245ee836abe811"
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name, digest in EXPECTED.items():
        if sha256(args.sources / name) != digest:
            raise ValueError("upstream checksum mismatch; do not execute")
    sys.path.insert(0, str(args.sources / "anls-0.0.2-py3-none-any.whl"))
    scorers = []
    for filename, cls in (("accuracy.py", "Accuracy"), ("f1.py", "F1"), ("anls_metric.py", "ANLS")):
        spec = importlib.util.spec_from_file_location("upstream_" + cls, args.sources / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        scorers.append(getattr(module, cls)())
    cases = [
        ("a a", ["a a"]),
        ("125.001", ["125.000"]),
        ("ab", ["ac"]),
        (" A\nB ", ["A\nB"]),
        ("A ¡sep¿ B", ["A\nB"]),
        ("", ["a"]),
        ("ĐỒNG", ["đồng"]),
        ("ß", ["s"]),
        ("a", ["a", "b"]),
        ("e\u0301", ["é"]),
    ]
    rng = random.Random(42)
    alphabet = ["đ", "A", "a", "1", ".", " ", "\n", "ß", "¡sep¿"]
    for _ in range(250):
        pred = "".join(rng.choices(alphabet, k=rng.randint(0, 20)))
        refs = [
            "".join(rng.choices(alphabet, k=rng.randint(1, 20))) + "x"
            for _ in range(rng.randint(1, 3))
        ]
        cases.append((pred, refs))
    # Caller strip is applied exactly as in base_executor; complete qid population supplied.
    gts = {str(i): [r.strip() for r in refs] for i, (_, refs) in enumerate(cases)}
    res = {str(i): [pred.strip()] for i, (pred, _) in enumerate(cases)}
    upstream = [scorer.compute_score(gts, res) for scorer in scorers]
    project = [compatible_scores(pred, refs) for pred, refs in cases]
    for metric, (_, vector) in zip(("accuracy", "set_token_f1", "anls"), upstream, strict=True):
        assert all(
            math.isclose(float(a), b[metric], abs_tol=1e-12)
            for a, b in zip(vector, project, strict=True)
        )
    write_json(
        args.output,
        {
            "status": "pass",
            "protocol": PROTOCOL,
            "cases": len(cases),
            "scorers": ["accuracy", "set_token_f1", "anls"],
            "upstream_files": EXPECTED,
            "raw_newline_preserved": True,
            "parts_not_alternative_references": True,
            "historical_anls_version_known": False,
            "original_benchmark_reproduced": False,
            "source_commit": "5b4376b455ed82e16b2285fca5d8b4b25ee3a3af",
        },
    )
    print(json.dumps({"status": "pass", "cases": len(cases), "protocol": PROTOCOL}))


if __name__ == "__main__":
    main()
