"""Mask Aadhaar and PAN numbers BEFORE any text is sent to an external API.
The real values are restored locally after extraction."""
import re

AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


def mask(text: str):
    mapping: dict[str, str] = {}

    def make(label):
        def repl(m):
            token = f"[{label}_{len(mapping) + 1}]"
            mapping[token] = m.group(0)
            return token
        return repl

    text = AADHAAR.sub(make("AADHAAR"), text)
    text = PAN.sub(make("PAN"), text)
    return text, mapping


def unmask(value, mapping: dict[str, str]):
    if not isinstance(value, str):
        return value
    for token, original in mapping.items():
        value = value.replace(token, original)
    return value
