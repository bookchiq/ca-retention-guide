import logging

from src import config

FAKE_TOKEN = "fedcba9876543210fedcba9876543210fedcba98"  # gitleaks:allow (test value)


def test_token_status_present_without_revealing_value(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("COURTLISTENER_TOKEN", FAKE_TOKEN)
    caplog.set_level(logging.DEBUG)
    settings = config.load(repo_root=tmp_path)
    status = settings.token_status()
    logging.getLogger("test").info("settings: %r status: %s", settings, status)
    assert status == "present"
    assert FAKE_TOKEN not in status
    assert FAKE_TOKEN not in repr(settings)
    assert FAKE_TOKEN not in caplog.text


def test_token_status_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("COURTLISTENER_TOKEN", raising=False)
    settings = config.load(repo_root=tmp_path)
    assert settings.token_status() == "missing"


def test_token_read_from_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("COURTLISTENER_TOKEN", raising=False)
    (tmp_path / ".env").write_text(f"COURTLISTENER_TOKEN={FAKE_TOKEN}\nCL_CONTACT_EMAIL=a@b.org\n")
    settings = config.load(repo_root=tmp_path)
    assert settings.token_status() == "present"
    assert settings.contact_email == "a@b.org"


def test_yaml_values_loaded(tmp_path, monkeypatch):
    monkeypatch.delenv("COURTLISTENER_TOKEN", raising=False)
    (tmp_path / "config.yaml").write_text("window:\n  start: '2023-01-01'\n")
    settings = config.load(repo_root=tmp_path)
    assert settings.raw["window"]["start"] == "2023-01-01"
