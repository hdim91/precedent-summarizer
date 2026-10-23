import pytest

from precedent_summarizer.engine.summarize import CaseInput, SummaryParseError, parse_output, request_params, user_message
from precedent_summarizer.engine.verify import check_disposition, statute_keys, verify

TEXT = "【주    문】\n상고를 기각한다.\n【이    유】\n원심은 피고의 주장을 배척하였다. 그러나 민법 제750조에 의하면 불법행위 책임이 인정된다."
SECTIONS = [{"header": "【주    문】", "header_norm": "주문", "start": 0, "end": TEXT.index("【이")},
            {"header": "【이    유】", "header_norm": "이유", "start": TEXT.index("【이"), "end": len(TEXT)}]


def _summary(**over):
    s = {"one_line": "x", "case_type": "민사", "issues": [{"id": "I1", "question": "q"}],
         "facts": {"summary": "s", "evidence": ["원심은 피고의 주장을 배척하였다."]},
         "lower_court": None,
         "rulings": [{"issue_id": "I1", "conclusion": "c", "reasoning": "r",
                      "evidence": ["민법 제750조에 의하면  불법행위 책임이"]}],
         "disposition": {"type": "상고기각", "text": "t", "evidence": ["상고를 기각한다."]},
         "cited_statutes": [{"statute": "민법 제750조", "evidence": ["민법 제750조에 의하면"]}],
         "cited_precedents": [], "separate_opinions": [], "not_in_text": []}
    s.update(over)
    return s


def test_pass_with_whitespace_normalization():
    r = verify(_summary(), full_text_clean=TEXT, sections=SECTIONS, ref_statutes_clean="민법 제750조")
    assert r.passed and r.evidence_found == r.evidence_total == 4
    assert r.disposition_check == "match" and r.statutes_overlap == 1


def test_fabricated_quote_fails():
    s = _summary(facts={"summary": "s", "evidence": ["원심은 원고의 주장을 받아들였다."]})
    r = verify(s, full_text_clean=TEXT, sections=SECTIONS)
    assert not r.passed and r.evidence_missing[0]["path"] == "facts.evidence[0]"


def test_disposition_mismatch_fails():
    s = _summary(disposition={"type": "파기환송", "text": "t", "evidence": ["상고를 기각한다."]})
    assert not verify(s, full_text_clean=TEXT, sections=SECTIONS).passed


def test_no_order_section_is_not_failure():
    r = verify(_summary(), full_text_clean=TEXT, sections=[])
    assert r.passed and r.disposition_check == "no_order_section"


def test_disposition_patterns():
    assert check_disposition("파기환송", "원심판결을 파기하고, 사건을 서울고등법원에 환송한다.") == "match"
    assert check_disposition("상고기각", "원심판결 중 일부를 파기하고 나머지 상고를 기각한다.") == "mismatch"


def test_statute_keys_carry_law_name():
    assert statute_keys("민법 제750조, 제751조 / 형법 제30조의2") == {"민법750", "민법751", "형법30의2"}


def test_statute_keys_old_law_parenthetical_and_beopryul():
    ref = ("[1] 구 산업재해보상보험법(2010. 5. 20. 법률 제10305호로 개정되기 전의 것) 제36조 제3항, "
           "구 진폐의 예방과 진폐근로자의 보호 등에 관한 법률(2010. 5. 20. 법률 제10304호로 개정되기 전의 것) 제1조, "
           "제24조 제1항 제2호 / [2] 행정소송법 제27조[행정소송재판일반]")
    k = statute_keys(ref)
    assert {"산업재해보상보험법36", "진폐의예방과진폐근로자의보호등에관한법률1",
            "진폐의예방과진폐근로자의보호등에관한법률24", "행정소송법27"} <= k
    assert statute_keys("구 진폐의 예방과 진폐근로자의 보호 등에 관한 법률 제24조 제1항 제2호") == {
        "진폐의예방과진폐근로자의보호등에관한법률24"}


def test_request_params_shape():
    c = CaseInput("1", "2020다1", "손해배상", "2020-01-01", "대법원", "민사", TEXT)
    p = request_params(c, "m")
    assert p["output_config"]["format"]["type"] == "json_schema" and p["system"][0]["cache_control"]
    assert "tools" not in p and "tool_choice" not in p
    assert "<판례내용>" in user_message(c)


def test_parse_output_dict():
    msg = {"stop_reason": "end_turn", "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": '{"a": 1}'}]}
    assert parse_output(msg) == {"a": 1}


def test_parse_output_truncated_raises():
    with pytest.raises(SummaryParseError):
        parse_output({"stop_reason": "max_tokens", "content": [{"type": "text", "text": '{"a"'}]})


def test_schema_has_no_unsupported_constraints():
    import json as _j
    from precedent_summarizer.schemas.summary import SUMMARY_SCHEMA
    s = _j.dumps(SUMMARY_SCHEMA)
    assert "maxItems" not in s and "minLength" not in s and "maxLength" not in s
