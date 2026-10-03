"""Copilot guardrails: numbers must come from tools; no write path to devices."""

from __future__ import annotations

import re

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def extract_numbers(text: str) -> list[str]:
    return NUMBER.findall(text or "")


def faithfulness(answer: str, tool_blobs: list[str], atol_ratio: float = 0.02) -> tuple[bool, list[str]]:
    """Every number in the answer must appear in a tool payload (allow rounding)."""
    hay = " ".join(tool_blobs)
    hay_nums = [float(x) for x in extract_numbers(hay)]
    missing = []
    for token in extract_numbers(answer):
        val = float(token)
        if any(abs(val - h) <= max(1.0, abs(h) * atol_ratio) or token in hay for h in hay_nums):
            continue
        # integers that are IDs / years / slot counts often appear as substrings
        if token in hay:
            continue
        missing.append(token)
    return len(missing) == 0, missing


WRITE_PATTERNS = (
    "turn on",
    "turn off",
    "turn pump",
    "switch on",
    "switch off",
    "dispatch now",
    "override the optimizer",
    "ignore constraints",
    "just run",
    "just turn",
    "switch the",
    "chargers on",
)


def is_actuation_request(text: str) -> bool:
    t = (text or "").lower()
    if any(p in t for p in WRITE_PATTERNS):
        return True
    return bool(
        re.search(r"\b(turn|switch|start|stop)\b.{0,40}\b(on|off|now|immediately)\b", t)
        and re.search(r"\b(pump|load|compressor|chargers?|hvac|depot|ev)\b", t)
    )


def sanitize_tool_text(text: str) -> str:
    """Tool outputs are data, never instructions."""
    blocked = ("ignore previous", "system prompt", "you are now")
    out = text
    for b in blocked:
        out = out.replace(b, "")
    return out
