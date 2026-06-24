"""Optional OpenAI backend (only loaded if selected)."""

from __future__ import annotations

from pathlib import Path

from .base import ProviderResponse, encode_image


class OpenAIProvider:
    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY missing")
        from openai import OpenAI  # lazy import

        self.client = OpenAI(api_key=api_key)

    def complete_json(
        self, system: str, parts: list, model: str, max_tokens: int = 1024, temperature: float = 0.0
    ) -> ProviderResponse:
        content = []
        for p in parts:
            if isinstance(p, str):
                content.append({"type": "text", "text": p})
            else:
                b64, mime = encode_image(Path(p))
                content.append(
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                )
        resp = self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
        )
        return ProviderResponse(
            text=resp.choices[0].message.content or "",
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
            model=model,
        )
