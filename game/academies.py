"""
Academy system — Ferrari FDA, Red Bull Junior, Mercedes Junior, Alpine, Aston Martin, Williams.
Handles loading, benefits application, restrictions, joining/leaving.
"""

import json
import os
import random
from typing import Optional
from game.models import Academy

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "academies.json")
_academies_cache: Optional[dict] = None


def load_academies() -> dict:
    """Load academies.json and return {id: Academy}."""
    global _academies_cache
    if _academies_cache is not None:
        return _academies_cache
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = {}
    for a in data["academies"]:
        result[a["id"]] = Academy(
            id=a["id"],
            name=a["name"],
            short=a["short"],
            affiliated_team_f1=a.get("affiliated_team_f1"),
            pipeline_teams=a.get("pipeline_teams", []),
            benefits=a.get("benefits", {}),
            restrictions=a.get("restrictions", {}),
            prestige=a.get("prestige", 50),
            annual_stipend=a.get("annual_stipend", 0),
        )
    _academies_cache = result
    return result


def get_academy(academy_id: str) -> Optional[Academy]:
    return load_academies().get(academy_id)


# --- Benefits ---

def apply_salary_discount(base_salary: int, academy_id: Optional[str]) -> int:
    """Academy pays part of driver salary — reduces cost to team."""
    if not academy_id:
        return base_salary
    ac = get_academy(academy_id)
    if not ac:
        return base_salary
    discount = ac.benefits.get("salary_discount", 0.0)
    return int(base_salary * (1.0 - discount))


def apply_potential_bonus(driver, academy_id: Optional[str]) -> int:
    """Called at season end. Adds potential bonus from academy development."""
    if not academy_id:
        return 0
    ac = get_academy(academy_id)
    if not ac:
        return 0
    bonus = ac.benefits.get("potential_bonus_per_season", 0)
    driver.potential = min(99, driver.potential + bonus)
    return bonus


def get_dev_speed_bonus(academy_id: Optional[str]) -> float:
    """Returns development speed multiplier bonus (e.g. 0.15 = +15%)."""
    if not academy_id:
        return 0.0
    ac = get_academy(academy_id)
    return ac.benefits.get("development_speed_bonus", 0.0) if ac else 0.0


# FP1 por categoria é raríssimo nas bases e relevante só perto da F1.
FP1_SERIES_FACTOR = {
    "formula_4":        0.03,   # ~raríssimo
    "formula_regional": 0.10,
    "formula_3":        0.45,
    "formula_2":        1.00,   # campeão/reserva: chance real
    "formula_1":        0.00,   # titular de F1 não faz FP1 por superlicença
}


def roll_fp1_session(driver, academy_id: Optional[str], series_id: str = "formula_3") -> bool:
    """Sorteia se a academia consegue uma sessão de FP1 neste fim de semana.

    FP1 é raro para pilotos de base fracos e nulo para titulares de F1.
    """
    if not academy_id:
        return False
    ac = get_academy(academy_id)
    if not ac:
        return False
    base = ac.benefits.get("fp1_access_chance", 0.0)
    factor = FP1_SERIES_FACTOR.get(series_id, 0.3)
    # piloto fraco quase nunca é escolhido; bom piloto tem chance plena
    quality = max(0.0, min(1.0, (driver.overall - 55) / 25.0))
    chance = base * factor * (0.2 + 0.8 * quality)
    return random.random() < chance


# --- Restrictions ---

def can_sign_with_team(driver_academy_id: Optional[str], team_id: str) -> tuple[bool, str]:
    """
    Check if a driver in an academy can sign with a given F1 team.
    Returns (allowed: bool, reason: str).
    """
    if not driver_academy_id:
        return True, ""
    ac = get_academy(driver_academy_id)
    if not ac:
        return True, ""
    banned = ac.restrictions.get("cannot_sign_with", [])
    if team_id in banned:
        return False, f"{ac.name} proibe contrato com {team_id}"
    return True, ""


def buyout_fee(academy_id: Optional[str]) -> int:
    """Cost to leave academy before contract expires."""
    if not academy_id:
        return 0
    ac = get_academy(academy_id)
    return ac.restrictions.get("buyout_fee", 0) if ac else 0


def min_contract_years(academy_id: Optional[str]) -> int:
    if not academy_id:
        return 0
    ac = get_academy(academy_id)
    return ac.restrictions.get("min_contract_years", 1) if ac else 1


# --- Join / Leave ---

def join_academy(driver, academy_id: str, budget_ref: dict) -> tuple[bool, str]:
    """
    Attempt to have driver join academy.
    budget_ref is a mutable dict with key "budget" (team or player budget).
    Returns (success, message).
    """
    academies = load_academies()
    if academy_id not in academies:
        return False, "Academia nao encontrada"
    if driver.academy_id:
        return False, f"Ja faz parte de {driver.academy_id} — saia primeiro"
    driver.academy_id = academy_id
    return True, f"Bem-vindo a {academies[academy_id].name}!"


def leave_academy(driver, pay_buyout: bool, budget_ref: dict) -> tuple[bool, str]:
    """
    Leave current academy. If before contract ends, may require buyout fee.
    budget_ref["budget"] is the player's available funds.
    """
    if not driver.academy_id:
        return False, "Nao esta em nenhuma academia"
    ac = get_academy(driver.academy_id)
    if not ac:
        driver.academy_id = None
        return True, "Saiu da academia"
    fee = buyout_fee(driver.academy_id)
    if pay_buyout and fee > 0:
        if budget_ref.get("budget", 0) < fee:
            return False, f"Saldo insuficiente para buyout de R${fee:,}"
        budget_ref["budget"] -= fee
    old_name = ac.name
    driver.academy_id = None
    return True, f"Saiu de {old_name}" + (f" (buyout: ${fee:,})" if pay_buyout and fee else "")


def academy_info_display(academy_id: Optional[str]) -> dict:
    """Return dict for display in UI."""
    if not academy_id:
        return {}
    ac = get_academy(academy_id)
    if not ac:
        return {}
    return {
        "name": ac.name,
        "short": ac.short,
        "prestige": ac.prestige,
        "stipend": ac.annual_stipend,
        "salary_discount": ac.benefits.get("salary_discount", 0),
        "potential_bonus": ac.benefits.get("potential_bonus_per_season", 0),
        "dev_speed": ac.benefits.get("development_speed_bonus", 0),
        "fp1_chance": ac.benefits.get("fp1_access_chance", 0),
        "buyout": ac.restrictions.get("buyout_fee", 0),
        "min_years": ac.restrictions.get("min_contract_years", 1),
        "banned_teams": ac.restrictions.get("cannot_sign_with", []),
        "affiliated_f1": ac.affiliated_team_f1,
    }
