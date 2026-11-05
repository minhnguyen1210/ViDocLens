"""Single-question raw labeling candidate; actual decoded text is always preserved."""

from typing import Literal

from pydantic import Field

from vidoclens.contracts.local_teacher import LocalTeacherConfig, LocalTeacherPlan


class RawTeacherConfig(LocalTeacherConfig):
    protocol: Literal["local_labels_single_raw_v1"] = "local_labels_single_raw_v1"
    max_questions: Literal[1] = 1
    qid_format: Literal["canonical"] = "canonical"
    max_new_tokens: int = Field(default=128, ge=32, le=256)


class RawTeacherPlan(LocalTeacherPlan):
    protocol: Literal["local_single_raw_plan_v1"] = "local_single_raw_plan_v1"
    config: RawTeacherConfig
