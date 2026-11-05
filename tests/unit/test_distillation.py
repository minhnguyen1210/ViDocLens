"""Protect source isolation, matched exposure, compact-ID transport and cohort scope."""

import json

import pytest
from test_local_labels import config
from test_silver import pool, sample
from test_silver_workflow import source  # noqa: F401 -- shared frozen archive fixture

from vidoclens.common.pilot import sha256
from vidoclens.contracts.distillation import DistillationExample
from vidoclens.contracts.local_teacher import LocalGeneration
from vidoclens.contracts.student import StudentQuestion
from vidoclens.distillation.sampler import exposure_counts, schedule, schedule_digest
from vidoclens.filtering.pool import make_pool
from vidoclens.teacher.local_labels import build_plan, parse_generation, request_text


def rows(gold=7, silver=13):
    result = []
    for i in range(gold + silver):
        s = sample(i + 1, image_id=i + 1)
        result.append(
            DistillationExample(
                source="gold" if i < gold else "silver",
                answer_raw="001,50 đ",
                input=StudentQuestion(
                    question=s.question,
                    partition="train_fit",
                    duplicate_group_id=s.duplicate_group_id,
                    image_sha256=s.image_sha256,
                    image_path=f"{i}.jpg",
                ),
            )
        )
    return result


def test_matched_sampler_gold_order_independent_of_silver_size():
    a, b = rows(), rows(silver=3)
    x, y = schedule(a, 17), schedule(b, 17)
    assert len(x) == len(y) == 3056
    assert [a[i].input.question.qid for i in x[::2]] == [b[i].input.question.qid for i in y[::2]]
    counts = exposure_counts(a, x)
    assert sum(counts["gold"].values()) == sum(counts["silver"].values()) == 1528
    for i in range(0, len(x), 16):
        assert [a[j].source for j in x[i : i + 16]].count("gold") == 8


def test_schedule_resume_prefix_and_unseen_membership():
    data = rows(gold=3053, silver=3000)
    order = schedule(data, 42)
    assert schedule(data, 42) == order
    assert schedule(data, 17) != order
    prefix, continuation = order[: 50 * 16], order[50 * 16 : 52 * 16]
    counts = exposure_counts(data, prefix + continuation)
    assert sum(counts["gold"].values()) == sum(counts["silver"].values()) == 416
    assert len(counts["silver"]) == 3000 and sum(v == 0 for v in counts["silver"].values()) == 2584
    shuffled = list(reversed(data))
    assert schedule_digest(data, order) == schedule_digest(shuffled, schedule(shuffled, 42))
    with pytest.raises(ValueError):
        schedule(rows(silver=0), 42)
    with pytest.raises(ValueError):
        schedule(data, 42, accumulation=13)


def test_compact_transport_preserves_canonical_identity_and_raw_answer():
    plan = build_plan(pool(), config(qid_format="request_local_v1"))
    request = plan.requests[0]
    assert request.questions[0].qid not in request_text(request, plan.config)
    raw = {
        "answers": [
            {
                "qid": "q0",
                "answer": " 001,50 đ\n",
                "evidence_text": "001,50 đ",
                "answerable": True,
                "reason_code": "visible_text",
            }
        ]
    }
    labels = parse_generation(
        request, LocalGeneration(raw_text=json.dumps(raw), status="completed")
    )
    assert labels[0].qid == request.questions[0].qid
    assert labels[0].answer_raw == " 001,50 đ\n"
    raw["answers"][0]["qid"] = request.questions[0].qid
    rejected = parse_generation(
        request, LocalGeneration(raw_text=json.dumps(raw), status="completed")
    )
    assert rejected[0].status == "parse_error"


def test_cohort_bound_to_receipt_groups_and_never_train_or_audit(source, tmp_path):  # noqa: F811
    full = make_pool(*source, "dev_select")
    s = full.samples[0]
    path = tmp_path / "cohort.json"
    cohort = {
        "protocol": "phase3_dev_v1",
        "test_or_ood_used": False,
        "qids": [s.question.qid],
        "groups": {s.question.qid: s.duplicate_group_id},
    }
    path.write_text(json.dumps(cohort))
    actual = make_pool(*source, "dev_select", path)
    assert actual.samples == full.samples and actual.evaluation_cohort_sha256 == sha256(path)
    for partition in ("train_fit", "audit_holdout", "test", "dev_calibrate"):
        with pytest.raises(PermissionError):
            make_pool(*source, partition, path)
    cohort["groups"][s.question.qid] = "wrong-group"
    path.write_text(json.dumps(cohort))
    with pytest.raises(ValueError, match="membership"):
        make_pool(*source, "dev_select", path)


def test_actual_transformers_bundled_sampling_cannot_override_greedy():
    transformers = pytest.importorskip("transformers")
    from transformers.generation.utils import GenerationMixin

    from vidoclens.teacher.local_qwen import greedy_generate

    class Model:
        generation_config = transformers.GenerationConfig(
            do_sample=True,
            temperature=0.7,
            top_k=20,
            top_p=0.8,
            transformers_version="4.57.1",
        )

        def generate(self, **kwargs):
            config = kwargs.pop("generation_config")
            defaults = kwargs.pop("use_model_defaults", None)
            effective, _ = GenerationMixin._prepare_generation_config(
                self, config, defaults, **kwargs
            )
            return effective

    actual = greedy_generate(Model(), {}, transformers.GenerationConfig(do_sample=False))
    assert actual.do_sample is False and actual.num_beams == 1
    assert actual.temperature == 1.0 and actual.top_p == 1.0


def test_ocr_cache_warming_shards_are_disjoint_and_cover_the_authorized_pool():
    from vidoclens.ocr.quality import select_shard

    population = list(range(101))
    shards = [select_shard(population, i, 3) for i in range(3)]
    assert [r for shard in shards for r in shard] == population
    assert not any(set(a) & set(b) for i, a in enumerate(shards) for b in shards[i + 1 :])
    for index, count in ((-1, 2), (2, 2), (0, 0), (0, 102)):
        with pytest.raises(ValueError, match="shard"):
            select_shard(population, index, count)
