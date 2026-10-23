"""설정 로딩. 규칙: docs/RULES.md 1장.

- `.env`는 프로젝트 루트의 파일만 로드한다(상위 폴더 탐색 안 함 — 다른 프로젝트의 .env와 섞이지 않게).
- 비밀값 필드는 repr=False: 객체를 print/로그해도 값이 나오지 않는다.
- 키의 "존재 여부"만 외부에 노출한다: `secret_status()`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

REQUIRED_SECRETS = ("ANTHROPIC_API_KEY", "LAW_API_KEY")


class MissingSecretError(RuntimeError):
    """필수 키 누락. 메시지에는 변수명만 담는다."""


def load_env() -> None:
    """프로젝트 루트 .env를 환경변수로 로드(이미 설정된 환경변수는 덮어쓰지 않음)."""
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)


def secret_status(names: tuple[str, ...] = REQUIRED_SECRETS) -> dict[str, bool]:
    load_env()
    return {n: bool(os.environ.get(n)) for n in names}


def require_secret(name: str) -> str:
    load_env()
    val = os.environ.get(name)
    if not val:
        raise MissingSecretError(f"{name}가 설정되어 있지 않습니다. 프로젝트 루트 .env에 {name}=<값> 형태로 입력하세요.")
    return val


def _opt_float(name: str) -> Optional[float]:
    v = os.environ.get(name, "").strip()
    return float(v) if v else None


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(repr=False)
    law_api_key: str = field(repr=False)
    model_default: str = "claude-sonnet-5-5"
    model_complex: str = "claude-opus-5-5"
    batch_budget_usd: Optional[float] = None
    db_path: Path = PROJECT_ROOT / "data" / "precedents.sqlite"
    raw_cache_dir: Path = PROJECT_ROOT / "data" / "raw_cache"


def _path(name: str, default: Path) -> Path:
    v = os.environ.get(name, "").strip()
    if not v:
        return default
    p = Path(v)
    return p if p.is_absolute() else PROJECT_ROOT / p


def get_settings() -> Settings:
    load_env()
    return Settings(
        anthropic_api_key=require_secret("ANTHROPIC_API_KEY"),
        law_api_key=require_secret("LAW_API_KEY"),
        model_default=os.environ.get("CLAUDE_MODEL_DEFAULT") or Settings.model_default,
        model_complex=os.environ.get("CLAUDE_MODEL_COMPLEX") or Settings.model_complex,
        batch_budget_usd=_opt_float("BATCH_BUDGET_USD"),
        db_path=_path("DB_PATH", Settings.db_path),
        raw_cache_dir=_path("RAW_CACHE_DIR", Settings.raw_cache_dir),
    )
