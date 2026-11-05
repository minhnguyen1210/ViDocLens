"""Deterministic matched-size selections; actual training stays in the Phase 3 runner."""

from collections import defaultdict

from vidoclens.contracts.silver import SilverExperiment
from vidoclens.filtering.io import digest, revalidate
from vidoclens.filtering.pipeline import validate_run


def select_experiments(pool, batch, run, approval, training_profile_sha256, optimizer_updates):
    pool, batch, run = validate_run(pool, batch, run)
    approval = revalidate(approval)
    if pool.partition != "train_fit" or not pool.gold_samples:
        raise PermissionError("experiment selection requires train_fit and G10 membership")
    if run.config.status != "frozen_dev_select":
        raise PermissionError("freeze filter before selecting training experiments")
    if (
        approval.pool_sha256 != digest(pool)
        or approval.batch_sha256 != digest(batch)
        or not all(
            (
                approval.training_labels_allowed,
                approval.data_rights_verified,
                approval.model_license_verified,
                approval.quality_pilot_passed,
            )
        )
    ):
        raise PermissionError("local label training gate has not passed for this exact batch")
    f0 = sorted(d.qid for d in run.decisions if d.f0_keep)
    f1 = sorted(d.qid for d in run.decisions if d.f1_keep)
    if not f1:
        raise ValueError("F1 retained no labels; cannot fabricate a distillation experiment")
    strata, wanted = defaultdict(list), defaultdict(int)
    for d in run.decisions:
        key = (d.question_type, d.answer_type)
        if d.f0_keep:
            strata[key].append(d.qid)
        if d.f1_keep:
            wanted[key] += 1
    output = []
    for seed in (17, 42, 2026):
        matched = []
        for key, count in sorted(wanted.items()):
            # Content ranking is independent of input order and Python hash/random state.
            ranked = sorted(strata[key], key=lambda qid: (digest([seed, key, qid]), qid))
            matched.extend(ranked[:count])
        for arm, selected in (("P1-full", f0), ("P1-size", sorted(matched)), ("P2", f1)):
            output.append(
                SilverExperiment(
                    arm=arm,
                    seed=seed,
                    pool_sha256=digest(pool),
                    batch_sha256=digest(batch),
                    filter_run_sha256=digest(run),
                    approval_sha256=digest(approval),
                    training_profile_sha256=training_profile_sha256,
                    optimizer_updates=optimizer_updates,
                    gold_qids=tuple(sorted(s.question.qid for s in pool.gold_samples)),
                    silver_qids=tuple(selected),
                    fixture_only=batch.fixture_only,
                )
            )
    return tuple(output)
