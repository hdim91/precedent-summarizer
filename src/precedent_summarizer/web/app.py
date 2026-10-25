"""내부용 웹 앱 (P5). API·조회 로직은 Claude 소유, 화면(templates/static)은 Codex(TASK-003).

실행(PC): uvicorn precedent_summarizer.web.app:app --host 127.0.0.1 --port 8000
- DB는 읽기 전용(mode=ro)으로만 연다. 쓰기는 적재·배치 명령의 몫(D-022).
- 외부 공개 금지: 127.0.0.1 바인딩 전제(INTENT: 내부 연구용).
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from precedent_summarizer.config import load_env
from precedent_summarizer.engine.variants import VARIANTS
from precedent_summarizer.web.highlight import evidence_spans

HERE = Path(__file__).resolve().parent
DATE_EXPR = "COALESCE(p.decision_date, p.decision_date_inferred)"


def _db_path() -> Path:
    import os
    from precedent_summarizer.config import PROJECT_ROOT
    load_env()
    v = os.environ.get("DB_PATH", "").strip()
    p = Path(v) if v else PROJECT_ROOT / "data" / "precedents.sqlite"
    return p if p.is_absolute() else PROJECT_ROOT / p


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or _db_path()
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _has_table(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone() is not None


def fts_query(q: str) -> Optional[str]:
    """사용자 입력 → 안전한 FTS5 질의(각 토큰을 따옴표로 감싸 AND). trigram이므로 3자 미만 토큰은 None 신호."""
    toks = [t for t in re.split(r"\s+", q.strip()) if t]
    if not toks or any(len(t) < 3 for t in toks):
        return None
    return " AND ".join('"' + t.replace('"', '""') + '"' for t in toks)


def create_app(db_path: Optional[Path] = None) -> FastAPI:
    app = FastAPI(title="대법원 판례 요약", docs_url="/api/docs", redoc_url=None)
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    if (HERE / "static").is_dir():
        app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    def db() -> sqlite3.Connection:
        return connect(db_path)

    @app.exception_handler(Exception)
    async def _err(request: Request, exc: Exception):  # 내부 정보(경로·설정·SQL) 비노출
        return JSONResponse({"error": "internal_error"}, status_code=500)

    # ------------------------------------------------------------ JSON API
    @app.get("/api/stats")
    def stats():
        c = db()
        out = {"precedents": dict(c.execute("SELECT detail_status, COUNT(*) FROM precedents GROUP BY 1").fetchall()),
               "by_source": dict(c.execute("SELECT data_source, COUNT(*) FROM precedents GROUP BY 1").fetchall()),
               "summaries": []}
        if _has_table(c, "summaries"):
            out["summaries"] = [dict(r) for r in c.execute(
                "SELECT version, model, COUNT(*) AS n FROM summaries GROUP BY 1, 2 ORDER BY 1, 2")]
        return out

    @app.get("/api/precedents")
    def list_precedents(q: str = "", year_from: Optional[int] = None, year_to: Optional[int] = None,
                        case_type: Optional[str] = None, data_source: Optional[str] = None,
                        has_summary: Optional[bool] = None, version: str = Query("v1", pattern=r"^v1o?$"),
                        page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
        c = db()
        where, params, join = ["1=1"], [], ""
        if q.strip():
            fq = fts_query(q)
            if fq:
                join = "JOIN precedents_fts f ON f.rowid = p.rowid"
                where.append("precedents_fts MATCH ?"); params.append(fq)
            else:  # 3자 미만 토큰 → 사건명·사건번호 LIKE
                where.append("(p.case_name LIKE ? OR p.case_no LIKE ?)"); params += [f"%{q.strip()}%"] * 2
        if year_from:
            where.append(f"{DATE_EXPR} >= ?"); params.append(f"{year_from:04d}-01-01")
        if year_to:
            where.append(f"{DATE_EXPR} <= ?"); params.append(f"{year_to:04d}-12-31")
        if case_type:
            where.append("p.case_type_name = ?"); params.append(case_type)
        if data_source:
            where.append("p.data_source = ?"); params.append(data_source)
        sum_join = ("LEFT JOIN summaries s ON s.prec_id = p.prec_id AND s.version = ?"
                    if _has_table(c, "summaries") else "")
        sum_cols = (", s.model AS summary_model, json_extract(s.summary_json, '$.one_line') AS one_line, "
                    "(SELECT group_concat(s2.version) FROM summaries s2 WHERE s2.prec_id = p.prec_id) AS summary_versions"
                    if sum_join else ", NULL AS summary_model, NULL AS one_line, NULL AS summary_versions")
        if has_summary is not None and sum_join:
            where.append("s.prec_id IS NOT NULL" if has_summary else "s.prec_id IS NULL")
        sql_from = f"FROM precedents p {join} {sum_join} WHERE {' AND '.join(where)}"
        all_params = ([version] if sum_join else []) + params
        total = c.execute(f"SELECT COUNT(*) {sql_from}", all_params).fetchone()[0]
        rows = c.execute(
            f"SELECT p.prec_id, p.case_no, p.case_name, p.decision_date, p.decision_date_inferred, p.case_type_name, "
            f"p.data_source, p.detail_status {sum_cols} {sql_from} "
            f"ORDER BY ({DATE_EXPR} IS NULL), {DATE_EXPR} DESC, CAST(p.prec_id AS INTEGER) DESC LIMIT ? OFFSET ?",
            all_params + [size, (page - 1) * size]).fetchall()
        return {"total": total, "page": page, "size": size, "items": [dict(r) for r in rows]}

    def _precedent(c, prec_id: str) -> sqlite3.Row:
        if not prec_id.isdigit():
            raise HTTPException(404)
        r = c.execute("SELECT * FROM precedents WHERE prec_id=?", (prec_id,)).fetchone()
        if r is None:
            raise HTTPException(404)
        return r

    @app.get("/api/precedents/{prec_id}")
    def get_precedent(prec_id: str):
        c = db()
        r = _precedent(c, prec_id)
        keep = ("prec_id", "case_no", "case_name", "decision_date", "decision_date_inferred", "date_status",
                "court_name", "case_type_name", "judgment_type", "data_source", "detail_status",
                "holdings_clean", "official_summary_clean", "ref_statutes_clean", "ref_precedents_clean",
                "full_text_clean", "has_order_section", "is_summary_dismissal", "case_year")
        out = {k: r[k] for k in keep if k in r.keys()}
        out["sections"] = json.loads(r["sections_json"] or "[]")
        out["summaries"] = [dict(x) for x in c.execute(
            "SELECT version, model, verify_passed, created_at FROM summaries WHERE prec_id=? ORDER BY version",
            (prec_id,))] if _has_table(c, "summaries") else []
        return out

    @app.get("/api/precedents/{prec_id}/summary/{version}")
    def get_summary(prec_id: str, version: str):
        if version not in VARIANTS.values():
            raise HTTPException(404)
        c = db()
        p = _precedent(c, prec_id)
        s = c.execute("SELECT * FROM summaries WHERE prec_id=? AND version=?", (prec_id, version)).fetchone() \
            if _has_table(c, "summaries") else None
        if s is None:
            raise HTTPException(404)
        summary = json.loads(s["summary_json"])
        return {"prec_id": prec_id, "version": version, "model": s["model"], "created_at": s["created_at"],
                "summary": summary, "verify": json.loads(s["verify_json"]),
                "evidence_spans": evidence_spans(summary, p["full_text_clean"] or "")}

    # ------------------------------------------------------------ HTML (템플릿은 TASK-003)
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request, "index.html", {})

    @app.get("/precedents/{prec_id}", response_class=HTMLResponse)
    def detail(request: Request, prec_id: str):
        if not prec_id.isdigit():
            raise HTTPException(404)
        return templates.TemplateResponse(request, "detail.html", {"prec_id": prec_id})

    return app


app = create_app()  # uvicorn 진입점
