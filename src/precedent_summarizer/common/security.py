"""비밀값 마스킹. 규칙: docs/RULES.md 1-3.

law.go.kr Open API는 인증키(OC)를 URL 쿼리 파라미터로 받고, **검색 응답 본문의 `판례상세링크`에도
요청한 OC 값을 그대로 넣어 돌려준다**(2026-10-23 실측). 따라서
  (1) requests 예외 메시지("... for url: ...?OC=<키>")
  (2) 응답 본문(raw 캐시)
  (3) 로그
모두 저장·출력 전에 이 모듈을 거쳐야 한다.
"""
from __future__ import annotations

import logging
import os
import re

MASK = "***"
_PARAM_NAMES = r"(?:OC|KEY|serviceKey|api_key|apikey|access_token)"
_PARAM_RE = re.compile(r"(?i)([?&]" + _PARAM_NAMES + r"=)[^&\s\"'<>]+")
_PARAM_RE_B = re.compile(rb"(?i)([?&]" + _PARAM_NAMES.encode() + rb"=)[^&\s\"'<>]+")
_SECRET_NAME_HINTS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")
_MIN_SECRET_LEN = 8


def _env_secrets() -> list[str]:
    vals = {
        v for n, v in os.environ.items()
        if v and len(v) >= _MIN_SECRET_LEN and any(h in n.upper() for h in _SECRET_NAME_HINTS)
    }
    return sorted(vals, key=len, reverse=True)


def mask_secrets(text: str) -> str:
    """URL 파라미터 형태의 키 + 환경변수에 있는 비밀값을 모두 MASK로 치환."""
    text = _PARAM_RE.sub(lambda m: m.group(1) + MASK, text)
    for v in _env_secrets():
        text = text.replace(v, MASK)
    return text


def mask_bytes(data: bytes) -> bytes:
    """응답 본문(bytes) 마스킹. 인코딩과 무관하게 바이트 단위로 처리."""
    out = _PARAM_RE_B.sub(lambda m: m.group(1) + MASK.encode(), data)
    for v in _env_secrets():
        out = out.replace(v.encode("utf-8"), MASK.encode())
    return out


class MaskedRequestError(Exception):
    """원 예외의 타입명과 마스킹된 메시지만 보관. 호출부는 `raise MaskedRequestError(e) from None`으로
    원 예외 체인(키가 든 URL 포함)을 끊는다."""

    def __init__(self, original: BaseException, *, status_code: int | None = None):
        self.original_type = type(original).__name__
        self.status_code = status_code
        super().__init__(f"{self.original_type}: {mask_secrets(str(original))}")


class SecretMaskingFilter(logging.Filter):
    """핸들러에 붙여 모든 로그 레코드의 메시지·예외 텍스트를 마스킹."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_secrets(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = mask_secrets(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def install_log_masking(level: int = logging.INFO) -> None:
    """루트 로거의 모든 핸들러에 마스킹 필터 설치(핸들러가 없으면 기본 핸들러 생성)."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level)
    for h in root.handlers:
        if not any(isinstance(f, SecretMaskingFilter) for f in h.filters):
            h.addFilter(SecretMaskingFilter())
