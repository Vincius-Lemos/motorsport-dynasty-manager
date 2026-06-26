"""
Utilitários compartilhados entre DriverCareer e ManagerCareer.
Carregamento de dados JSON, progressão de categorias, atribuição de pilotos da IA.
"""
import json
import os
import random
from typing import Dict, List, Optional
from .models import Driver, Team, SeasonRound, Season

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SERIES_PROGRESSION = [
    "formula_4",
    "formula_regional",
    "formula_3",
    "formula_2",
    "formula_1",
]

SERIES_DRIVER_FILES = {
    "formula_4":        "drivers_formula_4.json",
    "formula_regional": "drivers_formula_regional.json",
    "formula_3":        "drivers_formula_3.json",
    "formula_2":        "drivers_formula_2.json",
    "formula_1":        "drivers_formula_1.json",
}

SERIES_TEAM_FILES = {
    "formula_4":        "teams_formula_4.json",
    "formula_regional": "teams_formula_regional.json",
    "formula_3":        "teams_formula_3.json",
    "formula_2":        "teams_formula_2.json",
    "formula_1":        "teams_formula_1.json",
}


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_series(series_id: str) -> dict:
    return load_json(os.path.join(DATA_DIR, "series", f"{series_id}.json"))


def load_calendar(series_id: str) -> list:
    return load_json(
        os.path.join(DATA_DIR, "tracks", f"calendar_{series_id}.json")
    )["rounds"]


# Faixa de pontos de Super Licença plausível por categoria (NPCs).
# Garante que F1 nunca fique sem pilotos elegíveis (>=40) e dá um gradiente realista.
NPC_SL_RANGE = {
    "formula_1":        (40, 85),
    "formula_2":        (22, 48),
    "formula_3":        (10, 28),
    "formula_regional": (3, 15),
    "formula_4":        (0, 8),
}


# Faixa salarial anual (EUR) realista por categoria. Mapeada pelo overall do piloto.
SALARY_BAND = {
    "formula_4":        (20_000,    150_000),
    "formula_regional": (60_000,    400_000),
    "formula_3":        (150_000,   800_000),
    "formula_2":        (400_000,   2_000_000),
    "formula_1":        (1_000_000, 45_000_000),
}


def realistic_salary(series_id: str, overall: float) -> int:
    """Salário coerente com a categoria e a habilidade do piloto."""
    lo, hi = SALARY_BAND.get(series_id, (20_000, 200_000))
    frac = max(0.0, min(1.0, (overall - 55) / 35.0))
    # curva: estrelas ganham desproporcionalmente mais (sobretudo na F1)
    frac = frac ** 1.6
    val = lo + frac * (hi - lo)
    # arredonda para milhares
    return int(round(val / 1000.0)) * 1000


def _seed_npc(driver: Driver, series_id: str, year: int):
    """Dá Super Licença, salário coerente e envelhece o NPC pelo ano de carreira."""
    import random as _r
    lo, hi = NPC_SL_RANGE.get(series_id, (0, 10))
    # determinístico por id+ano para estabilidade dentro da mesma temporada
    seed = (hash(driver.id) ^ (year * 2654435761)) & 0xFFFFFFFF
    rng = _r.Random(seed)
    driver.super_licence_points = rng.randint(lo, hi)
    driver.experience = rng.randint(40, 400)
    # Progressão pelo número de anos desde o início (mundo vivo)
    offset = max(0, year - 2027)
    for _ in range(min(offset, 6)):
        driver.age_up()
    # Salário coerente com categoria/habilidade (+/- 12% de variação)
    band_lo, band_hi = SALARY_BAND.get(series_id, (20_000, 200_000))
    base = realistic_salary(series_id, driver.overall)
    sal = int(base * rng.uniform(0.88, 1.12) / 1000) * 1000
    driver.salary = max(band_lo, min(band_hi, sal))


def load_drivers_for_series(series_id: str, year: int = 2027) -> List[Driver]:
    fname = SERIES_DRIVER_FILES[series_id]
    raw = load_json(os.path.join(DATA_DIR, "drivers", fname))
    drivers = []
    for d in raw["drivers"]:
        d.setdefault("super_licence_points",    0)
        d.setdefault("sl_points_history",       {})
        d.setdefault("fp1_sessions",            0)
        d.setdefault("academy_id",              None)
        d.setdefault("health",                  100)
        d.setdefault("injury_races_remaining",  0)
        d.setdefault("injury_type",             "")
        d.setdefault("series_history",          [])
        d.setdefault("experience",              0)
        d.setdefault("races_completed",         0)
        d.setdefault("team_id",                 None)
        d.setdefault("contract_years",          0)
        d.setdefault("total_points",            0)
        d.setdefault("total_wins",              0)
        d.setdefault("total_podiums",           0)
        drv = Driver(**d)
        _seed_npc(drv, series_id, year)
        drivers.append(drv)
    return drivers


