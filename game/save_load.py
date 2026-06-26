import json
import os
import sys
import dataclasses
from datetime import datetime
from typing import Optional
from .models import Driver, Team, Season, SeasonRound
from .player_profile import PlayerProfile, CareerEntry

# Quando empacotado como .exe, salva ao lado do executável.
# Em desenvolvimento, salva em ../saves relativo ao módulo.
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.join(os.path.dirname(__file__), "..")

SAVES_DIR = os.path.join(_BASE_DIR, "saves")
SAVE_VERSION = "0.4"


def _to_dict(obj):
    if dataclasses.is_dataclass(obj):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _driver_defaults(d: dict) -> dict:
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
    return d


def _team_defaults(t: dict) -> dict:
    t.setdefault("academy",        None)
    t.setdefault("fac_factory",    1)
    t.setdefault("fac_simulator",  1)
    t.setdefault("fac_r_and_d",    1)
    t.setdefault("fac_pit_crew",   1)
    t.setdefault("fac_marketing",  1)
    t.setdefault("is_player_team", False)
    t.setdefault("drivers",        [])
    t.setdefault("season_points",  0)
    t.setdefault("season_wins",    0)
    t.setdefault("season_podiums", 0)
    return t


def _season_from_dict(s: dict, teams, drivers) -> Season:
    rounds = [SeasonRound(**r) for r in s["rounds"]]
    return Season(
        year=s["year"], series_id=s["series_id"],
        series_name=s["series_name"], rounds=rounds,
        current_round=s["current_round"],
        teams=teams, drivers=drivers,
    )


# ── Driver Career ─────────────────────────────────────────────────────────────

