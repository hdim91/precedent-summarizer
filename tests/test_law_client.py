import traceback

import pytest
import requests

from precedent_summarizer.clients.law_go_kr import (
    ORG_SUPREME_COURT, SEARCH_URL, LawGoKrClient, save_raw_response,
)
from precedent_summarizer.common.security import MaskedRequestError

FAKE = "fakeoc0123456789"


class FakeResp:
    def __init__(self, status=200, content=b"{}", url=""):
        self.status_code, self.content, self.url = status, content, url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error for url: {self.url}")


class FakeSession:
    def __init__(self, resp):
        self.resp, self.calls = resp, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params)))
        self.resp.url = requests.Request("GET", url, params=params).prepare().url
        return self.resp


def client(resp):
    return LawGoKrClient(oc=FAKE, session=FakeSession(resp), max_retries=2,
                         retry_backoff_sec=0, min_interval_sec=0)


def test_https_and_params():
    c = client(FakeResp())
    c.search_precedents(org=ORG_SUPREME_COURT, date_from="20250101", date_to="20251231", page=3)
    url, p = c.session.calls[0]
    assert url == SEARCH_URL and url.startswith("https://")
    assert p["OC"] == FAKE and p["org"] == "400201" and p["prncYd"] == "20250101~20251231" and p["page"] == 3
    assert "query" not in p


def test_error_is_masked_and_chain_cut():
    c = client(FakeResp(status=404))
    with pytest.raises(MaskedRequestError) as ei:
        c.search_precedents()
    tb = "".join(traceback.format_exception(ei.type, ei.value, ei.tb))
    assert FAKE not in tb and ei.value.status_code == 404
    assert ei.value.__cause__ is None and ei.value.__suppress_context__


def test_client_repr_hides_key():
    assert FAKE not in repr(client(FakeResp()))


def test_save_raw_masks_and_is_immutable(tmp_path):
    link = requests.Request("GET", "https://x/DRF/lawService.do", params={"OC": FAKE, "ID": "1"}).prepare().url
    out = save_raw_response(FakeResp(content=f'{{"link":"{link}"}}'.encode()), tmp_path / "a.json")
    assert FAKE.encode() not in out.read_bytes()
    save_raw_response(FakeResp(content=b"NEW"), out)
    assert out.read_bytes() != b"NEW"


def test_date_range_requires_both():
    with pytest.raises(ValueError):
        client(FakeResp()).search_precedents(date_from="20250101")
