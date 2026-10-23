import logging

import requests

from precedent_summarizer.common.security import (
    MASK, MaskedRequestError, SecretMaskingFilter, mask_bytes, mask_secrets,
)

FAKE = "fakeoc0123456789"


def _url_with_key(k: str) -> str:
    return requests.Request("GET", "https://www.law.go.kr/DRF/lawSearch.do",
                            params={"OC": k, "target": "prec"}).prepare().url


def test_param_masking():
    out = mask_secrets("error for url: " + _url_with_key(FAKE))
    assert FAKE not in out and "OC=" + MASK in out and "target=prec" in out


def test_env_secret_masking(monkeypatch):
    monkeypatch.setenv("DUMMY_API_KEY", FAKE)
    assert FAKE not in mask_secrets(f"plain text {FAKE} here")


def test_short_or_nonsecret_env_not_masked(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL_DEFAULT", "claude-sonnet-5-5")
    assert "claude-sonnet-5-5" in mask_secrets("model claude-sonnet-5-5")


def test_bytes_masking_in_json_body():
    body = ('{"판례상세링크":"' + _url_with_key(FAKE).split("law.go.kr")[1] + '"}').encode("utf-8")
    assert FAKE.encode() not in mask_bytes(body)


def test_masked_request_error():
    e = MaskedRequestError(requests.HTTPError("404 for url: " + _url_with_key(FAKE)), status_code=404)
    assert FAKE not in str(e) and e.original_type == "HTTPError" and e.status_code == 404


def test_logging_filter(caplog):
    logger = logging.getLogger("t")
    caplog.handler.addFilter(SecretMaskingFilter())
    logger.warning("url=%s", _url_with_key(FAKE))
    assert FAKE not in caplog.text
