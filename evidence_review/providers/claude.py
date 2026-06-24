"""Claude backend (judge tier; can also do perception)."""

from __future__ import annotations

from pathlib import Path

from .base import ProviderResponse, encode_image, with_retries


class ClaudeProvider:
    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")
        import anthropic  # lazy import

        self.client = anthropic.Anthropic(api_key=api_key)

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
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": b64},
                    }
                )
        # nudge JSON-only output
        content.append({"type": "text", "text": "Respond with a single JSON object only."})

        msg = with_retries(
            lambda: self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": content}],
            )
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return ProviderResponse(
            text=text,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            model=model,
        )
