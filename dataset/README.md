# Sample data (SYNTHETIC)

These rows and images are **synthetic placeholders** so ClaimLens runs out-of-the-box
— solid-color images and made-up labels, **not** real claim photos. Replace this folder
with your own data in the same shape:

- `claims.csv` — inputs: `user_id, image_paths(;-separated), user_claim, claim_object`
- `sample_claims.csv` — the same inputs **plus** the 14 labeled output columns, for evaluation
- `user_history.csv` — per-user risk context
- `evidence_requirements.csv` — minimum-evidence rules by object/issue family
- `images/...` — referenced by `image_paths`

See the output schema + allowed values in [`evidence_review/schema.py`](../evidence_review/schema.py).
