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
Phase 5 adds spatial/numeric/text snap guards and harm counts, frozen dev access/replay,
injected cascade gates/teacher verification, budget concurrency/unknown cost/cache integrity,
deadline/circuit behavior, routing Pareto/denominators, blind OOD human exchange and
archive-to-preregistration CLI tests that refuse final gold access. All new fixtures explicitly
remain synthetic; no live backend, human annotation or calibration claim follows.
Later suites include deterministic training resume, real fallback integration and GPU load.
No ML benchmark, accuracy claim or GPU compatibility follows from these smoke tests.

Repository workflow tests use synthetic fixtures and an isolated temporary Git
repository: forced-staged payload policy, index/worktree size separation, and
schema drift with a read-only check. They never stage or commit in the project repo.
