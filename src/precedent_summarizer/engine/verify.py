"""요약 근거 검증기 v1 (Claude 소유).

검사 항목
1. evidence 원문 대조(필수): 공백 정규화 후 `full_text_clean`의 부분 문자열인지.
2. 결론 ↔ 【주문】 대조(필수, 주문 구획이 있을 때만): 결론 유형과 주문 문구의 핵심 표현 일치.
3. 인용 조문 ↔ 참조조문(참고, 실패 사유 아님): 참조조문이 비어 있으면 skip.
통과 기준: 1의 불일치 0건 AND 2가 mismatch가 아님.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from precedent_summarizer.schemas.summary import EVIDENCE_MAX_ITEMS, EVIDENCE_MAX_LEN, EVIDENCE_MIN_LEN

_WS = re.compile(r"\s+")


def norm_ws(s: str) -> str:
    return _WS.sub(" ", s or "").strip()


def iter_evidence(summary: dict) -> list[tuple[str, str]]:
    """(경로, 인용문) 목록."""
    out: list[tuple[str, str]] = []

    def add(path: str, obj: Optional[dict]) -> None:
        if obj:
            for i, q in enumerate(obj.get("evidence") or []):
                out.append((f"{path}.evidence[{i}]", q))

    add("facts", summary.get("facts"))
    add("lower_court", summary.get("lower_court"))
    add("disposition", summary.get("disposition"))
    for key in ("rulings", "cited_statutes", "cited_precedents", "separate_opinions"):
        for i, item in enumerate(summary.get(key) or []):
            add(f"{key}[{i}]", item)
    return out


# 결론 유형별 주문 핵심 표현(하나라도 있으면 일치). 정규화(공백 제거) 문자열 기준.
_DISPOSITION_PATTERNS: dict[str, list[str]] = {
    "상고기각": ["상고를기각", "상고를모두기각", "상고는기각", "각상고를기각", "상고를각기각"],
    "상고각하": ["상고를각하", "상고를모두각하", "상고는각하"],
    "재항고기각": ["재항고를기각", "재항고를모두기각", "재항고는기각", "재항고를각기각"],
    "항고기각": ["항고를기각", "항고를모두기각", "항고는기각"],
    "파기환송": ["파기", "환송"],
    "일부파기환송": ["파기", "환송"],
    "파기이송": ["파기", "이송"],
    "파기자판": ["파기"],
}
_ALL_OF = {"파기환송", "일부파기환송", "파기이송"}  # 모든 표현이 있어야 함


def _order_text(full_text_clean: str, sections: list[dict]) -> Optional[str]:
    for s in sections or []:
        if s.get("header_norm") == "주문":
            return full_text_clean[s["start"]:s["end"]]
    return None


def check_disposition(dtype: str, order_text: Optional[str]) -> str:
    if order_text is None:
        return "no_order_section"
    pats = _DISPOSITION_PATTERNS.get(dtype)
    if not pats:
        return "unknown_type"
    t = re.sub(r"\s+", "", order_text)
    ok = all(p in t for p in pats) if dtype in _ALL_OF else any(p in t for p in pats)
    if dtype == "상고기각" and ("파기" in t or "재항고" in t):
        ok = False  # 일부 파기가 섞이거나 재항고 사건이면 단순 상고기각 아님
    return "match" if ok else "mismatch"


_LAW_NAME = r"[가-힣A-Za-z0-9·ㆍ\s]+?(?:법률|법|령|규칙|규정)(?:\s*시행령|\s*시행규칙)?"
_STATUTE = re.compile(r"(" + _LAW_NAME + r")\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")


def _prep_statutes(text: str) -> str:
    t = re.sub(r"\([^()]*\)", "", text or "")      # (2010. 5. 20. 법률 제10305호로 개정되기 전의 것) 등 제거
    t = re.sub(r"\[[^\]]*\]", ",", t)              # [1] 구분자, [행정소송재판일반] 분류 꼬리표
    t = re.sub(r"(^|[,/\n])\s*구\s+", r"\1", t)     # 구법 표시 '구 ' 제거(현행·구법 동일 키로 비교)
    return t


def statute_keys(text: str) -> set[str]:
    keys = set()
    last_law = None
    for part in re.split(r"[,/\n]", _prep_statutes(text)):
        m = _STATUTE.search(part)
        if m:
            last_law = re.sub(r"\s+", "", m.group(1))
            keys.add(f"{last_law}{m.group(2)}" + (f"의{m.group(3)}" if m.group(3) else ""))
        elif last_law:
            m2 = re.search(r"제\s*(\d+)\s*조(?:의\s*(\d+))?", part)
            if m2:
                keys.add(f"{last_law}{m2.group(1)}" + (f"의{m2.group(2)}" if m2.group(2) else ""))
    return keys


@dataclass
class VerifyResult:
    passed: bool
    evidence_total: int
    evidence_found: int
    evidence_missing: list[dict] = field(default_factory=list)
    disposition_check: str = "skip"
    statutes_summary: int = 0
    statutes_ref: Optional[int] = None
    statutes_overlap: Optional[int] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify(summary: dict, *, full_text_clean: str, sections: list[dict],
           ref_statutes_clean: Optional[str] = None) -> VerifyResult:
    src = norm_ws(full_text_clean)
    ev = iter_evidence(summary)
    missing = [{"path": p, "quote": q[:80]} for p, q in ev if norm_ws(q) not in src]
    disp = check_disposition((summary.get("disposition") or {}).get("type", ""),
                             _order_text(full_text_clean, sections))
    s_keys = set()
    for it in summary.get("cited_statutes") or []:
        s_keys |= statute_keys(it.get("statute", ""))
    r = VerifyResult(
        passed=(not missing) and disp != "mismatch" and len(ev) > 0,
        evidence_total=len(ev), evidence_found=len(ev) - len(missing), evidence_missing=missing,
        disposition_check=disp, statutes_summary=len(s_keys),
    )
    if ref_statutes_clean:
        r_keys = statute_keys(ref_statutes_clean)
        r.statutes_ref, r.statutes_overlap = len(r_keys), len(r_keys & s_keys)
    if not ev:
        r.notes.append("evidence 없음")
    # 스키마 밖 제약(경고만, 통과 여부에는 영향 없음)
    bad_len = sum(1 for _, q in ev if not EVIDENCE_MIN_LEN <= len(q) <= EVIDENCE_MAX_LEN)
    if bad_len:
        r.notes.append(f"evidence 길이 범위({EVIDENCE_MIN_LEN}~{EVIDENCE_MAX_LEN}자) 밖 {bad_len}건")
    many = sum(1 for p, _ in ev if p.endswith(f"[{EVIDENCE_MAX_ITEMS}]"))
    if many:
        r.notes.append(f"evidence {EVIDENCE_MAX_ITEMS}개 초과 항목 {many}건")
    return r
