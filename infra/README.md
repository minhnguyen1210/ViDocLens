# Deployment boundary

The root Dockerfile and Compose file provide a CPU foundation service bound to
localhost. They are not a GPU deployment. GPU images, reverse proxy, authentication,
monitoring and backup configuration are added in Phase 6 after package/model locks
and quality gates pass. Keep one inference worker per RTX 3060; multiple web workers
must not independently load copies of the student. See the canonical source of truth
and deployment runbook for the target topology.
