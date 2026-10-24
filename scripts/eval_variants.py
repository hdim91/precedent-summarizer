"""입력 변형 비교 채점: v1(blind) vs v1o(official) — 판결문 전문 기준 블라인드 쌍대 채점.

판결요지를 입력받은 v1o는 판결요지 기준 채점에서 유리하므로, 심판은 **판례내용 전문**을 기준으로 평가한다.
- 대상: summaries에 v1·v1o가 모두 있는 판결(--ids-file로 제한 가능)
- X/Y 순서 무작위(시드 고정), 결과는 원래 이름으로 환원
- 출력: data/pilot/eval_variants_{NAME}/{prec_id}.json, 끝에 집계 출력
- PC에서 실행(DB 읽기, --record-cost 시 장부 기록 — D-022·D-023)

사용: python scripts/eval_variants.py --ids-file data/eval_set_100.txt --judge claude-opus-5-5 --out opus [--workers 6] [--record-cost]
"""
from __future__ import annotations

import argparse, json, random, statistics as st
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from precedent_summarizer.clients.anthropic_client import make_client
from precedent_summarizer.common.security import install_log_masking, mask_secrets
from precedent_summarizer.config import get_settings
from precedent_summarizer.engine.batch import connect, record_extra_cost
from precedent_summarizer.engine.costs import actual_cost

STATUS = ["correct", "partial", "missing"]
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["key_points", "x_errors", "y_errors", "x_score", "y_score", "preference", "reason"],
    "properties": {
        "key_points": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                       "required": ["point", "x", "y"],
                       "properties": {"point": {"type": "string"}, "x": {"type": "string", "enum": STATUS},
                                      "y": {"type": "string", "enum": STATUS}}}},
        "x_errors": {"type": "array", "items": {"type": "string"}},
        "y_errors": {"type": "array", "items": {"type": "string"}},
        "x_score": {"type": "integer", "description": "1~5"},
        "y_score": {"type": "integer", "description": "1~5"},
        "preference": {"type": "string", "enum": ["X", "Y", "tie"]},
        "reason": {"type": "string"},
    },
}
SYSTEM = """당신은 대법원 판결 요약의 정확성과 충실도를 평가하는 법률 전문가다. 기준은 오직 [판례내용] 원문이다.
1. 원문에서 대법원 판단의 핵심 법리·결론을 3~8개 key_points로 직접 뽑고, 요약 X·Y가 각 point를 correct/partial/missing으로 판정한다.
2. x_errors/y_errors: 원문과 모순, 원심 판단을 대법원 판단으로 서술, 다수·소수의견 혼동, 결론 오류, 원문에 없는 내용 추가만 적는다. 문체·길이는 오류가 아니다.
3. x_score/y_score: 1(부정확)~5(정확·충실) 정수. 4. X/Y 순서는 무작위다. 길이·문체가 아니라 법리의 정확성과 충실도로만 판단한다."""


def brief(s: dict) -> dict:
    keep = ("one_line", "issues", "rulings", "disposition", "separate_opinions", "lower_court", "facts")
    out = json.loads(json.dumps({k: s.get(k) for k in keep}, ensure_ascii=False))
    def strip(o):
        if isinstance(o, dict):
            o.pop("evidence", None); [strip(v) for v in o.values()]
        elif isinstance(o, list):
            [strip(v) for v in o]
    strip(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-file"); ap.add_argument("--judge", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--record-cost", action="store_true")
    a = ap.parse_args()
    install_log_masking()
    s = get_settings(); client = make_client(s); conn = connect(s.db_path)
    rows = conn.execute("SELECT p.prec_id, p.case_type_name, p.full_text_clean, a.summary_json AS a_json, "
                        "b.summary_json AS b_json, a.model AS a_model FROM precedents p "
                        "JOIN summaries a ON a.prec_id=p.prec_id AND a.version='v1' "
                        "JOIN summaries b ON b.prec_id=p.prec_id AND b.version='v1o'").fetchall()
    if a.ids_file:
        keep = set(Path(a.ids_file).read_text(encoding="utf-8").strip().split(","))
        rows = [r for r in rows if r["prec_id"] in keep]
    print(f"비교 대상(두 버전 모두 있음): {len(rows)}건")
    out = s.raw_cache_dir.parent / "pilot" / f"eval_variants_{a.out}"; out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(a.seed)
    order = {r["prec_id"]: rnd.random() < 0.5 for r in rows}

    def one(r):
        dst = out / f"{r['prec_id']}.json"
        if dst.exists():
            return
        A, Bv = json.loads(r["a_json"]), json.loads(r["b_json"])
        x, y, nx, ny = (A, Bv, "v1", "v1o") if order[r["prec_id"]] else (Bv, A, "v1o", "v1")
        user = (f"[판례내용]\n{r['full_text_clean']}\n\n[요약 X]\n{json.dumps(brief(x), ensure_ascii=False)}\n\n"
                f"[요약 Y]\n{json.dumps(brief(y), ensure_ascii=False)}")
        try:
            msg = client.messages.create(model=a.judge, max_tokens=12000, system=SYSTEM,
                                         output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                                         messages=[{"role": "user", "content": user}])
            j = json.loads(next(b.text for b in msg.content if b.type == "text"))
        except Exception as e:  # noqa: BLE001
            print(r["prec_id"], "ERROR", mask_secrets(f"{type(e).__name__}: {e}")[:200]); return
        res = {"prec_id": r["prec_id"], "case_type": r["case_type_name"], "judge": a.judge,
               "points": [{"point": p["point"], nx: p["x"], ny: p["y"]} for p in j["key_points"]],
               "errors": {nx: j["x_errors"], ny: j["y_errors"]}, "score": {nx: j["x_score"], ny: j["y_score"]},
               "preference": {"X": nx, "Y": ny, "tie": "tie"}[j["preference"]], "reason": j["reason"],
               "usage": {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens}}
        dst.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(one, rows))

    rs = [json.loads(f.read_text(encoding="utf-8")) for f in out.glob("*.json")]
    if not rs:
        return
    def summ(sub, label):
        line = [f"[{label} n={len(sub)}]"]
        for v in ("v1", "v1o"):
            c = Counter(p[v] for r in sub for p in r["points"]); n = sum(c.values()) or 1
            line.append(f"{v}: 점수 {st.mean(r['score'][v] for r in sub):.2f}, correct {c['correct']/n:.0%}, "
                        f"missing {c['missing']/n:.0%}, 오류 {sum(len(r['errors'][v]) for r in sub)}")
        p = Counter(r["preference"] for r in sub)
        line.append(f"선호 v1 {p['v1']} / v1o {p['v1o']} / 동률 {p['tie']}")
        print(" | ".join(line))
    summ(rs, "전체")
    for k in sorted({r["case_type"] for r in rs}):
        summ([r for r in rs if r["case_type"] == k], k)
    cost = sum(actual_cost(a.judge, {"input_tokens": r["usage"]["in"], "output_tokens": r["usage"]["out"]}, batch=False)
               for r in rs)
    print(f"채점 비용(표준 단가, 누적): ${cost:.4f}")
    if a.record_cost:
        record_extra_cost(conn, "eval_variants_judge", cost, a.judge, f"eval_variants_{a.out}")
        print("장부(extra_costs)에 기록했습니다.")


if __name__ == "__main__":
    main()
