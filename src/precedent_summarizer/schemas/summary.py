"""요약 출력 계약 v1 (Claude 소유, 2026-10-23).

- Messages API 구조화 출력(`output_config.format = json_schema`)으로 이 스키마를 강제한다.
  (2026-10-23: 대상 모델이 강제 tool_choice를 지원하지 않아 전환. 구조화 출력은 문자열 길이·배열 최대 개수 제약을
   지원하지 않으므로 그런 제약은 description에 쓰고 검증기에서 확인한다.)
- 모든 서술 항목은 `evidence`(판례내용 원문에서 그대로 옮긴 문장)를 1~3개 가진다 → engine/verify.py가 대조.
"""
from __future__ import annotations

SUMMARY_VERSION = "v1"

DISPOSITION_TYPES = [
    "상고기각", "파기환송", "파기이송", "파기자판", "일부파기환송",
    "상고각하", "재항고기각", "재항고인용", "항고기각", "기타",
]
OPINION_KINDS = ["반대의견", "별개의견", "보충의견"]

_EVIDENCE = {
    "type": "array",
    "minItems": 1,
    "items": {"type": "string"},
    "description": "1~3개. 판례내용에서 글자 그대로 복사한 연속된 구절(각 8~300자). 요약·의역 금지.",
}


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


SUMMARY_SCHEMA: dict = _obj(
    {
        "one_line": {"type": "string", "description": "사건과 결론을 한 문장으로(80자 내외)."},
        "case_type": {"type": "string", "description": "민사/형사/행정/가사/특허/조세 등."},
        "issues": {
            "type": "array", "minItems": 1,
            "items": _obj({"id": {"type": "string", "description": "I1, I2 ..."},
                           "question": {"type": "string"}}, ["id", "question"]),
        },
        "facts": _obj({"summary": {"type": "string"}, "evidence": _EVIDENCE}, ["summary", "evidence"]),
        "lower_court": {
            "anyOf": [
                _obj({"summary": {"type": "string"}, "evidence": _EVIDENCE}, ["summary", "evidence"]),
                {"type": "null"},
            ],
            "description": "원심 판단. 판례내용에 원심 판단 서술이 없으면 null.",
        },
        "rulings": {
            "type": "array", "minItems": 1,
            "items": _obj({"issue_id": {"type": "string"},
                           "conclusion": {"type": "string"},
                           "reasoning": {"type": "string"},
                           "evidence": _EVIDENCE},
                          ["issue_id", "conclusion", "reasoning", "evidence"]),
        },
        "disposition": _obj({"type": {"type": "string", "enum": DISPOSITION_TYPES},
                             "text": {"type": "string"},
                             "evidence": _EVIDENCE}, ["type", "text", "evidence"]),
        "cited_statutes": {
            "type": "array",
            "items": _obj({"statute": {"type": "string", "description": "예: 민법 제750조"},
                           "evidence": _EVIDENCE}, ["statute", "evidence"]),
        },
        "cited_precedents": {
            "type": "array",
            "items": _obj({"case_no": {"type": "string", "description": "예: 대법원 2010. 1. 28. 선고 2009다12345 판결"},
                           "evidence": _EVIDENCE}, ["case_no", "evidence"]),
        },
        "separate_opinions": {
            "type": "array",
            "items": _obj({"kind": {"type": "string", "enum": OPINION_KINDS},
                           "summary": {"type": "string"},
                           "evidence": _EVIDENCE}, ["kind", "summary", "evidence"]),
        },
        "not_in_text": {
            "type": "array", "items": {"type": "string"},
            "description": "요약에 필요하지만 판례내용에 나오지 않아 쓰지 않은 정보(예: '구체적 사실관계 미기재').",
        },
    },
    ["one_line", "case_type", "issues", "facts", "lower_court", "rulings", "disposition",
     "cited_statutes", "cited_precedents", "separate_opinions", "not_in_text"],
)

OUTPUT_CONFIG: dict = {"format": {"type": "json_schema", "schema": SUMMARY_SCHEMA}}

# 스키마 밖 제약(검증기에서 확인)
EVIDENCE_MIN_LEN, EVIDENCE_MAX_LEN, EVIDENCE_MAX_ITEMS = 8, 300, 3
