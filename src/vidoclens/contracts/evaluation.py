"""Offline scoring contracts; errors, abstentions and missing predictions stay in denominator."""

from math import isclose
from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import FrozenContract


class AnswerPrediction(FrozenContract):
    qid: str = Field(min_length=1)
    status: Literal["answered", "abstained", "error"]
    answer_raw: str | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def check_status(self) -> "AnswerPrediction":
        if self.status == "answered" and (self.answer_raw is None or not self.answer_raw.strip()):
            raise ValueError("answered predictions require nonblank raw text")
        if self.status != "answered" and self.answer_raw is not None:
            raise ValueError("abstained/error predictions cannot carry an answer")
        return self


class AnswerScores(FrozenContract):
    strict_nfc_em: float = Field(ge=0, le=1)
    strict_nfc_token_f1: float = Field(ge=0, le=1)
    strict_nfc_anls: float = Field(ge=0, le=1)


class EvaluationSummary(AnswerScores):
    protocol: Literal["strict_nfc_v1"] = "strict_nfc_v1"
    official_compatible: Literal[False] = False
    n_questions: int = Field(gt=0)
    n_answered: int = Field(ge=0)
    n_abstained: int = Field(ge=0)
    n_error: int = Field(ge=0)
    n_missing: int = Field(ge=0)
    coverage: float = Field(ge=0, le=1)
    selective_em: float | None = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_denominators(self) -> "EvaluationSummary":
        if self.n_answered + self.n_abstained + self.n_error + self.n_missing != self.n_questions:
            raise ValueError("status counts must sum to the full reference population")
        if not isclose(self.coverage, self.n_answered / self.n_questions):
            raise ValueError("coverage must use all reference questions as denominator")
        for score in (self.strict_nfc_em, self.strict_nfc_token_f1, self.strict_nfc_anls):
            if score > self.coverage and not isclose(score, self.coverage):
                raise ValueError("unanswered questions cannot contribute positive scores")
        if not self.n_answered:
            if self.selective_em is not None:
                raise ValueError("selective accuracy is undefined at zero coverage")
        elif self.selective_em is None or not isclose(
            self.selective_em, self.strict_nfc_em / self.coverage
        ):
            raise ValueError("selective accuracy must use answered questions as denominator")
        return self
