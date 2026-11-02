# Prompt registry

`teacher_vqa_v1.txt` is a draft instruction, not a validated production prompt.
Render image/question/OCR inputs in the adapter; do not interpolate labels.
Freeze prompt bytes, message layout, question ordering, schema and model snapshot
in the request hash. A changed prompt is a new version. Keep audit/test gold out of
prompts and examples. Model self-reported confidence is not calibrated confidence.
