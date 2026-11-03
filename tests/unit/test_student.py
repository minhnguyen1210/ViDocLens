import json

import pytest
from pydantic import ValidationError

from vidoclens.contracts.student import StudentConfig
from vidoclens.student.checkpoint import validate_checkpoint
from vidoclens.student.collator import answer_labels, causal_targets
from vidoclens.student.data import epoch_order, safe_path


def test_answer_mask_preserves_digits_and_masks_expanded_image_prefix():
    prefix = [10, 99, 99, 99, 11, 20]
    full = prefix + [3, 1, 4, 16, 2]
    labels = answer_labels(full, prefix, 16, {10, 11, 20, 99}, 20)
    assert labels == [-100] * 6 + [3, 1, 4, 16, -100]
    assert causal_targets(labels) == ([5, 6, 7, 8], [3, 1, 4, 16])


@pytest.mark.parametrize(
    "full,prefix,cap",
    [
        ([1, 3, 4], [1, 2], 10),  # prefix changed at BPE boundary
        ([1, 2, 3, 16], [1, 2], 3),  # truncation is forbidden
        ([1, 2, 3], [1, 2], 10),  # no EOS
        ([1, 2, 16], [1, 2], 10),  # empty supervision
        ([1, 2, 99, 16], [1, 2], 10),  # image token in answer
    ],
)
def test_mask_rejects_invalid_template_or_target(full, prefix, cap):
    with pytest.raises(ValueError):
        answer_labels(full, prefix, 16, {99}, cap)


def test_causal_target_rejects_position_zero():
    with pytest.raises(ValueError):
        causal_targets([12, -100])


def test_supervised_logit_selection_matches_full_masked_ce_and_gradient():
    torch = pytest.importorskip("torch")
    import torch.nn.functional as F

    logits = torch.randn(1, 9, 32, requires_grad=True)
    labels = [-100] * 5 + [2, 12, 16, -100]
    expected = F.cross_entropy(logits[:, :-1].reshape(-1, 32), torch.tensor(labels[1:]))
    gradient = torch.autograd.grad(expected, logits, retain_graph=True)[0]
    positions, targets = causal_targets(labels)
    actual = F.cross_entropy(logits[0, positions], torch.tensor(targets))
    torch.testing.assert_close(actual, expected)
    torch.testing.assert_close(torch.autograd.grad(actual, logits)[0], gradient)


def test_order_has_full_coverage_and_is_seeded_without_global_rng():
    assert sorted(epoch_order(101, 17, 0)) == list(range(101))
    assert epoch_order(101, 17, 0) == epoch_order(101, 17, 0)
    assert epoch_order(101, 17, 0) != epoch_order(101, 42, 0)
    assert epoch_order(101, 17, 0) != epoch_order(101, 17, 1)


def test_profile_forbids_seed_drift_and_invalid_pixels():
    with pytest.raises(ValidationError):
        StudentConfig(seeds=(42,))
    with pytest.raises(ValidationError):
        StudentConfig(min_image_pixels=500000, max_image_pixels=262144)
    with pytest.raises(ValidationError):
        StudentConfig(api_key="fake-fixture")


def test_v2_requires_deterministic_math_attention_without_reinterpreting_v1():
    legacy = StudentConfig()
    assert legacy.attention_backend == "auto"
    assert not legacy.deterministic_algorithms
    for overrides in ({}, {"attention_backend": "math"}, {"deterministic_algorithms": True}):
        with pytest.raises(ValidationError, match="deterministic math"):
            StudentConfig(protocol="phase3_gold_v2", **overrides)
    config = StudentConfig(
        protocol="phase3_gold_v2", attention_backend="math", deterministic_algorithms=True
    )
    assert config.model_validate_json(config.model_dump_json()) == config


def test_checkpoint_rejects_incomplete_and_cross_plan(tmp_path):
    from vidoclens.common.pilot import sha256

    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "manifest.json").write_text("{}")
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    for complete, checksum in [(False, sha256(plan / "manifest.json")), (True, "0" * 64)]:
        (checkpoint / "checkpoint.json").write_text(
            json.dumps({"complete": complete, "accumulation_pending": 0, "plan_sha256": checksum})
        )
        with pytest.raises(ValueError):
            validate_checkpoint(checkpoint, plan)
    with pytest.raises(ValueError):
        safe_path(tmp_path, "../outside")


