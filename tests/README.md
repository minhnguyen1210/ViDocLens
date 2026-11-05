# Test boundaries

Implemented: HTTP readiness, explicit unavailable inference, upload validation,
external-processing policy, core contract invariants. Fixtures are synthetic.
Run `python -m pytest -q` with the `serve,dev` extras installed.

Phase 1 also covers strict/compatible metrics, multipart/ANLS edge cases,
split/duplicate containment, OCR cache integrity/concurrency, grouped bootstrap,
gold visibility, AI provenance, OOD rights/identity binding and review coverage.
SHA-pinned upstream parity runs separately against local fixtures/artifacts.

Phase 2 covers budget reservation/retry accounting and provider/Batch fixtures.
Phase 4 offline covers F0/F1 numeric/text/multipart evidence, fail-closed scope,
hash/replay integrity, filter audit denominators and matched experiment selections.
It also covers local request grouping/parsing, transactional retry/resume with zero-call
completed replay, snapshot/permission checks, atomic artifacts, dev-only threshold grid,
blind review coverage/provenance and fairness-checked 12-run paired/seed comparisons.
The Qwen GPU adapter has not been smoke-tested by these CPU fixtures.
Synthetic archive-to-CLI tests do not run a model or certify real data quality.
Later suites include snap ambiguity, deterministic training resume, cascade and GPU load.
No ML benchmark, accuracy claim or GPU compatibility follows from these smoke tests.

Phase 4 integration tests preserve the Phase 3 cohort and raw gold/silver targets,
check mixed-source exposure accounting and reject changed source/approval/group
bindings. Raw teacher replay rejects missing cache entries; format selection rejects
ineligible candidates, changed report bytes and mismatched cohorts. OCR shards must
cover the exact authorized pool without overlap. Actual GPU and human evidence is
tracked separately in [STATUS](../docs/STATUS.md).

Repository workflow tests use synthetic fixtures and an isolated temporary Git
repository: forced-staged payload policy, index/worktree size separation, and
schema drift with a read-only check. They never stage or commit in the project repo.
