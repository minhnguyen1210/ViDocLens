# Test boundaries

Implemented: HTTP readiness, explicit unavailable inference, upload validation,
external-processing policy, core contract invariants. Fixtures are synthetic.
Run `python -m pytest -q` with the `serve,dev` extras installed.

Phase 1 also covers strict/compatible metrics, multipart/ANLS edge cases,
split/duplicate containment, OCR cache integrity/concurrency, grouped bootstrap,
gold visibility, AI provenance, OOD rights/identity binding and review coverage.
SHA-pinned upstream parity runs separately against local fixtures/artifacts.

Later suites: budget reservation/retry accounting, filter numerical evidence and
snap ambiguity, deterministic training resume, cascade refusal, and GPU load tests.
No ML benchmark, accuracy claim or GPU compatibility follows from these smoke tests.

Repository workflow tests use synthetic fixtures and an isolated temporary Git
repository: forced-staged payload policy, index/worktree size separation, and
schema drift with a read-only check. They never stage or commit in the project repo.
