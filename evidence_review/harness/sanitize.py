"""Inbound prompt-injection guard for untrusted external chat text.

When claim text arrives from an external chat provider (Slack, WhatsApp, a CRM
webhook, …), the conversation is UNTRUSTED data, not instructions. This is the
text-channel sibling of `tools/ocr_injection.py` (which guards text painted
INSIDE images): both raise the SAME existing risk flag, `text_instruction_present`
(see `schema.RISK_FLAGS`), so the judge — which is told to decide from pixels and
ignore embedded directives — handles them uniformly.

Policy: we never raise and never mutate the text (the judge decides from the
actual image pixels regardless). We only emit the flag as a signal. Patterns are
kept tight to avoid false positives on ordinary claim language ("the screen is
cracked", "scratch on the top-left corner").
"""

from __future__ import annotations

import re

# Instruction-injection / role-hijack / tool-exfiltration phrasing. Each pattern
# targets directive language that a normal damage description would not contain.
_INJECTION_PATTERNS = [
    # "ignore / disregard / forget (the) previous/above/prior instructions"
    re.compile(
        r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b"
        r"(previous|prior|above|earlier|all|the\s+system)\b[^.\n]{0,20}"
        r"\b(instruction|instructions|prompt|prompts|rule|rules|context|message)s?\b",
        re.IGNORECASE,
    ),
    # role / persona hijack: "system:", "assistant:", "you are now", "act as", "pretend you are"
    re.compile(r"(?m)^\s*(system|assistant|developer)\s*:", re.IGNORECASE),
    re.compile(
        r"\byou\s+are\s+(now|a|an)\b|\bact\s+as\b|\bpretend\s+(to\s+be|you('?re|\s+are))\b",
        re.IGNORECASE,
    ),
    # direct command to the model to change its behaviour / verdict
    re.compile(
        r"\b(you\s+must|you\s+should\s+now|from\s+now\s+on|new\s+instructions?)\b",
        re.IGNORECASE,
    ),
    # explicit attempt to force a favourable verdict
    re.compile(
        r"\b(mark|set|approve|classify|treat)\b[^.\n]{0,30}\b(as\s+)?"
        r"(approved|supported|valid|accepted|legitimate|genuine)\b",
        re.IGNORECASE,
    ),
    # tool / data exfiltration phrasing
    re.compile(
        r"\b(system\s+prompt|reveal|exfiltrate|print|leak|disclose|repeat)\b"
        r"[^.\n]{0,30}\b(prompt|instructions?|secret|api[\s_-]?key|password|token|credentials?)\b",
        re.IGNORECASE,
    ),
]


def sanitize_claim_text(text):
    """Scan untrusted inbound chat text for prompt-injection.

    Returns ``(text_unchanged, flags)``. ``flags`` is ``["text_instruction_present"]``
    if any injection pattern matches, else ``[]``. Never raises; the text is
    returned verbatim (the judge decides from pixels — the flag is the signal).
    """
    if not text:
        return text, []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return text, ["text_instruction_present"]
    return text, []
