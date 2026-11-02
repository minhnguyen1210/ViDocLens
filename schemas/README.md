# Schema authority

Pydantic definitions in `src/vidoclens/contracts/` are authoritative.
Regenerate checked-in JSON schemas with `python scripts/export_schemas.py` after
contract changes. Increment schema versions for incompatible changes and add a
migration. These are draft offline contracts; they do not imply working inference.

`QARecord.answers` contains alternatives of COMPLETE answers. Its optional
`answer_parts` is a parallel list: each alternative has its own ordered evidence
parts. `Prediction.answer_parts` describes the single prediction. Preserve the raw
ReceiptVQA `¡sep¿` serialization until official parser/evaluator parity is verified;
the scaffold does not implement that parser. `TeacherInput` deliberately has no
answer fields and rejects extra keys, including nested answer keys. Do not serialize
a gold `QARecord` directly into a teacher prompt. `TeacherLabel` matches the draft
prompt's five canonical fields; provider strict-schema integration remains pending.

`Phase0PilotManifest` is a label-free feasibility input. It rejects unknown fields,
duplicate document/qid/image hashes and requires exclusion from future audit holdout.
The runtime additionally verifies local bytes and official-train-only hash membership.
It does not grant access to gold or certify near-duplicate removal.

Phase 1 adds `CorpusImage`, `DuplicateGroup`, `NearDuplicateCandidate` and
`SplitDraft` schemas. Pixel hashes explicitly differ from file hashes; canonical
derivative files have not been materialized. Perceptual candidates cannot auto-merge.
The draft can represent quarantine but cannot grant training or be parsed as a
`ReceiptAccessPlan`. ADR-020 adds conservative candidate containment as a separate
freeze path; it never claims all uncertain pairs are proven duplicates. Quarantined
assignments cannot expose training gold. Frozen readers verify graph/plan hashes.

`FeatureFingerprint`/`FeatureCandidate` validate rotation/crop/gradient artifacts.
`TranscriptionReview`/`OODAnnotation` distinguish AI review from human gold, preserve
evidence provenance and reject AI records claiming human verification. There are
22 exported root schemas; stored corpus/PII/model payloads remain Git ignored.
