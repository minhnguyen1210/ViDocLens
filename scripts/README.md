# Operational entry points

Current executable commands from the repository root:

```shell
python -m pip install -e ".[serve,dev]"
python -m vidoclens doctor
python scripts/export_schemas.py
python -m pytest -q
python -m ruff check .
python -m uvicorn vidoclens.serving.api:app --host 127.0.0.1 --port 8000
```

Create and activate an isolated Python environment first. For the optional status
demo install `.[demo]` and run `python app/demo.py` in a second terminal.
`docker compose up --build` starts the CPU API scaffold;
`docker compose --profile demo up --build` also starts the status demo.
Phase 0 has explicit local student/OCR feasibility runners described below.
Production image ingestion, teacher, train and final evaluation runners remain unimplemented.
Annotation loading and project metrics are implemented as described below.
The doctor does not load a GPU.

Read-only ReceiptVQA annotation audit (already downloaded archive only):

```shell
python -m vidoclens.data.audit_receiptvqa --archive data/raw/receiptvqa/ReceiptVQA_annotations.zip --output data/manifests/receiptvqa_annotations_new_audit.json
```

Use a new output name for each run; existing reports and input ZIP cannot be
overwritten. Exit codes: 0 = structural checks pass, 1 = data integrity findings,
2 = invalid input/unreadable archive. Output contains aggregate counts and hashes,
never QA contents. No downloads, extraction, normalization or image validation.
On Windows use the existing `.venv\Scripts\python.exe` interpreter.

Load the existing CSV archive with question-only output (console shows counts only):

```shell
python -m vidoclens.data.receiptvqa --archive data/raw/receiptvqa/ReceiptVQA_annotations.zip --split train
python -m vidoclens.data.receiptvqa --archive data/raw/receiptvqa/ReceiptVQA_annotations.zip --split dev
```

Gold training/evaluation access requires explicit receipt/group assignments and
uses separate Python APIs. Test access is blocked. Project metrics EM/token F1/ANLS
and qid-aligned aggregation are in `vidoclens.eval.metrics`; no official parity claim.
See [loader and metrics protocol](../docs/ANNOTATION_LOADER_AND_METRICS.md).

## Phase 0 local GPU/OCR pilot

See [verified environment and runbook](../docs/PHASE0_ENVIRONMENT.md) for the
WSL user, exact Python/package/model versions, hashed locks and run artifacts.
`bootstrap_phase0.sh` creates isolated Linux environments; `install_phase0_candidate.sh`
installs the original candidate roots. Prefer the checked-in hashed locks for a
new reproduction. `lock_phase0_environment.sh` records an environment and creates
a separate fresh venv; it refuses to overwrite an existing lock or destination.
`download_phase0_ocr.py` explicitly downloads pinned official OCR weights; run it
only when downloads are authorized and weights are absent, never as an import side effect.

```powershell
wsl -d Ubuntu-24.04 -u vidoclens -- bash /mnt/c/Users/Admin/Desktop/ViDocLens/scripts/run_phase0_pilot.sh student student_new_run -repro
wsl -d Ubuntu-24.04 -u vidoclens -- bash /mnt/c/Users/Admin/Desktop/ViDocLens/scripts/run_phase0_pilot.sh ocr ocr_new_run -repro
```

Each name must be new. Run sequentially. Inputs use train-only byte groups,
reject gold fields and validate image hashes. Outputs include actual local model
answers/OCR, timing and resource diagnostics; they are Git ignored. These are not
accuracy evaluations or serving readiness checks. No training or billable API call.

## Phase 1 ingestion and draft split

`python -m vidoclens.data.ingest_receiptvqa` validates existing archives and produces
a label-free image inventory with full-decode/CRC, raw/pixel hashes and perceptual
fingerprints. Run in the locked Linux ML environment (Pillow/NumPy); optional
dependencies for a new host are declared in `.[data]`.

`python -m vidoclens.data.split_draft` produces exact groups, a pending near-duplicate
review queue, quarantine assignments and nested gold-group IDs in a **draft**.
It does not grant training access or freeze a final split. Both CLIs refuse to
overwrite output directories and reject incomplete/tampered inputs.
See [Phase 1 workflow and exact commands](../docs/PHASE1_WORKFLOW.md).

`check_metric_parity.py` runs SHA-pinned upstream Accuracy/F1/ANLS against 260
deterministic fixtures. Source files and anls wheel must already exist in ignored
artifacts; the script does not download/install them. The paper's historical
unpinned anls version remains unknown.

Phase 1 modules also provide conservative freeze, OCR/cache, R1/bootstrap,
question-only distribution/overlap audit and transcription review scoring.
See [actual results and the AI-assisted G1 protocol](../docs/PHASE1_RESULTS.md).

`vidoclens.data.ood_seed` imports already-downloaded Commons seed images with rights
and cross-source overlap checks. `vidoclens.data.local_ai_review` runs the existing
offline GPU model with reference-free inputs. Outputs require explicit image
adjudication; `vidoclens.data.phase1_gate` validates the resulting evidence chain.
See the [commands](../docs/PHASE1_WORKFLOW.md); these modules never promote AI
annotations to human gold or enable training/final evaluation on the seed.

Repository maintenance (no network or Git writes):

- `python scripts/export_schemas.py --check`: fail on missing/changed/stale schemas
  without writing files. Omit `--check` to regenerate; stale schema files require
  explicit review/removal, never automatic deletion.
- `python scripts/check_repo.py`: check tracked/untracked nonignored file names,
  sizes and worktree YAML syntax. It does not inspect secrets or approve data rights.
- `python scripts/check_repo.py --staged`: inspect index paths/sizes for the next
  manual commit, not unstaged worktree content; exit 2 when there are no staged
  additions/modifications. It does not stage or commit anything.

The 5 MiB file threshold is this repository's source/docs policy, not a GitHub limit.
See [CONTRIBUTING](../CONTRIBUTING.md) for the owner's manual commit/push sequence.
