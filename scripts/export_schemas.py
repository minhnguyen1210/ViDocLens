"""Regenerate JSON Schema artifacts from the authoritative Python contracts."""

import argparse
import json
from pathlib import Path

from vidoclens.contracts.ai_review import (
    AIAdjudication,
    AIReviewOutput,
    AIReviewTask,
    OODSeedDocument,
    OODSeedQA,
)
from vidoclens.contracts.dataset import (
    GoldReference,
    ReceiptAccessPlan,
    ReceiptQuestion,
    SupervisedReceiptExample,
)
from vidoclens.contracts.distillation import (
    DistillationConfig,
    DistillationExample,
    DistillationPlan,
    Phase4Criteria,
    Phase4GateReport,
)
from vidoclens.contracts.evaluation import AnswerPrediction, AnswerScores, EvaluationSummary
from vidoclens.contracts.ingestion import (
    CorpusImage,
    DuplicateGroup,
    FeatureCandidate,
    FeatureFingerprint,
    NearDuplicateCandidate,
    SplitDraft,
)
from vidoclens.contracts.local_teacher import (
    LocalGeneration,
    LocalGenerationGrant,
    LocalModelSnapshot,
    LocalTeacherAnswer,
    LocalTeacherConfig,
    LocalTeacherOutput,
    LocalTeacherPlan,
    LocalTeacherRequest,
)
from vidoclens.contracts.models import (
    Document,
    OCRResult,
    Prediction,
    QARecord,
    TeacherInput,
    TeacherLabel,
)
from vidoclens.contracts.phase3 import Phase3Continuation
from vidoclens.contracts.pilot import Phase0PilotManifest
from vidoclens.contracts.raw_teacher import RawTeacherConfig, RawTeacherPlan
from vidoclens.contracts.review import OODAnnotation, TranscriptionReview
from vidoclens.contracts.silver import (
    FilterConfig,
    FilterDecision,
    FilterRun,
    PartSupport,
    SilverApproval,
    SilverBatch,
    SilverExperiment,
    SilverLabel,
    SilverPool,
    SilverSample,
)
from vidoclens.contracts.silver_reparse import SilverReparseManifest
from vidoclens.contracts.silver_results import SilverTrainingResult
from vidoclens.contracts.silver_review import (
    SilverHumanJudgment,
    SilverHumanReview,
    SilverReviewItem,
    SilverReviewPacket,
)
from vidoclens.contracts.student import StudentConfig, StudentQuestion, StudentTrainingExample
from vidoclens.contracts.teacher import (
    TeacherAnswer,
    TeacherOutput,
    TeacherPermission,
    TeacherPriceCard,
    TeacherProfile,
    TeacherQuery,
    TeacherRequest,
    TeacherResult,
    TeacherUsage,
)

MODELS = {
    "raw_teacher_config": RawTeacherConfig,
    "raw_teacher_plan": RawTeacherPlan,
    "silver_reparse_manifest": SilverReparseManifest,
    "phase4_criteria": Phase4Criteria,
    "phase4_gate_report": Phase4GateReport,
    "distillation_config": DistillationConfig,
    "distillation_example": DistillationExample,
    "distillation_plan": DistillationPlan,
    "local_teacher_config": LocalTeacherConfig,
    "local_teacher_request": LocalTeacherRequest,
    "local_teacher_plan": LocalTeacherPlan,
    "local_generation_grant": LocalGenerationGrant,
    "local_teacher_answer": LocalTeacherAnswer,
    "local_teacher_output": LocalTeacherOutput,
    "local_generation": LocalGeneration,
    "local_model_snapshot": LocalModelSnapshot,
    "silver_review_item": SilverReviewItem,
    "silver_review_packet": SilverReviewPacket,
    "silver_human_judgment": SilverHumanJudgment,
    "silver_human_review": SilverHumanReview,
    "silver_training_result": SilverTrainingResult,
    "silver_sample": SilverSample,
    "silver_pool": SilverPool,
    "silver_label": SilverLabel,
    "silver_batch": SilverBatch,
    "filter_config": FilterConfig,
    "part_support": PartSupport,
    "filter_decision": FilterDecision,
    "filter_run": FilterRun,
    "silver_approval": SilverApproval,
    "silver_experiment": SilverExperiment,
    "phase3_continuation": Phase3Continuation,
    "student_config": StudentConfig,
    "student_question": StudentQuestion,
    "student_training_example": StudentTrainingExample,
    "document": Document,
    "qa_record": QARecord,
    "ocr_result": OCRResult,
    "prediction": Prediction,
    "teacher_input": TeacherInput,
    "teacher_label": TeacherLabel,
    "receipt_question": ReceiptQuestion,
    "receipt_access_plan": ReceiptAccessPlan,
    "gold_reference": GoldReference,
    "supervised_receipt_example": SupervisedReceiptExample,
    "answer_prediction": AnswerPrediction,
    "answer_scores": AnswerScores,
    "evaluation_summary": EvaluationSummary,
    "phase0_pilot_manifest": Phase0PilotManifest,
    "corpus_image": CorpusImage,
    "duplicate_group": DuplicateGroup,
    "near_duplicate_candidate": NearDuplicateCandidate,
    "split_draft": SplitDraft,
    "transcription_review": TranscriptionReview,
    "ood_annotation": OODAnnotation,
    "feature_fingerprint": FeatureFingerprint,
    "feature_candidate": FeatureCandidate,
    "ood_seed_document": OODSeedDocument,
    "ood_seed_qa": OODSeedQA,
    "ai_review_task": AIReviewTask,
    "ai_review_output": AIReviewOutput,
    "ai_adjudication": AIAdjudication,
    "teacher_query": TeacherQuery,
    "teacher_profile": TeacherProfile,
    "teacher_request": TeacherRequest,
    "teacher_answer": TeacherAnswer,
    "teacher_output": TeacherOutput,
    "teacher_result": TeacherResult,
    "teacher_usage": TeacherUsage,
    "teacher_permission": TeacherPermission,
    "teacher_price_card": TeacherPriceCard,
}


def export(root: Path, *, check: bool = False) -> list[str]:
    """Check without writes, including missing/stale files; ignore platform newlines."""
    expected = {f"{name}.schema.json" for name in MODELS}
    problems = sorted(p.name for p in root.glob("*.schema.json") if p.name not in expected)
    if not check:
        root.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        file = root / f"{name}.schema.json"
        text = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
        if check:
            if not file.exists() or file.read_text(encoding="utf-8") != text:
                problems.append(file.name)
        else:
            file.write_text(text, encoding="utf-8", newline="\n")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report drift without rewriting files")
    args = parser.parse_args()
    problems = export(Path(__file__).resolve().parents[1] / "schemas", check=args.check)
    if problems:
        print("Schema mismatch/stale files: " + ", ".join(problems))
        raise SystemExit(1)
    print(f"{len(MODELS)} schemas {'match' if args.check else 'exported'}")


if __name__ == "__main__":
    main()
