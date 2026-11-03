"""Local student training contracts; no provider credentials or teacher labels."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract, ReceiptQuestion


class StudentConfig(FrozenContract):
    protocol: Literal["phase3_gold_v1", "phase3_gold_v2"] = "phase3_gold_v1"
    attention_backend: Literal["auto", "math"] = "auto"
    deterministic_algorithms: bool = False
    model_id: Literal["Qwen/Qwen3-VL-2B-Instruct"] = "Qwen/Qwen3-VL-2B-Instruct"
    revision: Literal["89644892e4d85e24eaac8bacfd4f463576704203"] = (
        "89644892e4d85e24eaac8bacfd4f463576704203"
    )
    weights_sha256: SHA256 = "7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0"
    max_image_pixels: int = Field(default=262144, ge=4096, le=589824)
    min_image_pixels: int = Field(default=4096, ge=1024)
    max_sequence_length: int = Field(default=2048, ge=256, le=4096)
    max_new_tokens: int = Field(default=128, ge=32, le=256)
    lora_rank: int = Field(default=8, ge=1, le=16)
    lora_alpha: int = Field(default=16, ge=1)
    lora_dropout: float = Field(default=0.05, ge=0, lt=1)
    learning_rate: float = Field(default=0.0001, gt=0, le=0.001)
    weight_decay: float = Field(default=0.01, ge=0)
    warmup_ratio: float = Field(default=0.03, ge=0, lt=1)
    gradient_accumulation: int = Field(default=16, ge=1, le=64)
    epochs: int = Field(default=1, ge=1, le=2)
    seeds: tuple[int, ...] = (17, 42, 2026)
    prompt_path: str = "prompts/student_vqa_v1.txt"
    environment_lock: str = "infra/requirements/phase0-ml-linux-py311.lock"
    checkpoint_rule: Literal["dev_em_numeric_em_latency_earlier"] = (
        "dev_em_numeric_em_latency_earlier"
    )

    @model_validator(mode="after")
    def valid_profile(self):
        if self.protocol == "phase3_gold_v2" and (
            self.attention_backend != "math" or not self.deterministic_algorithms
        ):
            raise ValueError("v2 requires deterministic math attention")
        if self.min_image_pixels > self.max_image_pixels or self.seeds != (17, 42, 2026):
            raise ValueError("invalid pixel range or primary seed protocol")
        return self


class StudentQuestion(FrozenContract):
    question: ReceiptQuestion
    partition: Literal["train_fit", "dev_select"]
    duplicate_group_id: str = Field(min_length=1)
    image_path: str = Field(min_length=1)
    image_sha256: SHA256

    @model_validator(mode="after")
    def correct_split(self):
        expected = "train" if self.partition == "train_fit" else "dev"
        if self.question.source_split != expected:
            raise ValueError("student partition/source mismatch")
        return self


class StudentTrainingExample(FrozenContract):
    input: StudentQuestion
    answer_raw: str = Field(min_length=1, repr=False)

    @model_validator(mode="after")
    def train_only(self):
        if self.input.partition != "train_fit" or not self.answer_raw.strip():
            raise ValueError("training requires nonempty authorized train_fit gold")
        return self
