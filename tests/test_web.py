import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from precedent_summarizer.web.app import create_app, fts_query
from precedent_summarizer.web.highlight import evidence_spans, find_span

ROOT = Path(__file__).resolve().parents[1] / "src" / "precedent_summarizer" / "schemas"
TEXT = "【주    문】\n상고를  기각한다.\n【이    유】\n원심은 피고의\n주장을 배척하였다."


def make_db(tmp):
    p = tmp / "w.sqlite"
    c = sqlite3.connect(p)
    c.executescript((ROOT / "db.sql").read_text(encoding="utf-8"))
    rows = [("1", "2025다1", "손해배상청구", "2025-03-01", None, "ok", TEXT),
            ("2", "2024두2", "요양불승인처분취소", None, "2024-05-05", "ok", TEXT),
            ("3", "2023누3", "법인세부과처분취소", "2023-01-01", None, "unavailable", None)]
    for pid, no, name, d, inf, st, t in rows:
        c.execute("INSERT INTO precedents(prec_id,case_no,case_name,decision_date,decision_date_inferred,date_status,"
                  "data_source,detail_status,full_text_clean,sections_json,list_file,loaded_at,case_type_name) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (pid, no, name, d, inf, "ok" if d else "placeholder", "대법원", st, t, "[]", "x", "t", "민사"))
    s = {"one_line": "요약", "facts": {"summary": "s", "evidence": ["원심은 피고의 주장을 배척하였다."]},
         "disposition": {"type": "상고기각", "text": "t", "evidence": ["상고를 기각한다."]}, "rulings": []}
    c.execute("INSERT INTO summaries VALUES (?,?,?,?,?,?,?,?,?)",
              ("1", "v1", "claude-sonnet-5-5", json.dumps(s, ensure_ascii=False), "{}", 1, 1, 1, "t"))
    c.execute("INSERT INTO precedents_fts(precedents_fts) VALUES('rebuild')")
    c.commit(); c.close()
    return p


def test_find_span_whitespace_mapping():
    a, b = find_span(TEXT, "원심은 피고의 주장을 배척하였다.")
    assert TEXT[a:b] == "원심은 피고의\n주장을 배척하였다."
    assert find_span(TEXT, "없는 문장") is None


def test_evidence_spans_paths():
    sp = evidence_spans({"facts": {"evidence": ["상고를 기각한다."]}}, TEXT)
    assert sp[0]["path"] == "facts.evidence[0]" and TEXT[sp[0]["start"]:sp[0]["end"]] == "상고를  기각한다."


def test_fts_query_quotes_tokens():
    assert fts_query('손해배상 "x" OR') is None  # 3자 미만 토큰 포함 → LIKE 폴백
    assert fts_query("손해배상 불법행위") == '"손해배상" AND "불법행위"'


def test_api_list_order_filters_and_summary(tmp_path):
    cl = TestClient(create_app(make_db(tmp_path)))
    r = cl.get("/api/precedents").json()
    assert [x["prec_id"] for x in r["items"]] == ["1", "2", "3"] and r["items"][0]["one_line"] == "요약"
    assert r["items"][0]["summary_versions"] == "v1" and r["items"][1]["summary_versions"] is None
    assert [x["prec_id"] for x in cl.get("/api/precedents", params={"has_summary": "true"}).json()["items"]] == ["1"]
    assert [x["prec_id"] for x in cl.get("/api/precedents", params={"year_from": 2024, "year_to": 2024}).json()["items"]] == ["2"]
    assert cl.get("/api/precedents", params={"q": "요양불승인"}).json()["total"] == 1
    assert cl.get("/api/precedents", params={"q": "손해"}).json()["total"] == 1  # LIKE 폴백


def test_api_detail_and_summary_spans(tmp_path):
    cl = TestClient(create_app(make_db(tmp_path)))
    d = cl.get("/api/precedents/1").json()
    assert d["summaries"][0]["version"] == "v1" and "full_text_clean" in d
    s = cl.get("/api/precedents/1/summary/v1").json()
    assert all(x["start"] is not None for x in s["evidence_spans"])
    assert cl.get("/api/precedents/1/summary/v9").status_code == 404
    assert cl.get("/api/precedents/abc").status_code == 404
    assert cl.get("/api/stats").json()["summaries"][0]["n"] == 1


def test_db_opened_read_only(tmp_path):
    p = make_db(tmp_path)
    from precedent_summarizer.web.app import connect
    c = connect(p)
    try:
        c.execute("DELETE FROM precedents")
        raise AssertionError("write should fail")
    except sqlite3.OperationalError:
        pass
