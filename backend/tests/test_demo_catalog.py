"""A fresh checkout must support the documented fictional demo without external data."""

from pathlib import Path
import runpy

from app.catalog import DatasetCatalog
from app.resolver import SchemaResolver


def test_fictional_demo_loads_through_the_real_resolver(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/create_demo.py"
    build = runpy.run_path(str(script))["build"]
    destination = tmp_path / "demo"
    build(destination)
    resolver = SchemaResolver(DatasetCatalog(tmp_path / "absent.sqlite", historical_data_path=destination))
    players = resolver.resolve_player_seasons().frame
    teams = resolver.resolve_team_seasons().frame
    assert len(players) == 24
    assert len(teams) == 8
    assert players["profile_id"].is_unique
    assert set(players["team_codes"]) == {"AUR", "HBR"}
    assert "Aster Guard" in set(players["name"])
