"""평가용 층화 표본 생성(raw 캐시 기준, DB 미사용).

사건종류별 할당량만큼, 판결요지가 있는 요약 대상 판결을 최신 선고일 순으로 뽑는다.
대상 조건은 P4 선정과 같다: 상세 있음, 정제 본문 300자 이상, 심리불속행 아님. 국세 출처 제외(본문 미제공).
사용: python scripts/make_eval_set.py --out data/eval_set_100.txt [--years 2022-2026]
"""
from __future__ import annotations

import argparse, json
from collections import Counter
from pathlib import Path

from precedent_summarizer.config import get_settings
from precedent_summarizer.load.normalize import clean_text, is_summary_dismissal, parse_date

QUOTA = {"민사": 30, "형사": 25, "일반행정": 20, "세무": 10, "가사": 8, "특허": 7}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--years", default="2022-2026")
    a = ap.parse_args()
    y0, y1 = map(int, a.years.split("-"))
    raw = get_settings().raw_cache_dir
    pool = {k: [] for k in QUOTA}
    for line in (raw / "manifest" / "prec_ids_org400201.jsonl").open(encoding="utf-8"):
        x = json.loads(line)
        if not x["year"] or not (y0 <= x["year"] <= y1):
            continue
        p = raw / "prec_detail" / f"{x['prec_id']}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))["PrecService"]
        kind = d.get("사건종류명")
        text = clean_text(d.get("판례내용")) or ""
        if kind not in pool or not clean_text(d.get("판결요지")) or len(text) < 300 or is_summary_dismissal(text):
            continue
        date, _ = parse_date(d.get("선고일자"))
        pool[kind].append((date or "", int(x["prec_id"]), len(text), "다수의견" in text and "반대의견" in text))
    picked, report = [], {}
    for kind, n in QUOTA.items():
        rows = sorted(pool[kind], reverse=True)[:n]
        picked += [str(r[1]) for r in rows]
        report[kind] = {"quota": n, "picked": len(rows), "pool": len(pool[kind]),
                        "date_range": [rows[-1][0], rows[0][0]] if rows else None,
                        "long_gt15k": sum(r[2] > 15000 for r in rows), "en_banc": sum(r[3] for r in rows)}
    Path(a.out).write_text(",".join(picked), encoding="utf-8")
    print(json.dumps({"n": len(picked), "by_kind": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
