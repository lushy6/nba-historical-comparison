from app.main import _searchable_text


def test_searchable_text_matches_accentless_player_queries() -> None:
    assert _searchable_text("Nikola Jokić") == "nikola jokic"
