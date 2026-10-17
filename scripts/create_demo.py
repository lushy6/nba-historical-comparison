"""Generate a tiny fictional catalog; never downloads or imitates real player records."""

import csv
from pathlib import Path


def build(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tables = {name: [] for name in (
        "Player Totals", "Advanced", "Player Per Game", "Team Summaries", "Team Abbrev"
    )}
    teams = [("AUR", "Aurora Comets"), ("HBR", "Harbor Pilots")]
    names = ["Aster Guard", "Beacon Wing", "Cedar Center", "Dune Forward", "Ember Guard", "Fern Wing"]
    for year_index, season in enumerate((2018, 2020, 2022, 2024)):
        for code, name in teams:
            tables["Team Abbrev"].append(dict(season=season, lg="NBA", team=name, abbreviation=code, playoffs=0))
            home = code == "AUR"
            offense = 108 + year_index * 2 + int(home)
            defense = 106 + year_index + int(not home)
            tables["Team Summaries"].append(dict(
                season=season, lg="NBA", team=name, abbreviation=code, playoffs=0,
                e_fg_percent=0.50 + year_index * 0.01 + int(home) * 0.005,
                tov_percent=12 + year_index * 0.2, orb_percent=24 + year_index,
                f_tr=0.20 + year_index * 0.005, o_rtg=offense, d_rtg=defense,
                n_rtg=offense-defense, pace=96 + year_index,
            ))
        for index, name in enumerate(names):
            code = teams[index % 2][0]
            common = dict(season=season, lg="NBA", player=name, player_id=f"fictional{index:02}", team=code)
            fg = 350 + index * 25 + year_index * 12
            fga = fg * 2 + index * 10
            three = 40 + index * 20 + year_index * 5
            ft = 100 + index * 15
            tables["Player Totals"].append(dict(
                **common, fg=fg, fga=fga, x3p=three, x3pa=three*3, ft=ft, fta=ft+30,
                trb=220+index*45, ast=130+index*35+year_index*15,
                stl=50+index*8, blk=20+index*10, tov=80+index*12,
                pts=2*fg+three+ft,
            ))
            tables["Advanced"].append(dict(
                **common, mp=1900+index*90, per=15+index+year_index*0.3,
                ts_percent=0.53+index*0.008, usg_percent=19+index,
                ws=3+index*0.8, bpm=-1+index*0.6, vorp=0.2+index*0.4,
            ))
            tables["Player Per Game"].append(dict(**common, e_fg_percent=(fg+0.5*three)/fga))
    for name, rows in tables.items():
        with (directory / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    build(Path(__file__).resolve().parents[1] / "data/demo")
    print("Created data/demo: 24 fictional player seasons and 8 fictional team seasons.")
