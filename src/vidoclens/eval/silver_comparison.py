"""Fairness-checked dev comparison of L2/P1/P2; no trainer or test access."""

from collections import defaultdict
from statistics import mean, stdev

from vidoclens.contracts.dataset import GoldReference
from vidoclens.eval.bootstrap import group_bootstrap
from vidoclens.eval.metrics import evaluate_answers, score_answer
from vidoclens.filtering.io import digest, revalidate

ARMS = ("L2", "P1-full", "P1-size", "P2")
SEEDS = (17, 42, 2026)
METRICS = ("strict_nfc_em", "strict_nfc_token_f1", "strict_nfc_anls")


def _macro(scores, units):
    grouped = defaultdict(list)
    for qid, value in scores.items():
        grouped[units[qid]].append(value)
    return mean(mean(values) for values in grouped.values())


def compare_results(
    training_pool,
    evaluation_pool,
    references,
    selections,
    results,
    *,
    resamples=2000,
    bootstrap_seed=42,
):
    pool = revalidate(evaluation_pool)
    training_pool = revalidate(training_pool)
    if training_pool.partition != "train_fit" or (
        training_pool.access_plan_sha256,
        training_pool.archive_sha256,
        training_pool.inventory_sha256,
    ) != (pool.access_plan_sha256, pool.archive_sha256, pool.inventory_sha256):
        raise ValueError("training/dev source identities differ")
    if {s.duplicate_group_id for s in (*training_pool.samples, *training_pool.gold_samples)} & {
        s.duplicate_group_id for s in pool.samples
    }:
        raise ValueError("training/evaluation groups overlap")
    if resamples < 2:
        raise ValueError("at least two bootstrap resamples required")
    if pool.partition != "dev_select":
        raise PermissionError(
            "Phase 4 comparison is dev_select only; no test/OOD/calibration/holdout tuning"
        )
    plans = [revalidate(p) for p in selections]
    runs = [revalidate(r) for r in results]
    expected = {(a, s) for a in ARMS for s in SEEDS}
    by_run = {(r.arm, r.seed): r for r in runs}
    by_plan = {(p.arm, p.seed): p for p in plans}
    if (
        len(runs) != 12
        or set(by_run) != expected
        or len(plans) != 9
        or set(by_plan) != expected - {("L2", s) for s in SEEDS}
    ):
        raise ValueError("comparison needs exactly 12 unique results and 9 selections")
    if len({r.run_id for r in runs}) != len(runs):
        raise ValueError("run IDs must be unique")
    reference_list = [GoldReference.model_validate(r.model_dump()) for r in references]
    gold = {r.qid: r for r in reference_list}
    samples = {s.question.qid: s for s in pool.samples}
    if (
        len(gold) != len(reference_list)
        or gold.keys() != samples.keys()
        or any(gold[q].document_id != samples[q].question.document_id for q in gold)
    ):
        raise ValueError("gold must cover exactly the frozen evaluation pool")
    first = by_plan[("P2", 17)]
    if first.pool_sha256 != digest(training_pool) or set(first.gold_qids) != {
        s.question.qid for s in training_pool.gold_samples
    }:
        raise ValueError("selections differ from training pool/gold membership")
    if any(
        not set(p.silver_qids) <= {s.question.qid for s in training_pool.samples} for p in plans
    ):
        raise ValueError("unknown silver training membership")
    common_plan = (
        first.pool_sha256,
        first.batch_sha256,
        first.filter_run_sha256,
        first.approval_sha256,
        first.training_profile_sha256,
        first.optimizer_updates,
        set(first.gold_qids),
        first.fixture_only,
    )
    for plan in plans:
        current = (
            plan.pool_sha256,
            plan.batch_sha256,
            plan.filter_run_sha256,
            plan.approval_sha256,
            plan.training_profile_sha256,
            plan.optimizer_updates,
            set(plan.gold_qids),
            plan.fixture_only,
        )
        if current != common_plan:
            raise ValueError("selection inputs/profile/budget/gold provenance differ")
    profiles = {(r.evaluation_profile_sha256, r.g3_evidence_sha256) for r in runs}
    if len(profiles) != 1:
        raise ValueError("evaluation protocol or G3 evidence differs")
    rows, em_scores = {}, {}
    groups = {q: s.duplicate_group_id for q, s in samples.items()}
    documents = {q: s.question.document_id for q, s in samples.items()}
    training_qids = set(first.gold_qids) | set(by_plan[("P1-full", 17)].silver_qids)
    if training_qids & samples.keys():
        raise ValueError("training/evaluation qids overlap")
    for (arm, seed), run in sorted(by_run.items()):
        if (
            run.fixture_only != first.fixture_only
            or run.training_pool_sha256 != first.pool_sha256
            or run.evaluation_pool_sha256 != digest(pool)
            or run.training_profile_sha256 != first.training_profile_sha256
            or run.optimizer_updates_completed != first.optimizer_updates
            or set(run.gold_qids) != set(first.gold_qids)
        ):
            raise ValueError("result pool/profile/compute/gold/fixture fairness mismatch")
        if arm != "L2":
            plan = by_plan[(arm, seed)]
            if run.selection_sha256 != digest(plan) or set(run.silver_qids) != set(
                plan.silver_qids
            ):
                raise ValueError("result does not match selected training membership")
        summary = evaluate_answers(reference_list, run.predictions).model_dump(mode="json")
        predictions = {p.qid: p.answer_raw for p in run.predictions}
        scores = {
            q: score_answer(predictions.get(q), ref.answers).model_dump() for q, ref in gold.items()
        }
        em = {q: values["strict_nfc_em"] for q, values in scores.items()}
        key = f"{arm}/{seed}"
        rows[key] = {
            "arm": arm,
            "seed": seed,
            "result_sha256": digest(run),
            "metrics": summary,
            "image_macro_em": _macro(em, documents),
            "group_macro_em": _macro(em, groups),
            "selected_gold": len(run.gold_qids),
            "selected_silver": len(run.silver_qids),
            "seen_unique_gold": sum(v > 0 for v in run.gold_exposure_counts.values()),
            "seen_unique_silver": sum(v > 0 for v in run.silver_exposure_counts.values()),
            "gold_exposures": sum(run.gold_exposure_counts.values()),
            "silver_exposures": sum(run.silver_exposure_counts.values()),
            "selected_checkpoint_step": run.selected_checkpoint_step,
            "selected_gold_exposures": sum(run.selected_gold_exposure_counts.values())
            if run.selected_gold_exposure_counts is not None
            else None,
            "selected_silver_exposures": sum(run.selected_silver_exposure_counts.values())
            if run.selected_silver_exposure_counts is not None
            else None,
            "training_seconds": run.training_seconds,
            "peak_reserved_bytes": run.peak_reserved_bytes,
        }
        em_scores[(arm, seed)] = em
    for seed in SEEDS:
        p2 = by_plan[("P2", seed)]
        if len(by_plan[("P1-size", seed)].silver_qids) != len(p2.silver_qids):
            raise ValueError("matched-size control differs from P2 size")
        if not set(p2.silver_qids) <= set(by_plan[("P1-full", seed)].silver_qids):
            raise ValueError("P2 must be a subset of F0")
        if (
            len({sum(by_run[(a, seed)].gold_exposure_counts.values()) for a in ARMS if a != "L2"})
            != 1
        ):
            raise ValueError("silver arms have different gold exposure budgets")
    aggregated = {}
    for arm in ARMS:
        aggregated[arm] = {}
        for metric in METRICS:
            values = [rows[f"{arm}/{s}"]["metrics"][metric] for s in SEEDS]
            aggregated[arm][metric] = {
                "mean": mean(values),
                "sample_std": stdev(values),
                "seeds": list(SEEDS),
            }
    paired = {}
    for control in ("P1-size", "P1-full", "L2"):
        per_seed = {}
        for seed in SEEDS:
            per_seed[str(seed)] = _bootstrap(
                em_scores[("P2", seed)],
                groups,
                em_scores[(control, seed)],
                resamples,
                bootstrap_seed,
            )
        fixed_seed_average = {
            arm: {q: mean(em_scores[(arm, seed)][q] for seed in SEEDS) for q in gold}
            for arm in ("P2", control)
        }
        deltas = [
            mean(em_scores[("P2", s)].values()) - mean(em_scores[(control, s)].values())
            for s in SEEDS
        ]
        paired["P2_vs_" + control] = {
            "primary": control == "P1-size",
            "per_seed": per_seed,
            "fixed_three_seed_mean_group_bootstrap": _bootstrap(
                fixed_seed_average["P2"],
                groups,
                fixed_seed_average[control],
                resamples,
                bootstrap_seed,
            ),
            "training_seed_delta_mean": mean(deltas),
            "training_seed_delta_sample_std": stdev(deltas),
        }
    # Slices are about student predictions on dev, independent of silver retention.
    from vidoclens.filtering.matching import answer_type, question_type

    slices = {}
    for axis, assignment in (
        ("question_type", {q: question_type(s.question.question_raw) for q, s in samples.items()}),
        ("reference_answer_type", {q: answer_type(gold[q].answers[0]) for q in gold}),
    ):
        slices[axis] = {}
        for group in sorted(set(assignment.values())):
            subset = [q for q, value in assignment.items() if value == group]
            slices[axis][group] = {
                "n_qa": len(subset),
                "arms": {
                    arm: {
                        "seed_em": {
                            str(s): mean(em_scores[(arm, s)][q] for q in subset) for s in SEEDS
                        }
                    }
                    for arm in ARMS
                },
            }
    return {
        "protocol": "phase4_dev_comparison_v1",
        "partition": "dev_select",
        "fixture_only": first.fixture_only,
        "evaluation_pool_sha256": digest(pool),
        "reference_sha256": digest(
            [r.model_dump(mode="json") for r in sorted(reference_list, key=lambda r: r.qid)]
        ),
        "selection_sha256s": sorted(digest(p) for p in plans),
        "runs": rows,
        "seed_summary": aggregated,
        "paired_em": paired,
        "slices": slices,
        "g4_automatically_passed": False,
        "limitations": [
            "dev_select findings are exploratory, not final test confirmation",
            "fairness checks validate submitted manifests; they do not attest actual GPU execution",
            "group bootstrap conditions on fixed seeds; training variance reported separately",
            "primary P2 vs P1-size; others secondary; no adjusted significance claim",
            "question types are heuristic; reference answer type uses first full alternative",
            "same update budget does not imply identical wall time, tokens or difficulty",
        ],
    }


def _bootstrap(scores, groups, paired, resamples, seed):
    if len(set(groups.values())) < 2:
        return {
            "point_estimate": mean(scores[q] - paired[q] for q in scores),
            "lower_95": None,
            "upper_95": None,
            "reason": "fewer_than_two_independent_groups",
            "training_variance_included": False,
        }
    return group_bootstrap(scores, groups, paired_scores=paired, resamples=resamples, seed=seed)