def save_driver_career(profile: PlayerProfile, career, slot: str = "save1") -> str:
    from .driver_career import DriverCareer
    os.makedirs(SAVES_DIR, exist_ok=True)
    path = os.path.join(SAVES_DIR, f"{slot}.json")
    pd = career.player_driver
    data = {
        "version":           SAVE_VERSION,
        "saved_at":          datetime.now().isoformat(),
        "slot":              slot,
        "game_mode":         "driver",
        "profile":           _to_dict(profile),
        "career_year":       career.career_year,
        "current_series_id": career.current_series_id,
        "season_number":     career.season_number,
        "player_driver":     _to_dict(pd) if pd else None,
        "current_team_id":   career.current_team.id if career.current_team else None,
        "all_drivers":       [_to_dict(d) for d in career.all_drivers],
        "all_teams":         [_to_dict(t) for t in career.all_teams],
        "season":            _to_dict(career.season) if career.season else None,
        "series_rules":      career.series_rules,
        "standings_drivers":       career.standings_drivers,
        "standings_teams":         career.standings_teams,
        "injury_log":              career.injury_log,
        "news_feed":               getattr(career, "news_feed", []),
        "npc_state":               getattr(career, "_npc_state", {}),
        "contract_next_year":      getattr(career, "_contract_next_year", None),
        "contract_next_series":    getattr(career, "_contract_next_series", None),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_driver_career(slot: str = "save1"):
    from .driver_career import DriverCareer
    path = os.path.join(SAVES_DIR, f"{slot}.json")
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("game_mode") != "driver":
        return None, None

    p = data["profile"]
    profile = PlayerProfile(
        name=p["name"], age=p["age"], nationality=p["nationality"],
        mode=p.get("mode", "driver"),
        personal_money=p.get("personal_money", 0),
        reputation=p.get("reputation", 30),
        history=[CareerEntry(**h) for h in p.get("history", [])],
        driver_id=p.get("driver_id"),
        team_id=p.get("team_id"),
        housing=p.get("housing", "origin"),
    )

    career = DriverCareer(profile)
    career.career_year            = data["career_year"]
    career.current_series_id      = data["current_series_id"]
    career.season_number          = data["season_number"]
    career.series_rules           = data["series_rules"]
    career.standings_drivers      = data["standings_drivers"]
    career.standings_teams        = data["standings_teams"]
    career.injury_log             = data.get("injury_log", [])
    career.news_feed              = data.get("news_feed", [])
    career._npc_state             = data.get("npc_state", {})
    career._contract_next_year    = data.get("contract_next_year")
    career._contract_next_series  = data.get("contract_next_series")

    career.all_drivers = [Driver(**_driver_defaults(d)) for d in data["all_drivers"]]
    career.all_teams   = [Team(**_team_defaults(t))     for t in data["all_teams"]]

    if data.get("player_driver"):
        pd = Driver(**_driver_defaults(data["player_driver"]))
        # Replace or append
        existing = next((d for d in career.all_drivers if d.id == pd.id), None)
        if existing:
            career.all_drivers[career.all_drivers.index(existing)] = pd
        else:
            career.all_drivers.append(pd)
        career.player_driver = pd
    else:
        # fallback p/ saves antigos: usa driver_id do perfil
        career.player_driver = next(
            (d for d in career.all_drivers if d.id == profile.driver_id), None)
    if career.player_driver is None:
        return None, None   # save incompatível

    career.current_team = next(
        (t for t in career.all_teams if t.id == data.get("current_team_id")), None)
    if career.current_team is None:
        career.current_team = next(
            (t for t in career.all_teams if career.player_driver.id in t.drivers), None)

    if data.get("season"):
        career.season = _season_from_dict(
            data["season"], career.all_teams, career.all_drivers)

    return profile, career


# ── Manager Career ────────────────────────────────────────────────────────────

def save_manager_career(profile: PlayerProfile, career, slot: str = "save1") -> str:
    os.makedirs(SAVES_DIR, exist_ok=True)
    path = os.path.join(SAVES_DIR, f"{slot}.json")
    data = {
        "version":           SAVE_VERSION,
        "saved_at":          datetime.now().isoformat(),
        "slot":              slot,
        "game_mode":         "manager",
        "profile":           _to_dict(profile),
        "career_year":       career.career_year,
        "current_series_id": career.current_series_id,
        "season_number":     career.season_number,
        "player_team_id":    career.player_team.id if career.player_team else None,
        "all_drivers":       [_to_dict(d) for d in career.all_drivers],
        "all_teams":         [_to_dict(t) for t in career.all_teams],
        "season":            _to_dict(career.season) if career.season else None,
        "series_rules":      career.series_rules,
        "standings_drivers": career.standings_drivers,
        "standings_teams":   career.standings_teams,
        "injury_log":        career.injury_log,
        "news_feed":         getattr(career, "news_feed", []),
        "npc_state":         getattr(career, "_npc_state", {}),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_manager_career(slot: str = "save1"):
    from .manager_career import ManagerCareer
    path = os.path.join(SAVES_DIR, f"{slot}.json")
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("game_mode") != "manager":
        return None, None

    p = data["profile"]
    profile = PlayerProfile(
        name=p["name"], age=p["age"], nationality=p["nationality"],
        mode=p.get("mode", "manager"),
        personal_money=p.get("personal_money", 0),
        reputation=p.get("reputation", 30),
        history=[CareerEntry(**h) for h in p.get("history", [])],
        driver_id=p.get("driver_id"),
        team_id=p.get("team_id"),
        housing=p.get("housing", "origin"),
    )

    career = ManagerCareer(profile)
    career.career_year       = data["career_year"]
    career.current_series_id = data["current_series_id"]
    career.season_number     = data["season_number"]
    career.series_rules      = data["series_rules"]
    career.standings_drivers = data["standings_drivers"]
    career.standings_teams   = data["standings_teams"]
    career.injury_log        = data.get("injury_log", [])
    career.news_feed         = data.get("news_feed", [])
    career._npc_state        = data.get("npc_state", {})

    career.all_drivers = [Driver(**_driver_defaults(d)) for d in data["all_drivers"]]
    career.all_teams   = [Team(**_team_defaults(t))     for t in data["all_teams"]]
    # Resolve a equipe do jogador, com fallbacks p/ saves antigos
    career.player_team = next(
        (t for t in career.all_teams if t.id == data.get("player_team_id")), None)
    if career.player_team is None:
        career.player_team = next(
            (t for t in career.all_teams if t.is_player_team), None)
    if career.player_team is None and career.all_teams:
        career.player_team = career.all_teams[0]
    if career.player_team is None:
        return None, None   # save incompatível
    career.player_team.is_player_team = True

    if data.get("season"):
        career.season = _season_from_dict(
            data["season"], career.all_teams, career.all_drivers)

    return profile, career


# ── Genérico ──────────────────────────────────────────────────────────────────

def save_game(profile: PlayerProfile, career, slot: str = "save1") -> str:
    mode = profile.mode
    if mode in ("driver", "manager_turned_driver"):
        return save_driver_career(profile, career, slot)
    return save_manager_career(profile, career, slot)


def load_game(slot: str = "save1"):
    """Retorna (profile, career) ou (None, None) se falhar."""
    path = os.path.join(SAVES_DIR, f"{slot}.json")
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    mode = data.get("game_mode", "manager")
    if mode == "driver":
        return load_driver_career(slot)
    return load_manager_career(slot)


def list_saves() -> list:
    if not os.path.exists(SAVES_DIR):
        return []
    result = []
    for fname in os.listdir(SAVES_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(SAVES_DIR, fname)
        with open(path, encoding="utf-8") as fp:
            d = json.load(fp)
        p = d.get("profile", {})
        result.append({
            "slot":     fname.replace(".json", ""),
            "saved_at": d.get("saved_at", "?"),
            "mode":     d.get("game_mode", "?"),
            "name":     p.get("name", "?"),
            "year":     d.get("career_year", "?"),
            "series":   d.get("current_series_id", "?"),
            "version":  d.get("version", "?"),
        })
    return result
