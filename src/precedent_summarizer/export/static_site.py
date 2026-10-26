"""요약된 판례 전체를 서버 없이 열리는 정적 웹사이트로 내보낸다 (Claude 소유, 2026-10-27).

- 화면은 web/templates·web/static(app.css, app.js)을 그대로 재사용하고, export/assets/static_shim.js가
  /api 호출·절대경로 링크·pushState를 브라우저 안에서 대신 처리한다(app.js 무수정).
- 대상: v1o 또는 v1 요약이 하나라도 있는 판례. 데이터는 페이지에 내장(<script>)되어 file:// 에서도 동작.
- 함께 생성: 검토 평가표(CSV, Excel용 UTF-8 BOM), 사용 안내(README.html), 선택 시 ZIP.
- DB 읽기 전용, PC에서 실행(D-022). 생성 후 키 노출 검사(마스킹되지 않은 OC 파라미터·환경변수 비밀값) 결과 출력.

사용: python -m precedent_summarizer.export.static_site [--out data/export/site] [--zip]
"""
from __future__ import annotations

import argparse, csv, json, re, shutil, sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from precedent_summarizer.common.security import _env_secrets
from precedent_summarizer.config import get_settings
from precedent_summarizer.web.highlight import evidence_spans

KST = timezone(timedelta(hours=9))
PKG = Path(__file__).resolve().parents[1]
WEB = PKG / "web"
SHIM = Path(__file__).resolve().parent / "assets" / "static_shim.js"
DETAIL_KEYS = ("prec_id", "case_no", "case_name", "decision_date", "decision_date_inferred", "date_status",
               "court_name", "case_type_name", "judgment_type", "data_source", "detail_status", "holdings_clean",
               "official_summary_clean", "ref_statutes_clean", "ref_precedents_clean", "full_text_clean",
               "has_order_section", "is_summary_dismissal", "case_year")


def _js(obj) -> str:
    """<script> 안에 안전하게 넣을 JSON 리터럴."""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _env(root: str) -> Environment:
    env = Environment(loader=FileSystemLoader(str(WEB / "templates")), autoescape=True)
    env.globals["url_for"] = lambda name, path="": f"{root}static/{path}"
    return env


def _inject(html: str, root: str, data_js: str) -> str:
    """shim·데이터를 app.js 앞에 삽입하고, 템플릿의 절대경로 '/' 링크를 상대경로로."""
    tag = f'<script>window.__PS_ROOT__={_js(root)};{data_js}</script><script defer src="{root}static/static_shim.js"></script>'
    app = f'<script defer src="{root}static/app.js"></script>'
    assert html.count(app) == 1, "app.js 로딩 태그를 찾지 못함"
    html = html.replace(app, tag + app)
    return html.replace('href="/"', f'href="{root}index.html"')


