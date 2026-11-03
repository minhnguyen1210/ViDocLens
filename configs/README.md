# Configuration status

Configuration readiness is per consumer. The Phase 2 teacher CLI reads its YAML
and validates profile, prices and request-scoped permission artifacts. Phase 4
`python -m vidoclens.filtering` reads `filtering/f1.yaml` through `FilterConfig`;
its defaults are **not calibrated**. Freeze binds dev evidence and access-plan
identity before holdout audit or training selection. Keep immutable run copies.

`python -m vidoclens.teacher.local_labels config --snapshot ... --output ...` creates
candidate `LocalTeacherConfig` defaults bound to an existing snapshot manifest.
It does not download/approve a model or validate GPU compatibility. No permission
template grants generation/training by default. See [local tools](../docs/PHASE4_LOCAL_TOOLS.md).

Student/serving experiment candidates in this checkout are not proof of training
or deployment. Integrate the PC Phase 3 consumer separately. Never invent resolved
revisions, rights, prices or successful gate values to make a config load.

The lightweight API currently reads only `VIDOCLENS_EXTERNAL_ENABLED`; the demo
reads `VIDOCLENS_API_BASE_URL` and `GRADIO_SERVER_NAME`. The teacher external client
is separate from the still-unimplemented product inference backend.
