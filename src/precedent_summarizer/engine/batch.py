"""배치 요약 파이프라인 P4 (Claude 소유).

명령 (PC에서 실행 권장 — DB가 로컬 디스크):
  python -m precedent_summarizer.engine.batch plan    --variant blind [--budget 81] [--max N] [--ids-file F]
  python -m precedent_summarizer.engine.batch submit  --variant blind [--budget 81] [--max N] [--ids-file F] [--yes]
  python -m precedent_summarizer.engine.batch status
  python -m precedent_summarizer.engine.batch collect           # 끝난 배치 수거·검증·저장, 검증 실패는 재시도 큐
  python -m precedent_summarizer.engine.batch retry   --variant blind [--yes]   # 검증 실패 건 상위 모델로 1회 재요청
  python -m precedent_summarizer.engine.batch spend             # 누적 지출

정책
- 선정: detail_status=ok, 본문 300자 이상, 심리불속행 제외(컬럼 있을 때), 이미 해당 버전 요약이 있는 건 제외.
  정렬: COALESCE(decision_date, decision_date_inferred) 내림차순(최신순), 날짜 없으면 맨 뒤.
- 모델 라우팅(D-020, 안 C): 일반 → CLAUDE_MODEL_DEFAULT, 장문(>15,000자)·전원합의체(다수의견·반대의견 존재) → CLAUDE_MODEL_COMPLEX.
  검증 실패 건은 retry에서 CLAUDE_MODEL_COMPLEX로 1회만 재요청.
- 예산: 누적 실측 지출 + 미수거 배치 추정 + 이번 추정 ≤ budget(기본 BATCH_BUDGET_USD). 초과분은 잘라서 제출.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from precedent_summarizer.common.security import install_log_masking, mask_secrets
from precedent_summarizer.config import Settings, get_settings
from precedent_summarizer.engine.costs import actual_cost, est_cost
from precedent_summarizer.engine.summarize import CaseInput, parse_output, request_params
from precedent_summarizer.engine.variants import VARIANTS, build_user_message, has_official
from precedent_summarizer.engine.verify import verify

KST = timezone(timedelta(hours=9))
LOG = logging.getLogger(__name__)
BATCH_SQL = Path(__file__).resolve().parents[1] / "schemas" / "batch.sql"
MIN_CHARS = 300
LONG_CHARS = 15000
MAX_REQUESTS_PER_BATCH = 10000
_MODEL_CODE = {"claude-sonnet-5-5": "s", "claude-opus-5-5": "o"}


def now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(BATCH_SQL.read_text(encoding="utf-8"))
    return conn


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def is_en_banc(text: str) -> bool:
    return "다수의견" in text and "반대의견" in text


def route_model(s: Settings, text: str) -> str:
    return s.model_complex if (len(text) > LONG_CHARS or is_en_banc(text)) else s.model_default


def custom_id(prec_id: str, variant: str, model: str, attempt: int) -> str:
    cid = f"{prec_id}-{variant[0]}-{_MODEL_CODE.get(model, 'x')}-{attempt}"
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cid)
    return cid


def parse_custom_id(cid: str) -> tuple[str, str, int]:
    pid, v, _m, a = cid.split("-")
    return pid, {"b": "blind", "o": "official"}[v], int(a)


# ---------------------------------------------------------------- 선정
def candidates(conn: sqlite3.Connection, variant: str, ids: Optional[list[str]] = None) -> Iterable[sqlite3.Row]:
    cols = columns(conn, "precedents")
    date_expr = "COALESCE(p.decision_date, p.decision_date_inferred)" if "decision_date_inferred" in cols else "p.decision_date"
    where = ["p.detail_status='ok'", f"length(p.full_text_clean) >= {MIN_CHARS}",
             "NOT EXISTS (SELECT 1 FROM summaries s WHERE s.prec_id=p.prec_id AND s.version=?)",
             # 제출됐지만 아직 수거되지 않은 건 중복 제출 방지
             "NOT EXISTS (SELECT 1 FROM batch_items b JOIN batch_runs r USING(batch_id) "
             "WHERE b.prec_id=p.prec_id AND b.variant=? AND r.status!='collected')"]
    if "is_summary_dismissal" in cols:
        where.append("p.is_summary_dismissal=0")
    if variant == "official":  # 판시사항·판결요지가 있는 판결만(없으면 blind와 동일)
        where.append("(p.holdings_clean IS NOT NULL OR p.official_summary_clean IS NOT NULL)")
    params: list[Any] = [VARIANTS[variant], variant]
    if ids:
        where.append(f"p.prec_id IN ({','.join('?' * len(ids))})")
        params += ids
    sql = (f"SELECT p.prec_id, p.case_no, p.case_name, {date_expr} AS ddate, p.court_name, p.case_type_name, "
           f"p.full_text_clean, p.holdings_clean, p.official_summary_clean, p.sections_json, p.ref_statutes_clean "
           f"FROM precedents p WHERE {' AND '.join(where)} ORDER BY ({date_expr} IS NULL), {date_expr} DESC, "
           f"CAST(p.prec_id AS INTEGER) DESC")
    return conn.execute(sql, params)


def spent_and_pending(conn: sqlite3.Connection) -> tuple[float, float]:
    spent = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM batch_items WHERE cost_usd IS NOT NULL").fetchone()[0]
    pending = conn.execute("SELECT COALESCE(SUM(b.est_cost_usd),0) FROM batch_items b JOIN batch_runs r USING(batch_id) "
                           "WHERE r.status!='collected'").fetchone()[0]
    return float(spent), float(pending)


def plan(conn, s: Settings, variant: str, budget: float, max_n: Optional[int], ids=None) -> dict:
    spent, pending = spent_and_pending(conn)
    room = budget - spent - pending
    picked, total, by_model, dates = [], 0.0, {}, []
    for r in candidates(conn, variant, ids):
        if max_n is not None and len(picked) >= max_n:
            break
        model = route_model(s, r["full_text_clean"])
        extra = len((r["holdings_clean"] or "") + (r["official_summary_clean"] or "")) if variant == "official" else 0
        c = est_cost(model, len(r["full_text_clean"]), extra)
        if total + c > room:
            break
        picked.append((r, model, c))
        total += c
        by_model[model] = by_model.get(model, 0) + 1
        dates.append(r["ddate"])
    return {"variant": variant, "budget": budget, "spent": round(spent, 4), "pending_est": round(pending, 4),
            "room": round(room, 4), "n": len(picked), "est_cost": round(total, 4), "by_model": by_model,
            "date_range": [dates[0] if dates else None, dates[-1] if dates else None], "_items": picked}


def build_request(row, model: str, variant: str, attempt: int) -> dict:
    c = CaseInput(row["prec_id"], row["case_no"], row["case_name"], row["ddate"], row["court_name"],
                  row["case_type_name"], row["full_text_clean"])
    params = request_params(c, model)
    params["messages"] = [{"role": "user", "content": build_user_message(
        c, variant, row["holdings_clean"], row["official_summary_clean"])}]
    return {"custom_id": custom_id(row["prec_id"], variant, model, attempt), "params": params}


def submit(conn, client, p: dict, attempt: int = 1, note: str = "") -> list[str]:
    ids = []
    items = p["_items"]
    for i in range(0, len(items), MAX_REQUESTS_PER_BATCH):
        chunk = items[i:i + MAX_REQUESTS_PER_BATCH]
        reqs = [build_request(r, m, p["variant"], attempt) for r, m, _ in chunk]
        b = client.messages.batches.create(requests=reqs)
        est = sum(c for _, _, c in chunk)
        conn.execute("INSERT INTO batch_runs VALUES (?,?,?,?,?,?,?,?)",
                     (b.id, p["variant"], now(), "submitted", len(chunk), est, None, note))
        conn.executemany("INSERT INTO batch_items(batch_id,custom_id,prec_id,variant,model,attempt,est_cost_usd) "
                         "VALUES (?,?,?,?,?,?,?)",
                         [(b.id, q["custom_id"], r["prec_id"], p["variant"], m, attempt, c)
                          for q, (r, m, c) in zip(reqs, chunk)])
        conn.commit()
        ids.append(b.id)
        LOG.info("submitted %s (%d requests, est $%.2f)", b.id, len(chunk), est)
    return ids


# ---------------------------------------------------------------- 수거
def _get(o, k, default=None):
    return o.get(k, default) if isinstance(o, dict) else getattr(o, k, default)


def handle_result(conn, s: Settings, batch_id: str, res) -> dict:
    cid = _get(res, "custom_id")
    pid, variant, attempt = parse_custom_id(cid)
    model = conn.execute("SELECT model FROM batch_items WHERE batch_id=? AND custom_id=?", (batch_id, cid)).fetchone()[0]
    result = _get(res, "result")
    rtype = _get(result, "type")
    out = {"custom_id": cid, "type": rtype, "passed": None}
    if rtype != "succeeded":
        err = mask_secrets(json.dumps(_get(result, "error"), default=str)[:300])
        conn.execute("UPDATE batch_items SET result_type=?, error=?, cost_usd=0 WHERE batch_id=? AND custom_id=?",
                     (rtype, err, batch_id, cid))
        return out
    msg = _get(result, "message")
    u = _get(msg, "usage")
    usage = {k: (_get(u, k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                            "cache_creation_input_tokens")}
    cost = actual_cost(model, usage)
    row = conn.execute("SELECT full_text_clean, sections_json, ref_statutes_clean FROM precedents WHERE prec_id=?",
                       (pid,)).fetchone()
    try:
        summary = parse_output(msg)
        v = verify(summary, full_text_clean=row["full_text_clean"], sections=json.loads(row["sections_json"] or "[]"),
                   ref_statutes_clean=row["ref_statutes_clean"])
    except Exception as exc:  # noqa: BLE001 — 파싱 실패도 원장에 남기고 재시도 대상
        conn.execute("UPDATE batch_items SET result_type=?, verify_passed=0, cost_usd=?, error=? "
                     "WHERE batch_id=? AND custom_id=?",
                     ("succeeded", cost, mask_secrets(f"{type(exc).__name__}: {exc}")[:300], batch_id, cid))
        out["passed"] = False
        return out
    conn.execute("UPDATE batch_items SET result_type='succeeded', verify_passed=?, cost_usd=? "
                 "WHERE batch_id=? AND custom_id=?", (int(v.passed), cost, batch_id, cid))
    if v.passed:  # RULES 5장: 검증 통과한 요약만 저장
        conn.execute("INSERT OR REPLACE INTO summaries(prec_id,version,model,summary_json,verify_json,verify_passed,"
                     "input_tokens,output_tokens,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (pid, VARIANTS[variant], model, json.dumps(summary, ensure_ascii=False),
                      json.dumps(v.to_dict(), ensure_ascii=False), 1, usage["input_tokens"], usage["output_tokens"], now()))
    out["passed"] = v.passed
    return out


def collect(conn, client, s: Settings) -> list[dict]:
    reports = []
    for (bid,) in conn.execute("SELECT batch_id FROM batch_runs WHERE status!='collected'").fetchall():
        b = client.messages.batches.retrieve(bid)
        if _get(b, "processing_status") != "ended":
            reports.append({"batch_id": bid, "status": _get(b, "processing_status")})
            continue
        stats = {"succeeded": 0, "errored": 0, "canceled": 0, "expired": 0, "passed": 0, "failed_verify": 0}
        for res in client.messages.batches.results(bid):
            o = handle_result(conn, s, bid, res)
            stats[o["type"]] = stats.get(o["type"], 0) + 1
            if o["passed"] is True:
                stats["passed"] += 1
            elif o["passed"] is False:
                stats["failed_verify"] += 1
        cost = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM batch_items WHERE batch_id=?", (bid,)).fetchone()[0]
        conn.execute("UPDATE batch_runs SET status='collected', actual_cost_usd=? WHERE batch_id=?", (cost, bid))
        conn.commit()
        reports.append({"batch_id": bid, "status": "collected", "actual_cost_usd": round(cost, 4), **stats})
    return reports


def retry_plan(conn, s: Settings, variant: str, budget: float) -> dict:
    """1차(attempt=1)에서 검증 실패·파싱 실패·errored인 건 → 상위 모델로 1회."""
    rows = conn.execute(
        "SELECT DISTINCT b.prec_id FROM batch_items b JOIN batch_runs r USING(batch_id) "
        "WHERE r.status='collected' AND b.variant=? AND b.attempt=1 AND (b.verify_passed=0 OR b.result_type!='succeeded') "
        "AND NOT EXISTS (SELECT 1 FROM batch_items c WHERE c.prec_id=b.prec_id AND c.variant=b.variant AND c.attempt=2) "
        "AND NOT EXISTS (SELECT 1 FROM summaries x WHERE x.prec_id=b.prec_id AND x.version=?)",
        (variant, VARIANTS[variant])).fetchall()
    ids = [r[0] for r in rows]
    if not ids:
        return {"variant": variant, "n": 0, "est_cost": 0, "_items": []}
    p = plan(conn, s, variant, budget, None, ids)
    p["_items"] = [(r, s.model_complex, est_cost(s.model_complex, len(r["full_text_clean"]))) for r, _, _ in p["_items"]]
    p["est_cost"] = round(sum(c for _, _, c in p["_items"]), 4)
    return p


def public(p: dict) -> dict:
    return {k: v for k, v in p.items() if not k.startswith("_")}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="배치 요약 P4")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "submit", "retry"):
        sp = sub.add_parser(name)
        sp.add_argument("--variant", choices=list(VARIANTS), default="blind")
        sp.add_argument("--budget", type=float)
        if name != "retry":
            sp.add_argument("--max", type=int)
            sp.add_argument("--ids-file")
        if name != "plan":
            sp.add_argument("--yes", action="store_true", help="확인 없이 제출")
    sub.add_parser("status"); sub.add_parser("collect"); sub.add_parser("spend")
    a = ap.parse_args(argv)
    install_log_masking()
    s = get_settings()
    conn = connect(s.db_path)
    budget = getattr(a, "budget", None) or s.batch_budget_usd
    if a.cmd in ("plan", "submit", "retry") and budget is None:
        print("예산이 없습니다: --budget 또는 .env BATCH_BUDGET_USD"); return 2
    from precedent_summarizer.clients.anthropic_client import make_client
    if a.cmd in ("plan", "submit"):
        ids = Path(a.ids_file).read_text(encoding="utf-8").strip().split(",") if a.ids_file else None
        p = plan(conn, s, a.variant, budget, a.max, ids)
        print(json.dumps(public(p), ensure_ascii=False, indent=2))
        if a.cmd == "submit" and p["n"]:
            if not a.yes and input(f"{p['n']}건, 추정 ${p['est_cost']:.2f} 제출할까요? [y/N] ").strip().lower() != "y":
                print("취소"); return 1
            print("batch:", submit(conn, make_client(s), p, note=f"{a.variant} plan"))
    elif a.cmd == "retry":
        p = retry_plan(conn, s, a.variant, budget)
        print(json.dumps(public(p), ensure_ascii=False, indent=2))
        if p["n"] and (a.yes or input(f"재시도 {p['n']}건 ${p['est_cost']:.2f} 제출? [y/N] ").strip().lower() == "y"):
            print("batch:", submit(conn, make_client(s), p, attempt=2, note=f"{a.variant} retry"))
    elif a.cmd == "status":
        for r in conn.execute("SELECT * FROM batch_runs ORDER BY created_at"):
            print(dict(r))
    elif a.cmd == "collect":
        for r in collect(conn, make_client(s), s):
            print(json.dumps(r, ensure_ascii=False))
    elif a.cmd == "spend":
        spent, pending = spent_and_pending(conn)
        print(f"실측 지출 ${spent:.4f} / 미수거 추정 ${pending:.4f} / 예산 ${budget or 0:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
