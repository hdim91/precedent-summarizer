"""판례 데이터 계약(Claude 소유 — Codex는 변경 금지, 변경 필요 시 TASK 명세 '질문'란).

필드 매핑은 2026-10-23 law.go.kr 실측 응답 기준.
  목록(PrecSearch.prec[]): id, 사건번호, 데이터출처명, 사건종류코드, 사건종류명, 선고, 선고일자,
                           판례일련번호, 판결유형, 법원종류코드, 법원명, 판례상세링크, 사건명
  상세(PrecService):       판례정보일련번호, 사건번호, 사건명, 선고일자, 선고, 법원명, 법원종류코드,
                           사건종류명, 사건종류코드, 판결유형, 판시사항, 판결요지, 참조조문, 참조판례, 판례내용
정규화 원칙(RULES 5장): 빈 문자열/공백은 None으로 바꾸되 추정·보완하지 않는다. 원문 텍스트는 손대지 않고
태그 제거본은 별도 필드로 둔다(P2에서 결정).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

LIST_FIELD_MAP: dict[str, str] = {
    "판례일련번호": "prec_id",
    "사건번호": "case_no",
    "사건명": "case_name",
    "선고일자": "decision_date",      # 원본 'YYYY.MM.DD' 또는 'YYYYMMDD' → 'YYYY-MM-DD'로 정규화
    "선고": "decision_kind",
    "법원명": "court_name",
    "법원종류코드": "court_type_code",
    "사건종류명": "case_type_name",
    "사건종류코드": "case_type_code",
    "판결유형": "judgment_type",
    "데이터출처명": "data_source",
}

DETAIL_FIELD_MAP: dict[str, str] = {
    "판례정보일련번호": "prec_id",
    "사건번호": "case_no",
    "사건명": "case_name",
    "선고일자": "decision_date",
    "선고": "decision_kind",
    "법원명": "court_name",
    "법원종류코드": "court_type_code",
    "사건종류명": "case_type_name",
    "사건종류코드": "case_type_code",
    "판결유형": "judgment_type",
    "판시사항": "holdings",
    "판결요지": "official_summary",
    "참조조문": "ref_statutes",
    "참조판례": "ref_precedents",
    "판례내용": "full_text",
}


@dataclass
class PrecedentListItem:
    prec_id: str
    case_no: Optional[str] = None
    case_name: Optional[str] = None
    decision_date: Optional[str] = None
    decision_kind: Optional[str] = None
    court_name: Optional[str] = None
    court_type_code: Optional[str] = None
    case_type_name: Optional[str] = None
    case_type_code: Optional[str] = None
    judgment_type: Optional[str] = None
    data_source: Optional[str] = None


@dataclass
class PrecedentDetail(PrecedentListItem):
    holdings: Optional[str] = None
    official_summary: Optional[str] = None
    ref_statutes: Optional[str] = None
    ref_precedents: Optional[str] = None
    full_text: Optional[str] = None
    missing_fields: list[str] = field(default_factory=list)  # 원본에서 비어 있던 필드명(정규화명)
