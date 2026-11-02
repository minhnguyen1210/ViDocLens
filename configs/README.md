# Configuration status

These YAML files define draft defaults and planned run inputs. The current CLI/API
does not yet load them. Unresolved revisions, rights and price cards are `null` or
`false`; do not replace them with fabricated values. Phase 0 locks environments,
Phase 1 validates data, and later pipeline commands must validate a resolved config
before execution. Store its canonical hash alongside every run.

The lightweight API currently reads only `VIDOCLENS_EXTERNAL_ENABLED`; the demo
reads `VIDOCLENS_API_BASE_URL` and `GRADIO_SERVER_NAME`. No real external client exists.
