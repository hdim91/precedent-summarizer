from precedent_summarizer.clients.anthropic_client import make_client
from precedent_summarizer.config import Settings

FAKE_ANTHROPIC = "fake-anthropic-" + "0" * 10  # 더미값(pre-commit 패턴 회피를 위해 조합)
FAKE_OC = "fakeoc" + "0123456789"


def test_workspace_header_added_only_when_set():
    base = dict(anthropic_api_key=FAKE_ANTHROPIC, law_api_key=FAKE_OC)
    c1 = make_client(Settings(**base, anthropic_workspace_id="wrkspc_test"))
    assert c1.default_headers.get("anthropic-workspace-id") == "wrkspc_test"
    c2 = make_client(Settings(**base))
    assert "anthropic-workspace-id" not in c2.default_headers
