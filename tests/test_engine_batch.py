import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from precedent_summarizer.config import Settings
from precedent_summarizer.engine import batch as B
from precedent_summarizer.engine.costs import actual_cost, est_cost
from precedent_summarizer.engine.variants import build_user_message
from precedent_summarizer.engine.summarize import CaseInput

DB_SQL = Path(B.__file__).resolve().parents[1] / "schemas" / "db.sql"
TEXT = "【주    문】\n상고를 기각한다.\n【이    유】\n" + "원심은 피고의 주장을 배척하였다. " * 20
SECTIONS = json.dumps([{"header": "주    문", "header_norm": "주문", "start": 0, "end": TEXT.index("【이")}])


def settings(tmp):
    return Settings(anthropic_api_key="fake-a" + "0" * 10, law_api_key="fake-o" + "0" * 10,
                    db_path=tmp / "t.sqlite", raw_cache_dir=tmp / "raw")


def make_db(tmp, rows):
    conn = sqlite3.connect(tmp / "t.sqlite")
    conn.executescript(DB_SQL.read_text(encoding="utf-8"))
    for r in rows:
        base = dict(prec_id=r["id"], case_no="2025다1", decision_date=r.get("date"), date_status="ok",
                    data_source="대법원", detail_status=r.get("status", "ok"), full_text_clean=r.get("text", TEXT),
                    official_summary_clean=r.get("off"), sections_json=SECTIONS, list_file="x", loaded_at="t")
        if "dismissal" in r:
            base["is_summary_dismissal"] = r["dismissal"]
        conn.execute(f"INSERT INTO precedents ({','.join(base)}) VALUES ({','.join('?' * len(base))})", tuple(base.values()))
    conn.commit(); conn.close()
    return B.connect(tmp / "t.sqlite")


def good_summary():
    return {"one_line": "x", "case_type": "민사", "issues": [{"id": "I1", "question": "q"}],
            "facts": {"summary": "s", "evidence": ["원심은 피고의 주장을 배척하였다."]}, "lower_court": None,
            "rulings": [{"issue_id": "I1", "conclusion": "c", "reasoning": "r", "evidence": ["원심은 피고의 주장을 배척하였다."]}],
            "disposition": {"type": "상고기각", "text": "t", "evidence": ["상고를 기각한다."]},
            "cited_statutes": [], "cited_precedents": [], "separate_opinions": [], "not_in_text": []}


class FakeBatches:
    def __init__(self):
        self.created, self.n = [], 0

    def create(self, requests):
        self.n += 1; self.created.append(requests); return NS(id=f"msgbatch_{self.n}")

    def retrieve(self, bid):
        return NS(processing_status="ended")

    def results(self, bid):
        reqs = self.created[int(bid.split("_")[1]) - 1]
        for q in reqs:
            bad = q["custom_id"].startswith("2-")
            s = good_summary()
            if bad:
                s["facts"]["evidence"] = ["원문에 없는 문장입니다만"]
            yield NS(custom_id=q["custom_id"], result=NS(type="succeeded", message=NS(
                stop_reason="end_turn", content=[NS(type="text", text=json.dumps(s, ensure_ascii=False))],
                usage=NS(input_tokens=1000, output_tokens=2000, cache_read_input_tokens=0, cache_creation_input_tokens=0))))


def client():
    return NS(messages=NS(batches=FakeBatches()))


def test_selection_order_and_filters(tmp_path):
    conn = make_db(tmp_path, [dict(id="1", date="2024-01-01"), dict(id="2", date="2026-01-01"),
                              dict(id="3", date=None), dict(id="4", date="2025-05-05", status="unavailable"),
                              dict(id="5", date="2025-01-01", text="짧다"), dict(id="6", date="2025-02-02", dismissal=1)])
    ids = [r["prec_id"] for r in B.candidates(conn, "blind")]
    assert ids == ["2", "1", "3"]  # 최신순, 날짜 없음 맨 뒤, 미제공·단문·심리불속행 제외


def test_official_variant_only_with_official_text(tmp_path):
    conn = make_db(tmp_path, [dict(id="1", date="2025-01-01", off="법원 요지"), dict(id="2", date="2025-01-02")])
    assert [r["prec_id"] for r in B.candidates(conn, "official")] == ["1"]


def test_routing_long_and_en_banc(tmp_path):
    s = settings(tmp_path)
    assert B.route_model(s, TEXT) == s.model_default
    assert B.route_model(s, "가" * 15001) == s.model_complex
    assert B.route_model(s, "다수의견 ... 반대의견") == s.model_complex


def test_budget_cuts_plan(tmp_path):
    conn = make_db(tmp_path, [dict(id=str(i), date=f"2025-01-{i:02d}") for i in range(1, 11)])
    s = settings(tmp_path)
    one = est_cost(s.model_default, len(TEXT))
    p = B.plan(conn, s, "blind", budget=one * 3.5, max_n=None)
    assert p["n"] == 3 and p["est_cost"] <= one * 3.5


def test_submit_collect_verify_and_retry(tmp_path):
    conn = make_db(tmp_path, [dict(id="1", date="2025-01-01"), dict(id="2", date="2025-01-02")])
    s = settings(tmp_path); c = client()
    p = B.plan(conn, s, "blind", budget=10, max_n=None)
    B.submit(conn, c, p)
    assert B.plan(conn, s, "blind", budget=10, max_n=None)["n"] == 0  # 미수거 배치 중복 제출 방지
    rep = B.collect(conn, c, s)[0]
    assert rep["passed"] == 1 and rep["failed_verify"] == 1
    saved = [r[0] for r in conn.execute("SELECT prec_id FROM summaries WHERE version='v1'")]
    assert saved == ["1"]  # 검증 통과분만 저장
    spent, pending = B.spent_and_pending(conn)
    assert pending == 0 and spent == pytest.approx(2 * actual_cost(s.model_default, {"input_tokens": 1000, "output_tokens": 2000}))
    r = B.retry_plan(conn, s, "blind", budget=10)
    assert r["n"] == 1 and r["_items"][0][1] == s.model_complex
    B.submit(conn, c, r, attempt=2)
    assert B.retry_plan(conn, s, "blind", budget=10)["n"] == 0  # 재시도는 1회만


def test_custom_id_format():
    cid = B.custom_id("619499", "official", "claude-opus-5-5", 2)
    assert cid == "619499-o-o-2" and B.parse_custom_id(cid) == ("619499", "official", 2)


def test_official_message_contains_reference_only_when_present():
    c = CaseInput("1", "a", "b", "c", "d", "e", TEXT)
    assert "<판결요지>" in build_user_message(c, "official", None, "요지")
    assert "<판결요지>" not in build_user_message(c, "blind", None, "요지")
    assert "<판결요지>" not in build_user_message(c, "official", None, None)
