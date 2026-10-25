"""배치 요약 최종 통계를 JSON 파일로 내보낸다(DB 읽기 전용, PC에서 실행 — D-022).

사용: python scripts/export_stats.py  →  data/raw_cache/reports/stats_{YYYYMMDD_HHMM}.json
원격 셸(Claude)은 DB를 직접 열 수 없으므로 이 파일로 통계를 공유한다.
"""
from __future__ import annotations

import json, sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone

from precedent_summarizer.config import get_settings

KST = timezone(timedelta(hours=9))


def main():
    s = get_settings()
    c = sqlite3.connect(f"file:{s.db_path.as_posix()}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    q = lambda sql, *a: [dict(r) for r in c.execute(sql, a)]
    out = {"generated_at": datetime.now(KST).isoformat(timespec="seconds")}
    out["summaries_by_version_model"] = q("SELECT version, model, COUNT(*) n FROM summaries GROUP BY 1,2 ORDER BY 1,2")
    out["v1o_date_range"] = q("SELECT MIN(COALESCE(p.decision_date,p.decision_date_inferred)) min_date, "
                              "MAX(COALESCE(p.decision_date,p.decision_date_inferred)) max_date, COUNT(*) n "
                              "FROM summaries s JOIN precedents p USING(prec_id) WHERE s.version='v1o'")[0]
    out["v1o_by_year"] = q("SELECT substr(COALESCE(p.decision_date,p.decision_date_inferred),1,4) y, COUNT(*) n "
                           "FROM summaries s JOIN precedents p USING(prec_id) WHERE s.version='v1o' GROUP BY 1 ORDER BY 1 DESC")
    out["v1o_by_case_type"] = q("SELECT p.case_type_name, COUNT(*) n FROM summaries s JOIN precedents p USING(prec_id) "
                                "WHERE s.version='v1o' GROUP BY 1 ORDER BY 2 DESC")
    # 1차 시도 기준 검증 통과율(사건종류·모델별), 최종 미요약 건
    out["first_attempt_pass_by_case_type"] = q(
        "SELECT p.case_type_name, b.model, COUNT(*) n, SUM(b.verify_passed) passed, "
        "ROUND(1.0*SUM(b.verify_passed)/COUNT(*),4) rate FROM batch_items b JOIN precedents p USING(prec_id) "
        "WHERE b.variant='official' AND b.attempt=1 AND b.result_type='succeeded' GROUP BY 1,2 ORDER BY 1,2")
    out["retry_pass"] = q("SELECT variant, model, COUNT(*) n, SUM(verify_passed) passed FROM batch_items "
                          "WHERE attempt=2 GROUP BY 1,2")
    out["unsummarized_after_retry"] = q(
        "SELECT b.variant, COUNT(DISTINCT b.prec_id) n FROM batch_items b WHERE NOT EXISTS "
        "(SELECT 1 FROM summaries x WHERE x.prec_id=b.prec_id AND x.version=CASE b.variant WHEN 'official' THEN 'v1o' ELSE 'v1' END) "
        "GROUP BY 1")
    # 실패 사유 분포(사유가 저장된 건만)
    reasons = Counter(); n_detail = 0
    for (e,) in c.execute("SELECT error FROM batch_items WHERE verify_passed=0 AND error IS NOT NULL"):
        try:
            d = json.loads(e)
        except json.JSONDecodeError:
            reasons["unparsable_detail"] += 1; continue
        n_detail += 1
        if d.get("parse_error"):
            reasons["parse_error"] += 1
        if d.get("missing"):
            reasons["evidence_not_in_text"] += 1
            for m in d["missing"]:
                reasons["missing_at:" + m["path"].split("[")[0].split(".")[0]] += 1
        if d.get("disposition") == "mismatch":
            reasons["disposition_mismatch"] += 1
    out["failure_reasons"] = {"items_with_detail": n_detail, "counts": dict(reasons.most_common())}
    out["cost"] = {
        "batch_actual_usd": c.execute("SELECT ROUND(SUM(cost_usd),4) FROM batch_items").fetchone()[0],
        "extra_usd": c.execute("SELECT ROUND(COALESCE(SUM(cost_usd),0),4) FROM extra_costs").fetchone()[0],
        "by_model": q("SELECT model, attempt, COUNT(*) n, ROUND(SUM(cost_usd),4) usd, ROUND(AVG(cost_usd),5) avg_usd, "
                      "ROUND(SUM(cost_usd)/NULLIF(SUM(est_cost_usd),0),3) actual_over_est "
                      "FROM batch_items WHERE cost_usd IS NOT NULL GROUP BY 1,2"),
    }
    out_dir = s.raw_cache_dir / "reports"; out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"stats_{datetime.now(KST):%Y%m%d_%H%M}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
