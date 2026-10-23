"""Anthropic 클라이언트 생성(단일 진입점). 키·헤더는 로그에 남기지 않는다(RULES 1-3)."""
from __future__ import annotations

import anthropic

from precedent_summarizer.config import Settings, get_settings


def make_client(settings: Settings | None = None) -> anthropic.Anthropic:
    s = settings or get_settings()
    headers = {"anthropic-workspace-id": s.anthropic_workspace_id} if s.anthropic_workspace_id else None
    return anthropic.Anthropic(api_key=s.anthropic_api_key, default_headers=headers)
