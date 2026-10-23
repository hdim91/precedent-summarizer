"""요약 엔진 소규모 시범(DB 적재 전, raw 상세 직접 사용).

사용: python scripts/pilot_summarize.py --ids 123,456 | --sample N [--model M]
출력: data/pilot/{prec_id}.json (요약·검증·토큰). 정제·구획은 TASK-002의 load.normalize가 생기면 그것으로 교체한다.
"""
from __future__ import annotations

import argparse, json, random, re, time
from pathlib import Path

from precedent_summarizer.clients.anthropic_client import make_client
from precedent_summarizer.common.security import install_log_masking, mask_secrets
from precedent_summarizer.config import get_settings
from precedent_summarizer.engine.summarize import CaseInput, summarize_one
from precedent_summarizer.engine.verify import verify

try:  # TASK-002 완료 후 우선 사용
    from precedent_summarizer.load.normalize import clean_text, split_sections  # type: ignore
except ImportError:  # 임시 구현(시범 전용)
    def clean_text(s):
        s = re.sub(r"(?i)<br\s*/?>", "\n", s or "")
        s = "\n".join(l.rstrip() for l in s.split("\n"))
        return re.sub(r"\n{3,}", "\n\n", s).strip()

    def split_sections(t):
        hs = [(m.start(), m.group(0), re.sub(r"\s+", "", m.group(1))) for m in re.finditer(r"【([^】]{1,30})】", t)]
        return [{"header": h, "header_norm": n, "start": st, "end": (hs[i + 1][0] if i + 1 < len(hs) else len(t))}
                for i, (st, h, n) in enumerate(hs)]


def load_case(raw_dir: Path, pid: str):
    d = json.loads((raw_dir / "prec_detail" / f"{pid}.json").read_text(encoding="utf-8"))["PrecService"]
    full = clean_text(d.get("판례내용"))
    return d, CaseInput(pid, d.get("사건번호"), d.get("사건명"), d.get("선고일자"), d.get("법원명"),
                        d.get("사건종류명"), full), split_sections(full)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids"); g.add_argument("--sample", type=int)
    ap.add_argument("--model"); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    install_log_masking()
    s = get_settings(); client = make_client(s); model = a.model or s.model_default
    raw = s.raw_cache_dir
    ids = a.ids.split(",") if a.ids else random.Random(a.seed).sample(
        sorted(p.stem for p in (raw / "prec_detail").glob("*.json")), a.sample)
    out = s.raw_cache_dir.parent / "pilot"; out.mkdir(parents=True, exist_ok=True)
    for pid in ids:
        d, c, secs = load_case(raw, pid)
        t0 = time.time()
        try:
            summ, usage = summarize_one(client, c, model)
            v = verify(summ, full_text_clean=c.full_text_clean, sections=secs,
                       ref_statutes_clean=clean_text(d.get("참조조문")))
            rec = {"prec_id": pid, "model": model, "elapsed_s": round(time.time() - t0, 1), "usage": usage,
                   "verify": v.to_dict(), "summary": summ, "official_summary": clean_text(d.get("판결요지"))}
            print(f"{pid} {c.case_no} len={len(c.full_text_clean)} pass={v.passed} ev={v.evidence_found}/{v.evidence_total} "
                  f"disp={v.disposition_check} stat={v.statutes_overlap}/{v.statutes_ref} tok={usage['input_tokens']}+{usage['output_tokens']} "
                  f"cache_r={usage['cache_read_input_tokens']} {rec['elapsed_s']}s")
        except Exception as e:  # noqa: BLE001
            rec = {"prec_id": pid, "error": mask_secrets(f"{type(e).__name__}: {e}")}
            print(pid, "ERROR", rec["error"][:200])
        (out / f"{pid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
