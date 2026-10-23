"""두 모델 요약을 법원 작성 판시사항·판결요지 기준으로 블라인드 쌍대 채점.

사용: python scripts/eval_ab.py --a ab_sonnet --b ab_opus --ids-file F [--ids-file G] --judge MODEL --out NAME [--workers K]
- A/B 제시 순서는 건마다 무작위(시드 고정) → 결과는 원래 이름으로 환원해 저장.
- 출력: data/pilot/eval_{NAME}/{prec_id}.json
"""
from __future__ import annotations

import argparse, json, random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from precedent_summarizer.clients.anthropic_client import make_client
from precedent_summarizer.common.security import install_log_masking, mask_secrets
from precedent_summarizer.config import get_settings
from precedent_summarizer.load.normalize import clean_text

STATUS = ["covered", "partial", "missing"]
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["points", "x_errors", "y_errors", "x_score", "y_score", "preference", "reason"],
    "properties": {
        "points": {"type": "array", "items": {"type": "object", "additionalProperties": False,
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
SYSTEM = """당신은 대법원 판례 요약의 품질을 평가하는 법률 전문가다. 기준은 법원이 작성한 [판시사항]과 [판결요지]다.
1. 판결요지를 핵심 법리 단위(point)로 나누고, 요약 X와 Y가 각 point를 covered(정확히 담음)/partial(일부·모호)/missing(없음)으로 판정한다.
2. x_errors/y_errors: 판결요지와 모순되는 서술, 원심 판단을 대법원 판단으로 적은 것, 다수의견과 소수의견을 혼동한 것, 결론 오류만 적는다. 문체·길이는 오류가 아니다.
3. x_score/y_score: 1(부정확)~5(정확·충실) 정수.
4. 요약의 길이나 문체가 아니라 법리의 정확성과 충실도로만 판단한다. X/Y 순서는 무작위다."""


def brief(s: dict) -> dict:
    keep = ("one_line", "issues", "rulings", "disposition", "separate_opinions", "lower_court")
    out = {k: s.get(k) for k in keep}
    for r in out.get("rulings") or []:
        r.pop("evidence", None)
    for k in ("disposition", "lower_court"):
        if isinstance(out.get(k), dict):
            out[k] = {kk: vv for kk, vv in out[k].items() if kk != "evidence"}
    for o in out.get("separate_opinions") or []:
        o.pop("evidence", None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True); ap.add_argument("--b", required=True)
    ap.add_argument("--ids-file", action="append", required=True)
    ap.add_argument("--judge", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4); ap.add_argument("--seed", type=int, default=20261024)
    a = ap.parse_args()
    install_log_masking()
    s = get_settings(); client = make_client(s)
    base = s.raw_cache_dir.parent / "pilot"; out = base / f"eval_{a.out}"; out.mkdir(parents=True, exist_ok=True)
    ids = [i for f in a.ids_file for i in Path(f).read_text(encoding="utf-8").strip().split(",")]
    rnd = random.Random(a.seed); order = {pid: rnd.random() < 0.5 for pid in ids}

    def one(pid):
        dst = out / f"{pid}.json"
        if dst.exists():
            return
        ra = json.loads((base / a.a / f"{pid}.json").read_text(encoding="utf-8"))
        rb = json.loads((base / a.b / f"{pid}.json").read_text(encoding="utf-8"))
        d = json.loads((s.raw_cache_dir / "prec_detail" / f"{pid}.json").read_text(encoding="utf-8"))["PrecService"]
        x, y = (ra, rb) if order[pid] else (rb, ra)
        user = (f"[판시사항]\n{clean_text(d.get('판시사항')) or '(없음)'}\n\n[판결요지]\n{clean_text(d.get('판결요지'))}\n\n"
                f"[요약 X]\n{json.dumps(brief(x['summary']), ensure_ascii=False)}\n\n[요약 Y]\n{json.dumps(brief(y['summary']), ensure_ascii=False)}")
        try:
            msg = client.messages.create(model=a.judge, max_tokens=12000, system=SYSTEM,
                                         output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                                         messages=[{"role": "user", "content": user}])
            j = json.loads(next(b.text for b in msg.content if b.type == "text"))
        except Exception as e:  # noqa: BLE001
            print(pid, "ERROR", mask_secrets(f"{type(e).__name__}: {e}")[:200]); return
        name_x, name_y = (a.a, a.b) if order[pid] else (a.b, a.a)
        res = {"prec_id": pid, "judge": a.judge, "x_is": name_x,
               "points": [{"point": p["point"], name_x: p["x"], name_y: p["y"]} for p in j["points"]],
               "errors": {name_x: j["x_errors"], name_y: j["y_errors"]},
               "score": {name_x: j["x_score"], name_y: j["y_score"]},
               "preference": {"X": name_x, "Y": name_y, "tie": "tie"}[j["preference"]], "reason": j["reason"],
               "usage": {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens}}
        dst.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(pid, "ok", res["score"], res["preference"])

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(one, ids))


if __name__ == "__main__":
    main()
