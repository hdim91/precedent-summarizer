from precedent_summarizer import config


def test_settings_repr_hides_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-0000000000")
    monkeypatch.setenv("LAW_API_KEY", "fakeoc0123456789")
    s = config.get_settings()
    r = repr(s)
    assert "fake-anthropic" not in r and "fakeoc" not in r


def test_missing_secret_message_has_name_only(monkeypatch):
    monkeypatch.setattr(config, "load_env", lambda: None)
    monkeypatch.delenv("LAW_API_KEY", raising=False)
    try:
        config.require_secret("LAW_API_KEY")
    except config.MissingSecretError as e:
        assert "LAW_API_KEY" in str(e)
    else:
        raise AssertionError("expected MissingSecretError")
