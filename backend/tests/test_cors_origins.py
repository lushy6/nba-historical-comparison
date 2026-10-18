from app.main import LOCAL_ORIGINS, _allowed_origins


def test_defaults_to_local_origins(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert _allowed_origins() == LOCAL_ORIGINS


def test_env_origins_are_added_and_normalized(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " https://demo.example.app/ ,, https://b.example ")
    assert _allowed_origins() == [*LOCAL_ORIGINS, "https://demo.example.app", "https://b.example"]
