"""배치 단가·토큰 추정 (Claude 소유).

단가: Claude Platform 가격표(2026-10-23 확인) Batch API = 표준의 50%.
  https://platform.claude.com/docs/en/about-claude/pricing
토큰 추정식: 2026-10-23~24 시범·비교 시험 요약 74개(판결 39건) 실측(한국어 본문 ≈ 1토큰/자, 출력에 내부 추론 포함).
"""
from __future__ import annotations

# 1M 토큰당 USD (batch): input, output, cache_read, cache_write_5m
BATCH_PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-sonnet-5-5": (1.0, 5.0, 0.05, 1.25),
    "claude-opus-5-5": (2.0, 10.0, 0.10, 2.50),
}
SYSTEM_TOKENS = 4700        # 시스템 프롬프트 + 스키마(캐시 대상)
META_TOKENS = 250
SAFETY = 1.15               # 추정치 상향 보정(실측 분산 대비)


def est_tokens(chars: int, extra_chars: int = 0) -> tuple[int, int]:
    """(입력, 출력) 토큰 추정. extra_chars: 판시사항·판결요지 등 추가 입력."""
    inp = int(chars + extra_chars + META_TOKENS)
    out = int(min(16000, 1200 + 0.42 * chars))
    return inp, out


def est_cost(model: str, chars: int, extra_chars: int = 0) -> float:
    pi, po, _pr, pw = BATCH_PRICES[model]
    inp, out = est_tokens(chars, extra_chars)
    # 배치에서는 캐시 적중이 보장되지 않으므로 시스템 프롬프트를 캐시 쓰기 단가로 보수 계산
    return SAFETY * (inp * pi + SYSTEM_TOKENS * pw + out * po) / 1e6


def actual_cost(model: str, usage: dict) -> float:
    pi, po, pr, pw = BATCH_PRICES[model]
    return (usage.get("input_tokens", 0) * pi + usage.get("output_tokens", 0) * po
            + usage.get("cache_read_input_tokens", 0) * pr
            + usage.get("cache_creation_input_tokens", 0) * pw) / 1e6
