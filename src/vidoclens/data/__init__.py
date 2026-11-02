"""Dataset adapters, canonical image records, rights ledger, duplicate groups and immutable
split manifests. Never expose held-out labels to training.

Annotation audit and label-separated CSV loading are implemented. Image
ingestion, deduplication and split generation remain planned. Access manifests
must be supplied explicitly; question-only outputs contain no reference fields.
"""
