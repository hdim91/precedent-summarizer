"""요약 입력 변형 (Claude 소유).

- blind   (요약 버전 v1):  판례내용만 입력. 법원 판결요지를 오염 없는 평가 기준으로 쓸 수 있다(D-019).
- official(요약 버전 v1o): 판례내용 + 판시사항·판결요지(있을 때만)를 '참고자료'로 입력. 근거 인용은 여전히 판례내용에서만.
  판시사항·판결요지가 없는 판결은 두 변형의 입력이 같으므로 official을 따로 돌리지 않는다(blind 결과 공유).
"""
from __future__ import annotations

from typing import Optional

from precedent_summarizer.engine.summarize import CaseInput, user_message

VARIANTS = {"blind": "v1", "official": "v1o"}

OFFICIAL_NOTE = (
    "\n\n# 참고자료 (법원 작성)\n아래 판시사항·판결요지는 법원이 작성한 요지다. 쟁점과 판단을 빠뜨리지 않는 데 참고하되, "
    "모든 evidence는 반드시 <판례내용>에서만 복사한다(참고자료 문장을 인용하지 말 것).\n"
)


def has_official(holdings: Optional[str], official_summary: Optional[str]) -> bool:
    return bool((holdings or "").strip() or (official_summary or "").strip())


def build_user_message(c: CaseInput, variant: str, holdings: Optional[str] = None,
                       official_summary: Optional[str] = None) -> str:
    base = user_message(c)
    if variant == "blind" or not has_official(holdings, official_summary):
        return base
    ref = OFFICIAL_NOTE
    if holdings:
        ref += f"<판시사항>\n{holdings}\n</판시사항>\n"
    if official_summary:
        ref += f"<판결요지>\n{official_summary}\n</판결요지>\n"
    return base + ref
