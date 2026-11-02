"""Exact image grouping and a review-only perceptual candidate queue."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterator, Sequence

from vidoclens.contracts.ingestion import CorpusImage, DuplicateGroup, NearDuplicateCandidate


def exact_groups(images: Sequence[CorpusImage], pilot_ids: set[int]) -> tuple[DuplicateGroup, ...]:
    by_id = {r.source_image_id: r for r in images}
    if len(by_id) != len(images) or not pilot_ids <= by_id.keys():
        raise ValueError("duplicate IDs or pilot not covered by image inventory")
    parents = {key: key for key in by_id}

    def root(value):
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    for field in ("raw_image_sha256", "canonical_pixel_sha256"):
        first = {}
        for row in sorted(images, key=lambda r: r.source_image_id):
            representative = first.setdefault(getattr(row, field), row.source_image_id)
            left, right = root(representative), root(row.source_image_id)
            parents[max(left, right)] = min(left, right)
    components = defaultdict(list)
    for key in sorted(by_id):
        components[root(key)].append(key)
    groups = []
    for members in components.values():
        # Namespace/membership-linked ID, independent of traversal or Python hash seed.
        documents = sorted(by_id[key].document_id for key in members)
        identity = hashlib.sha256(json.dumps(documents, separators=(",", ":")).encode()).hexdigest()
        groups.append(
            DuplicateGroup(
                duplicate_group_id=f"receiptvqa-group:{identity}",
                source_image_ids=tuple(members),
                source_splits=tuple(sorted({by_id[key].source_split for key in members})),
                pilot_exposed=bool(set(members) & pilot_ids),
            )
        )
    return tuple(sorted(groups, key=lambda g: g.duplicate_group_id))


def near_candidates(
    images: Sequence[CorpusImage],
    groups: Sequence[DuplicateGroup],
    *,
    full_threshold: int = 6,
    crop_threshold: int = 4,
) -> Iterator[NearDuplicateCandidate]:
    """All-pairs within this source. Similarity is never a duplicate decision."""
    import numpy as np

    if not (0 <= full_threshold <= 64 and 0 <= crop_threshold <= 64):
        raise ValueError("perceptual thresholds must be within [0,64]")
    records = sorted(images, key=lambda r: r.source_image_id)
    membership = {i: g.duplicate_group_id for g in groups for i in g.source_image_ids}
    if set(membership) != {r.source_image_id for r in records}:
        raise ValueError("groups must cover exactly the inventory")
    full = np.array([int(r.phash64, 16) for r in records], dtype=np.uint64)
    crop = np.array([int(r.center_crop_phash64, 16) for r in records], dtype=np.uint64)
    for index, left in enumerate(records[:-1]):
        full_distance = np.bitwise_count(full[index + 1 :] ^ full[index])
        crop_distance = np.bitwise_count(crop[index + 1 :] ^ crop[index])
        selected = np.flatnonzero(
            (full_distance <= full_threshold) | (crop_distance <= crop_threshold)
        )
        for offset in selected:
            right = records[index + 1 + int(offset)]
            if membership[left.source_image_id] == membership[right.source_image_id]:
                continue
            yield NearDuplicateCandidate(
                left_image_id=left.source_image_id,
                right_image_id=right.source_image_id,
                left_group_id=membership[left.source_image_id],
                right_group_id=membership[right.source_image_id],
                full_phash_distance=int(full_distance[offset]),
                crop_phash_distance=int(crop_distance[offset]),
                crosses_official_splits=left.source_split != right.source_split,
            )