def load_teams_for_series(series_id: str) -> List[Team]:
    fname = SERIES_TEAM_FILES[series_id]
    raw = load_json(os.path.join(DATA_DIR, "teams", fname))
    teams = []
    for t in raw["teams"]:
        t.setdefault("academy",       None)
        t.setdefault("fac_factory",   1)
        t.setdefault("fac_simulator", 1)
        t.setdefault("fac_r_and_d",   1)
        t.setdefault("fac_pit_crew",  1)
        t.setdefault("fac_marketing", 1)
        t.setdefault("is_player_team", False)
        t.setdefault("drivers",        [])
        t.setdefault("season_points",  0)
        t.setdefault("season_wins",    0)
        t.setdefault("season_podiums", 0)
        teams.append(Team(**t))
    return teams


def build_season(series_id: str, year: int, series_rules: dict,
                 all_teams: List[Team], all_drivers: List[Driver]) -> Season:
    cal = load_calendar(series_id)
    rounds = [SeasonRound(
        round_number=r["round"],
        track_name=r["name"],
        country=r["country"],
        laps=r["laps"],
        length_km=r["length_km"],
        track_type=r["type"],
        overtaking_index=r["overtaking"],
        tyre_wear_index=r["tyre_wear"],
    ) for r in cal]
    return Season(
        year=year,
        series_id=series_id,
        series_name=series_rules["name"],
        rounds=rounds,
        teams=all_teams,
        drivers=all_drivers,
    )


def assign_ai_drivers(all_teams: List[Team], all_drivers: List[Driver],
                      exclude_ids: List[str]):
    """Fill non-excluded teams with available drivers (2 per team)."""
    available = [d for d in all_drivers if d.id not in exclude_ids]
    random.shuffle(available)
    ai_teams = [t for t in all_teams if not t.is_player_team]
    idx = 0
    for t in ai_teams:
        t.drivers = []
        for _ in range(2):
            if idx < len(available):
                available[idx].team_id = t.id
                available[idx].contract_years = random.randint(1, 2)
                t.drivers.append(available[idx].id)
                idx += 1


def series_above(sid: str) -> Optional[str]:
    idx = SERIES_PROGRESSION.index(sid) if sid in SERIES_PROGRESSION else -1
    return SERIES_PROGRESSION[idx + 1] if 0 <= idx < len(SERIES_PROGRESSION) - 1 else None


def series_below(sid: str) -> Optional[str]:
    idx = SERIES_PROGRESSION.index(sid) if sid in SERIES_PROGRESSION else -1
    return SERIES_PROGRESSION[idx - 1] if idx > 0 else None


def prize_money(position: int) -> int:
    table = {1: 500_000, 2: 350_000, 3: 250_000, 4: 180_000, 5: 130_000}
    return table.get(position, max(0, 100_000 - position * 8_000))


# ── Race weekend format per series ─────────────────────────────────────────────

RACE_WEEKEND_FORMAT = {
    "formula_1":        "single",         # feature race only (sprint weekends not modelled yet)
    "formula_2":        "sprint_feature", # qualifying → sprint (reverse grid) → feature
    "formula_3":        "sprint_feature",
    "formula_regional": "single",
    "formula_4":        "single",
}

# Sprint race scoring — shorter race, fewer points
SPRINT_SCORING = {
    "formula_2": [8, 7, 6, 5, 4, 3, 2, 1, 0, 0],
    "formula_3": [6, 5, 4, 3, 2, 1, 0, 0, 0, 0],
}

# Feature race scoring — same as standard F1 table
FEATURE_SCORING = {
    "formula_2": [25, 18, 15, 12, 10, 8, 6, 4, 2, 1],
    "formula_3": [25, 18, 15, 12, 10, 8, 6, 4, 2, 1],
}

# How many qualifiers are reversed for the sprint grid
SPRINT_REVERSE_TOP = {
    "formula_2": 8,
    "formula_3": 8,
}


def sprint_grid_from_quali(quali_order: list, series_id: str) -> list:
    """Return sprint start grid: top N reversed, rest in quali order."""
    n = SPRINT_REVERSE_TOP.get(series_id, 8)
    top = list(reversed(quali_order[:n]))
    rest = list(quali_order[n:])
    return top + rest