def test_rng_checkpoint_roundtrip():
    torch = pytest.importorskip("torch")
    import random

    from vidoclens.student.checkpoint import restore_rng, rng_state

    # CPU-only runners have no CUDA RNG states, which is valid for this unit fixture.
    saved = rng_state()
    expected = (random.random(), torch.rand(3))
    restore_rng(saved)
    actual = (random.random(), torch.rand(3))
    assert actual[0] == expected[0]
    torch.testing.assert_close(actual[1], expected[1], rtol=0, atol=0)


def test_progress_updates_atomically_but_completed_report_is_immutable(tmp_path):
    from vidoclens.student.progress import write_progress

    path = tmp_path / "run.json"
    write_progress(path, {"complete": False, "step": 0})
    write_progress(path, {"complete": False, "step": 1})
    write_progress(path, {"complete": True, "step": 2})
    assert json.loads(path.read_text())["step"] == 2
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(ValueError, match="immutable"):
        write_progress(path, {"complete": False, "step": 3})


@pytest.mark.parametrize(
    "text,expected",
    [
        ("125.000", True),
        ("12/03/2026", True),
        ("1,5", True),
        ("125.000đ", False),
        ("ABC12", False),
        ("---", False),
    ],
)
def test_numeric_slice_is_predeclared_and_does_not_normalize_digits(text, expected):
    from vidoclens.eval.student import numeric_reference

    assert numeric_reference(text) is expected


def test_checkpoint_selection_uses_all_declared_tiebreaks():
    from vidoclens.eval.student import choose_checkpoint

    def candidate(step, em, numeric, latency):
        return {
            "step": step,
            "metrics": {
                "strict": {"strict_nfc_em": em},
                "numeric_em": numeric,
                "p50_seconds": latency,
            },
        }

    a = candidate(96, 0.5, 0.4, 1.0)
    b = candidate(191, 0.6, 0.3, 2.0)
    assert choose_checkpoint([a, b]) is b
    b["metrics"]["strict"]["strict_nfc_em"] = 0.5
    assert choose_checkpoint([a, b]) is a
    b["metrics"]["numeric_em"] = 0.4
    assert choose_checkpoint([a, b]) is a
    b["metrics"]["p50_seconds"] = 1.0
    assert choose_checkpoint([b, a]) is a


def test_student_inputs_reject_gold_and_training_rejects_dev():
    from vidoclens.contracts.dataset import ReceiptQuestion
    from vidoclens.contracts.student import StudentQuestion, StudentTrainingExample

    digest = "a" * 64
    doc = f"receiptvqa:{digest}:image:1"
    question = ReceiptQuestion(
        archive_sha256=digest,
        source_split="dev",
        source_image_id=1,
        source_question_id=2,
        source_row_index=0,
        filename="1.jpg",
        document_id=doc,
        qid=doc + ":question:2",
        question_raw="Tổng?",
        question_nfc="Tổng?",
    )
    row = StudentQuestion(
        question=question,
        partition="dev_select",
        duplicate_group_id="g",
        image_path="data/example.jpg",
        image_sha256="b" * 64,
    )
    with pytest.raises(ValidationError):
        StudentQuestion.model_validate(row.model_dump() | {"answer_raw": "125.000"})
    with pytest.raises(ValidationError):
        StudentTrainingExample(input=row, answer_raw="125.000")
    with pytest.raises(ValidationError):
        StudentQuestion.model_validate(row.model_dump() | {"partition": "train_fit"})


def test_primary_schedule_covers_all_gold_once_and_partial_final_batch():
    from vidoclens.student.train import sample_schedule

    schedule = sample_schedule([None] * 3053, StudentConfig(), 17, "train")
    assert sorted(schedule) == list(range(3053))
    batches = [schedule[i : i + 16] for i in range(0, len(schedule), 16)]
    assert len(batches) == 191
    assert len(batches[-1]) == 13


def test_checkpoint_rejects_tampered_optimizer_state(tmp_path):
    from vidoclens.common.pilot import sha256

    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "manifest.json").write_text("{}")
    checkpoint = tmp_path / "checkpoint"
    (checkpoint / "adapter").mkdir(parents=True)
    names = [
        "training_state.pt",
        "adapter/adapter_model.safetensors",
        "adapter/adapter_config.json",
    ]
    for name in names:
        (checkpoint / name).write_bytes(b"synthetic-boundary-fixture")
    meta = {
        "complete": True,
        "accumulation_pending": 0,
        "plan_sha256": sha256(plan / "manifest.json"),
        "files": {name: sha256(checkpoint / name) for name in names},
    }
    (checkpoint / "checkpoint.json").write_text(json.dumps(meta))
    validate_checkpoint(checkpoint, plan)
    (checkpoint / "training_state.pt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_checkpoint(checkpoint, plan)
