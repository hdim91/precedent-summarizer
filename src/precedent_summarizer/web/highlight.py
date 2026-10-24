"""요약 근거 문장 → 원문(full_text_clean) 위치 매핑 (Claude 소유).

검증기(engine/verify.py)는 공백을 정규화해 대조하므로, 화면 하이라이트도 같은 규칙으로 찾고
원문 오프셋으로 되돌린다. 반환 오프셋은 Python 문자열 인덱스(코드포인트) 기준.
"""
from __future__ import annotations

import re
from typing import Optional

from precedent_summarizer.engine.verify import iter_evidence

_WS = re.compile(r"\s+")


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """공백 연속을 한 칸으로 줄인 문자열과, 정규화 문자 i → 원문 인덱스 대응표."""
    out, idx = [], []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            if out:  # 앞쪽 공백은 버림(norm_ws의 strip과 동일)
                out.append(" "); idx.append(i)
            i = j
        else:
            out.append(text[i]); idx.append(i); i += 1
    if out and out[-1] == " ":
        out.pop(); idx.pop()
    return "".join(out), idx


def find_span(text: str, quote: str, _cache: Optional[dict] = None) -> Optional[tuple[int, int]]:
    norm, idx = (_cache["norm"], _cache["idx"]) if _cache else _normalize_with_map(text)
    q = _WS.sub(" ", quote or "").strip()
    if not q:
        return None
    k = norm.find(q)
    if k < 0:
        return None
    return idx[k], idx[k + len(q) - 1] + 1


def evidence_spans(summary: dict, text: str) -> list[dict]:
    norm, idx = _normalize_with_map(text)
    cache = {"norm": norm, "idx": idx}
    out = []
    for path, quote in iter_evidence(summary):
        span = find_span(text, quote, cache)
        out.append({"path": path, "quote": quote, "start": span[0] if span else None,
                    "end": span[1] if span else None})
    return out
