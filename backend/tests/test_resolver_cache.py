import app.main as main


class CountingResolver:
    def __init__(self) -> None:
        self.player_calls = 0

    def resolve_player_seasons(self) -> object:
        self.player_calls += 1
        return object()


def test_cached_season_frame_reuses_a_resolved_source(monkeypatch) -> None:
    resolver = CountingResolver()
    main._cached_season_frame.cache_clear()
    monkeypatch.setattr(main, "_resolver", lambda: resolver)

    first = main._cached_season_frame("player", ("historical_csv", "fixture"))
    second = main._cached_season_frame("player", ("historical_csv", "fixture"))

    assert first is second
    assert resolver.player_calls == 1
