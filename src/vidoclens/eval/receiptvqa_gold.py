"""Privileged gold access lives in evaluation, separate from the question-only loader."""

from pathlib import Path

from vidoclens.contracts.dataset import GoldReference, ReceiptAccessPlan
from vidoclens.data.receiptvqa import _partition_rows, _reference


def load_evaluation_gold(
    archive: Path, plan: ReceiptAccessPlan, *, partition: str
) -> tuple[GoldReference, ...]:
    permitted = {"audit_holdout": "train", "dev_select": "dev", "dev_calibrate": "dev"}
    if partition not in permitted:
        raise PermissionError("Only audit_holdout/dev_select/dev_calibrate gold is enabled")
    return tuple(
        _reference(row)
        for row, entry in _partition_rows(archive, plan, permitted[partition])
        if entry.partition == partition
    )
