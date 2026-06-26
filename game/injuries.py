"""
Injury system — health tracking, probability per race, reserve substitution.
"""

import random
from typing import Optional, List

# Base probability per race for each severity (before modifiers)
BASE_INJURY_PROB = {
    "minor":    0.030,
    "moderate": 0.010,
    "serious":  0.002,
}

# Races missed per severity
RACES_MISSED = {
    "minor":    1,
    "moderate": 3,
    "serious":  6,
}

# Health damage per severity
HEALTH_DAMAGE = {
    "minor":    10,
    "moderate": 30,
    "serious":  60,
}

# Modifiers (multiplicative)
TRACK_TYPE_MODIFIERS = {
    "street":   1.4,
    "mixed":    1.1,
    "permanent": 0.9,
}

AGGRESSIVENESS_MODIFIER = {
    # driver.aggressiveness 1-10 → extra incident chance
    # High aggressiveness increases injury risk
}


def _aggressiveness_mod(aggressiveness: int) -> float:
    """Returns multiplier based on aggressiveness (1-10 scale)."""
    if aggressiveness <= 3:
        return 0.7
    if aggressiveness <= 6:
        return 1.0
    if aggressiveness <= 8:
        return 1.2
    return 1.5


def _health_mod(health: int) -> float:
    """Weakened drivers are more susceptible."""
    if health >= 90:
        return 0.8
    if health >= 70:
        return 1.0
    if health >= 50:
        return 1.3
    return 1.6


def roll_injury(driver, track_type: str = "permanent") -> Optional[str]:
    """
    Roll for injury this race. Returns severity string or None if uninjured.
    Does NOT modify driver — caller should call apply_injury() if result is not None.
    """
    if driver.is_injured:
        return None  # already out, handled separately

    track_mod = TRACK_TYPE_MODIFIERS.get(track_type, 1.0)
    agg_mod = _aggressiveness_mod(driver.aggressiveness)
    health_mod = _health_mod(driver.health)
    multiplier = track_mod * agg_mod * health_mod

    roll = random.random()
    # Check most severe first
    if roll < BASE_INJURY_PROB["serious"] * multiplier:
        return "serious"
    if roll < BASE_INJURY_PROB["moderate"] * multiplier:
        return "moderate"
    if roll < BASE_INJURY_PROB["minor"] * multiplier:
        return "minor"
    return None


def apply_injury(driver, severity: str) -> dict:
    """
    Apply injury to driver. Updates health, injury_type, injury_races_remaining.
    Returns event dict for UI display.
    """
    driver.health = max(0, driver.health - HEALTH_DAMAGE.get(severity, 10))
    driver.injury_type = severity
    driver.injury_races_remaining = RACES_MISSED.get(severity, 1)

    labels = {
        "minor":    "Lesao leve",
        "moderate": "Lesao moderada",
        "serious":  "Lesao grave",
    }
    descriptions = {
        "minor":    f"{driver.name} sofreu uma lesao leve e fica de fora por 1 corrida.",
        "moderate": f"{driver.name} sofreu uma lesao moderada. 3 corridas de ausencia.",
        "serious":  f"{driver.name} sofreu uma lesao grave! 6 corridas fora do grid.",
    }

    return {
        "driver_id": driver.id,
        "driver_name": driver.name,
        "severity": severity,
        "label": labels.get(severity, "Lesao"),
        "description": descriptions.get(severity, ""),
        "races_missed": RACES_MISSED.get(severity, 1),
        "health_after": driver.health,
    }


def find_reserve_driver(injured_driver, team_drivers: list, all_drivers: list):
    """
    Find the best available reserve to fill in for injured driver.
    Checks team drivers first, then pool of available (unsigned) drivers.
    Returns substitute driver or None.
    """
    # Look for a second team driver who is healthy
    for d in team_drivers:
        if d.id != injured_driver.id and not d.is_injured:
            return d

    # Try unsigned drivers in the pool
    reserves = [d for d in all_drivers
                if d.team_id is None and not d.is_injured]
    if not reserves:
        return None
    # Pick the one closest in ability to the injured driver
    target_overall = injured_driver.overall
    reserves.sort(key=lambda d: abs(d.overall - target_overall))
    return reserves[0]


def process_recovery(driver) -> dict:
    """
    Call at start of each race week for injured drivers.
    Advances recovery countdown, restores health.
    Returns event dict with recovery status.
    """
    if not driver.is_injured:
        return {"recovered": True, "races_remaining": 0}

    driver.injury_races_remaining -= 1
    health_gain = 25
    driver.health = min(100, driver.health + health_gain)

    if driver.injury_races_remaining <= 0:
        driver.health = 100
        driver.injury_type = ""
        return {
            "driver_id": driver.id,
            "driver_name": driver.name,
            "recovered": True,
            "races_remaining": 0,
            "description": f"{driver.name} esta recuperado e pronto para voltar!",
        }
    return {
        "driver_id": driver.id,
        "driver_name": driver.name,
        "recovered": False,
        "races_remaining": driver.injury_races_remaining,
        "health": driver.health,
        "description": f"{driver.name} ainda em recuperacao. {driver.injury_races_remaining} corrida(s) restantes.",
    }


def injury_report(driver) -> str:
    """One-line status string for display."""
    if not driver.is_injured:
        return f"Saude: {driver.health}% — Apto"
    labels = {"minor": "leve", "moderate": "moderada", "serious": "grave"}
    lbl = labels.get(driver.injury_type, driver.injury_type)
    return (f"Saude: {driver.health}% — Lesao {lbl} "
            f"({driver.injury_races_remaining} corrida(s) ausente)")
