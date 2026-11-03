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
prompt's five canonical fields; Phase 2 uses separate strict `TeacherAnswer` and
`TeacherOutput` provider contracts.

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
59 exported root schemas after Phase 4 offline extensions; stored corpus/PII/model payloads
remain Git ignored.

Phase 4 adds `SilverSample`, `SilverPool`, `SilverLabel`, `SilverBatch`,
`FilterConfig`, `PartSupport`, `FilterDecision`, `FilterRun`, `SilverApproval` and
`SilverExperiment`. These keep local teacher results, raw targets, OCR evidence,
scope/permission hashes and fixture provenance separate from training execution.
They do not certify G3/G4 or grant access to API evaluation caches. See the
[offline workflow](../docs/PHASE4_OFFLINE_WORKFLOW.md) and PC handoff.

ADR-P4-002 adds eight local teacher config/request/plan/grant/output/snapshot schemas,
four blind review/item/human annotation schemas, and `SilverTrainingResult`.
Generation grants and training approvals are distinct; attestation fields and hashes
do not authenticate licenses, reviewers or actual GPU execution. See the
[extended tools](../docs/PHASE4_LOCAL_TOOLS.md) for exchange and integration details.
