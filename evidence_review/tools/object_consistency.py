"""ObjectConsistencyTool — zero-shot claim<->image check (ADAPTER, CPU-feasible).

Uses open_clip ViT-B-32 (MIT/Apache weights) to test whether the image actually
depicts the claimed object type, independent of the VLM. If the claimed object
is not the best-matching class (or similarity is low), assert `wrong_object` —
an independent signal the VLM judge cannot override by itself (P8).

Self-disables unless `open_clip_torch` is installed. open_clip is the LIVE
recommendation from research; we ship it as an opt-in adapter so the default
CPU run stays dependency-light. Enable: pip install torch open_clip_torch.
GroundingDINO / OWL-ViT (box-level part presence) are documented as heavier
adapters in docs/SCENARIO_COVERAGE.md.
"""

from __future__ import annotations

from ..harness.tool import Tool, ToolResult

_OBJECTS = ["car", "laptop", "package"]
_PROMPTS = {
    "car": "a photo of a car",
    "laptop": "a photo of a laptop computer",
    "package": "a photo of a shipping package or cardboard box",
}
# Conservative: only assert wrong_object when the claimed class is clearly below
# the best-matching class (large CLIP gap). Keeps false positives ~0 on valid,
# possibly-cropped/damaged images so review accuracy is preserved.
_SIM_MARGIN = 0.05


class ObjectConsistencyTool(Tool):
    name = "object_consistency"
    tier = "consistency"
    produces_flags = ("wrong_object",)
    optional = True

    def __init__(self):
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._torch = None

    def available(self, ctx) -> bool:
        try:
            import open_clip  # noqa: F401

            return True
        except Exception:
            return False

    def _load(self):
        if self._model is None:
            import open_clip
            import torch

            self._torch = torch
            self._model, _, self._preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained="openai"
            )
            self._tokenizer = open_clip.get_tokenizer("ViT-B-32")
            self._model.eval()

    def run(self, ctx) -> ToolResult:
        try:
            self._load()
        except Exception as e:
            return self._skip(f"open_clip load failed: {e}")

        import torch
        from PIL import Image

        claimed = (ctx.claim_object or "").lower()
        text = self._tokenizer([_PROMPTS[o] for o in _OBJECTS])
        flags, per_image = set(), []
        with torch.no_grad():
            tfeat = self._model.encode_text(text)
            tfeat = tfeat / tfeat.norm(dim=-1, keepdim=True)
            for p in ctx.abs_paths:
                if not p.exists():
                    continue
                img = self._preprocess(Image.open(p).convert("RGB")).unsqueeze(0)
                ifeat = self._model.encode_image(img)
                ifeat = ifeat / ifeat.norm(dim=-1, keepdim=True)
                sims = (ifeat @ tfeat.T).squeeze(0).tolist()
                scored = dict(zip(_OBJECTS, [round(s, 3) for s in sims]))
                best = max(scored, key=scored.get)
                ok = (best == claimed) or (
                    claimed in scored and scored[claimed] >= scored[best] - _SIM_MARGIN
                )
                if not ok:
                    flags.add("wrong_object")
                per_image.append(
                    {
                        "image_id": p.stem,
                        "sims": scored,
                        "best": best,
                        "claimed": claimed,
                        "consistent": ok,
                    }
                )

        note = f"clip object check: flags={sorted(flags) or 'none'}"
        return ToolResult(
            name=self.name,
            available=True,
            signals={"per_image": per_image},
            risk_flags=sorted(flags),
            evidence={"clip_object": per_image},
            note=note,
        )