def collect(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    ids = [r[0] for r in conn.execute("SELECT DISTINCT prec_id FROM summaries WHERE verify_passed=1")]
    index, cases = [], {}
    for pid in ids:
        p = conn.execute("SELECT * FROM precedents WHERE prec_id=?", (pid,)).fetchone()
        if p is None:
            continue
        detail = {k: p[k] for k in DETAIL_KEYS if k in p.keys()}
        detail["sections"] = json.loads(p["sections_json"] or "[]")
        sums = conn.execute("SELECT * FROM summaries WHERE prec_id=? AND verify_passed=1 ORDER BY version", (pid,)).fetchall()
        detail["summaries"] = [{"version": s["version"], "model": s["model"], "verify_passed": 1,
                                "created_at": s["created_at"]} for s in sums]
        summaries, idx_s = {}, {}
        for s in sums:
            sm = json.loads(s["summary_json"])
            summaries[s["version"]] = {"prec_id": pid, "version": s["version"], "model": s["model"],
                                       "created_at": s["created_at"], "summary": sm,
                                       "verify": json.loads(s["verify_json"]),
                                       "evidence_spans": evidence_spans(sm, p["full_text_clean"] or "")}
            idx_s[s["version"]] = {"model": s["model"], "one_line": sm.get("one_line")}
        cases[pid] = {"detail": detail, "summaries": summaries}
        index.append({k: p[k] for k in ("prec_id", "case_no", "case_name", "decision_date", "decision_date_inferred",
                                         "case_type_name", "data_source", "detail_status")} | {"summaries": idx_s})
    return index, cases


def stats_of(index) -> dict:
    by_vm = Counter((v, s["model"]) for it in index for v, s in it["summaries"].items())
    return {"precedents": dict(Counter(it["detail_status"] for it in index)),
            "by_source": dict(Counter(it["data_source"] for it in index)),
            "summaries": [{"version": v, "model": m, "n": n} for (v, m), n in sorted(by_vm.items())]}


def scan_secrets(out: Path) -> int:
    secrets = [x.encode() for x in _env_secrets()]
    pat = re.compile(rb"(?i)[?&](?:OC|KEY|serviceKey)=(?!\*\*\*)[A-Za-z0-9_-]{3,}")
    n = 0
    for f in out.rglob("*"):
        if f.is_file():
            b = f.read_bytes()
            n += len(pat.findall(b)) + sum(b.count(s) for s in secrets)
    return n


def export(db_path: Path, out: Path, *, make_zip: bool = False) -> dict:
    conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    index, cases = collect(conn)
    if out.exists():
        shutil.rmtree(out)
    (out / "static").mkdir(parents=True); (out / "cases").mkdir()
    for f in ("app.css", "app.js"):
        shutil.copy2(WEB / "static" / f, out / "static" / f)
    shutil.copy2(SHIM, out / "static" / "static_shim.js")
    (out / "static" / "index-data.js").write_text(
        f"window.__PS_INDEX__={_js(index)};window.__PS_STATS__={_js(stats_of(index))};", encoding="utf-8")
    # 목록 페이지(데이터는 index-data.js를 별도 로드)
    html = _env("").get_template("index.html").render(request=None)
    html = _inject(html, "", "") .replace('<script defer src="static/static_shim.js"></script>',
                                          '<script src="static/index-data.js"></script><script defer src="static/static_shim.js"></script>')
    (out / "index.html").write_text(html, encoding="utf-8")
    det_t = _env("../").get_template("detail.html")
    for pid, c in cases.items():
        h = det_t.render(request=None, prec_id=pid)
        h = _inject(h, "../", f"window.__PS_CASE__={_js(c)};")
        (out / "cases" / f"{pid}.html").write_text(h, encoding="utf-8")
    # 평가표
    with (out / "평가표_판례검토.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["판례일련번호", "사건번호", "선고일", "사건종류", "사건명", "요약 버전·모델", "파일",
                    "결론 정확(O/X)", "쟁점 누락(없음/일부/중대)", "판단 왜곡(O/X)", "원심·대법원 혼동(O/X)",
                    "소수의견 처리(적절/부적절/해당없음)", "전반 점수(1~5)", "의견"])
        for it in sorted(index, key=lambda x: (x["decision_date"] or x["decision_date_inferred"] or ""), reverse=True):
            vm = ", ".join(f"{v}:{s['model'].replace('claude-', '')}" for v, s in sorted(it["summaries"].items(), reverse=True))
            w.writerow([it["prec_id"], it["case_no"], it["decision_date"] or it["decision_date_inferred"] or "",
                        it["case_type_name"], it["case_name"], vm, f"cases/{it['prec_id']}.html"] + [""] * 7)
    gen = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    (out / "README.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>사용 안내</title>
<body style="font-family:sans-serif;max-width:720px;margin:40px auto;line-height:1.7">
<h1>대법원 판례 자동 요약 — 검토용 사본</h1><p>생성: {gen} · 수록: 요약된 판례 {len(index):,}건</p>
<ol><li><b>index.html</b>을 더블클릭하면 목록이 열립니다(인터넷 연결 없이 동작, 글꼴만 온라인일 때 적용).</li>
<li>목록 검색은 사건명·사건번호·한 줄 요약 기준입니다(판결문 전문 검색은 이 사본에서 지원하지 않음).</li>
<li>상세 화면 왼쪽 요약의 <b>근거 번호</b>를 누르면 오른쪽 판결 원문의 해당 문장이 강조됩니다.</li>
<li>검토 의견: <b>평가표_판례검토.csv</b>(엑셀)에서 검토한 판례 행에 기입하거나, 상세 화면의 <b>‘검토 의견 양식 복사’</b> 버튼으로 양식을 복사해 메일·메신저로 보내 주세요.</li></ol>
<p>요약 버전: v1o(판결요지 참고, 기본) / v1(블라인드, 일부 비교용). 모든 요약은 원문 인용 검증을 통과한 것만 수록했습니다.
<br><b>연구용 자동 요약 — 법률 자문이 아니며, 반드시 원문을 확인하세요.</b></p></body>""", encoding="utf-8")
    leaks = scan_secrets(out)
    result = {"out": str(out), "cases": len(cases), "index": len(index), "secret_scan_hits": leaks}
    if make_zip:
        result["zip"] = shutil.make_archive(str(out), "zip", root_dir=out)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out"); ap.add_argument("--zip", action="store_true")
    a = ap.parse_args()
    s = get_settings()
    out = Path(a.out) if a.out else s.raw_cache_dir.parent / "export" / "site"
    print(json.dumps(export(s.db_path, out, make_zip=a.zip), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
