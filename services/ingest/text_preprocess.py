from __future__ import annotations

import re


def clean_for_embedding(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
