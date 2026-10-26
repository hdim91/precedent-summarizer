import json
import re
import sqlite3
from pathlib import Path

from precedent_summarizer.export.static_site import export

SQL = Path(__file__).resolve().parents[1] / "src" / "precedent_summarizer" / "schemas" / "db.sql"
TEXT = "【주    문】\n상고를 기각한다.\n【이    유】\n원심은 피고의 주장을 배척하였다.</script><b>"


def make_db(tmp):
    p = tmp / "x.sqlite"; c = sqlite3.connect(p); c.executescript(SQL.read_text(encoding="utf-8"))
    for pid, d in (("1", "2026-01-01"), ("2", "2025-01-01"), ("3", "2024-01-01")):
        c.execute("INSERT INTO precedents(prec_id,case_no,case_name,decision_date,date_status,data_source,detail_status,"
                  "full_text_clean,sections_json,list_file,loaded_at,case_type_name) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (pid, f"2025다{pid}", f"사건{pid}", d, "ok", "대법원", "ok", TEXT, "[]", "x", "t", "민사"))
    s = {"one_line": "요약", "facts": {"summary": "s", "evidence": ["원심은 피고의 주장을 배척하였다."]}}
    c.execute("INSERT INTO summaries VALUES ('1','v1o','claude-sonnet-5-5',?,?,1,1,1,'t')", (json.dumps(s, ensure_ascii=False), "{}"))
    c.execute("INSERT INTO summaries VALUES ('2','v1','claude-opus-5-5',?,?,1,1,1,'t')", (json.dumps(s, ensure_ascii=False), "{}"))
    c.execute("INSERT INTO summaries VALUES ('3','v1o','claude-sonnet-5-5',?,?,0,1,1,'t')", (json.dumps(s, ensure_ascii=False), "{}"))
    c.commit(); c.close(); return p


def test_export_structure_and_safety(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "zzsecretvalue123456")
    r = export(make_db(tmp_path), tmp_path / "site", make_zip=True)
    out = tmp_path / "site"
    assert r["cases"] == 2 and r["secret_scan_hits"] == 0 and Path(r["zip"]).exists()  # 검증 미통과(3)는 제외
    assert sorted(p.name for p in (out / "cases").iterdir()) == ["1.html", "2.html"]
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'static/index-data.js' in idx and idx.index("static_shim.js") < idx.index("static/app.js")
    assert 'href="/"' not in idx
    case = (out / "cases" / "1.html").read_text(encoding="utf-8")
    assert "window.__PS_CASE__" in case and "../static/app.js" in case
    m = re.search(r"window\.__PS_CASE__=(.*?);</script>", case, re.S)
    assert "</script><b>" not in m.group(1)  # 원문 속 </script>가 이스케이프됨
    data = json.loads(m.group(1).replace("<\\/", "</"))
    assert data["summaries"]["v1o"]["evidence_spans"][0]["start"] is not None
    csv_text = (out / "평가표_판례검토.csv").read_text(encoding="utf-8-sig")
    assert csv_text.splitlines()[1].startswith("1,2025다1,2026-01-01")
