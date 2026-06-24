"""Gemini backend (cheapest vision tier). Uses the google-genai SDK."""

from __future__ import annotations

from pathlib import Path

from .base import ProviderResponse, with_retries


class GeminiProvider:
    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY missing")
        from google import genai  # lazy import

        self._genai = genai
        self.client = genai.Client(api_key=api_key)

    def complete_json(
        self, system: str, parts: list, model: str, max_tokens: int = 1024, temperature: float = 0.0
    ) -> ProviderResponse:
        from google.genai import types

        contents = []
        for p in parts:
            if isinstance(p, (str,)):
                contents.append(p)
            else:  # Path -> image bytes
                path = Path(p)
                mime = "image/jpeg"
                if path.suffix.lower() in (".png",):
                    mime = "image/png"
                contents.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=mime))

        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        )
        resp = with_retries(
            lambda: self.client.models.generate_content(model=model, contents=contents, config=cfg)
        )
        usage = getattr(resp, "usage_metadata", None)
        return ProviderResponse(
            text=resp.text or "",
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            model=model,
        )
