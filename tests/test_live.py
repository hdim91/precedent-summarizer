"""실제 API 호출 테스트 — 기본 제외. 실행: pytest -m live"""
import pytest

from precedent_summarizer.clients.law_go_kr import ORG_SUPREME_COURT, LawGoKrClient
from precedent_summarizer.common.security import mask_bytes
from precedent_summarizer.config import require_secret


@pytest.mark.live
def test_live_supreme_court_search_and_masking():
    key = require_secret("LAW_API_KEY")
    r = LawGoKrClient().search_precedents(org=ORG_SUPREME_COURT, display=1)
    j = r.json()["PrecSearch"]
    assert int(j["totalCnt"]) > 70000
    assert key.encode() not in mask_bytes(r.content)


@pytest.mark.live
def test_live_anthropic_models_available():
    from precedent_summarizer.clients.anthropic_client import make_client
    from precedent_summarizer.config import get_settings
    s = get_settings()
    c = make_client(s)
    for m in (s.model_default, s.model_complex):
        assert c.models.retrieve(m).id == m
