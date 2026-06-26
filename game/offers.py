"""
Dynamic offer system — score-based opportunity resolver.

Types:
  step_up       — team in a higher category wants you
  step_down     — team in a lower category (better conditions)
  lateral_better — different team in same category, better car
  lateral_worse  — different team in same category, higher salary
  fired          — your current team is dropping you mid-season
"""
import random
from typing import Optional, List
from .models import Team, Driver
from .career import SERIES_PROGRESSION, load_series, load_teams_for_series
from . import super_licence as sl
from .i18n import t as _t

OFFER_CHANCE_PER_RACE = 0.30   # base 30 % chance after each race

# Tipos de desligamento
DISMISSAL_TYPES = {"fired", "not_renewed"}


# ─── Series helpers ──────────────────────────────────────────────────────────

def _series_label(sid: str) -> str:
    names = {
        "formula_4":        "Formula 4",
        "formula_regional": "Formula Regional",
        "formula_3":        "Formula 3",
        "formula_2":        "Formula 2",
        "formula_1":        "Formula 1",
    }
    return names.get(sid, sid.replace("_", " ").title())


def _series_above(sid: str) -> Optional[str]:
    idx = SERIES_PROGRESSION.index(sid) if sid in SERIES_PROGRESSION else -1
    return SERIES_PROGRESSION[idx + 1] if 0 <= idx < len(SERIES_PROGRESSION) - 1 else None


def _series_below(sid: str) -> Optional[str]:
    idx = SERIES_PROGRESSION.index(sid) if sid in SERIES_PROGRESSION else -1
    return SERIES_PROGRESSION[idx - 1] if idx > 0 else None


# ─── Score-based opportunity resolver ────────────────────────────────────────

def _driver_score(driver: Driver) -> float:
    """
    Multidimensional driver score used by teams to evaluate the player.
    Weighted blend of attributes + career stats bonus.
    Range roughly 0-100.
    """
    raw = (driver.speed       * 0.28 +
           driver.consistency * 0.22 +
           driver.overtaking  * 0.15 +
           driver.tyre_mgmt   * 0.15 +
           driver.defence     * 0.10 +
           driver.rain        * 0.10)
    # Popularity bonus (marketability)
    pop_bonus = driver.popularity * 0.05
    # Potential bonus (teams value upside)
    pot_bonus = max(0, driver.potential - raw) * 0.10
    # Slight penalty for injury history
    health_pen = max(0, (100 - driver.health) * 0.02)
    return raw + pop_bonus + pot_bonus - health_pen


def _team_interest_score(team: Team, driver: Driver, series_id: str) -> float:
    """
    How interested is this team in the driver?
    Higher score → more likely to send an offer.
    """
    driver_sc = _driver_score(driver)
    team_quality = team.car_performance

    # Teams with strong academies prefer their own pipeline — slight penalty for outsiders
    academy_penalty = 5.0 if (team.academy and
                               not _driver_in_pipeline(driver, team.academy)) else 0.0

    # Budget fit — top teams only interested in drivers who justify the salary
    budget_ratio = min(1.5, team.budget / max(1, driver.salary * 10))
    budget_fit = 10.0 * min(1.0, budget_ratio)

    # Prestige gap — star teams less likely to approach mid-table drivers
    prestige_gap = max(0, team.reputation - driver.popularity) * 0.05

    return driver_sc + budget_fit - academy_penalty - prestige_gap


def _driver_in_pipeline(driver: Driver, academy_id: str) -> bool:
    return driver.academy_id == academy_id


# ─── Main offer generator ─────────────────────────────────────────────────────

def generate_offer(career) -> Optional[dict]:
    """
    Returns an offer dict or None.
    Applies score-based weighting + Super Licence gate for F1 offers.
    """
    if random.random() > OFFER_CHANCE_PER_RACE:
        return None

    # Se já assinou contrato para o próximo ano, só aceita promoções superiores
    already_signed = getattr(career, "_contract_next_year", None) is not None
    signed_series  = getattr(career, "_contract_next_series", None)

    current      = career.current_series_id
    pos          = career.player_team_position()
    total        = len(career.all_teams)
    rounds_done  = career.season.current_round if career.season else 0
    total_rounds = len(career.season.rounds)   if career.season else 12

    # Pick best player driver for scoring
    p_drivers = career.player_drivers()
    p_driver  = max(p_drivers, key=lambda d: _driver_score(d)) if p_drivers else None

    weights = _offer_weights(pos, total, rounds_done, total_rounds, current)
    offer_type = random.choices(
        ["step_up", "step_down", "lateral_better", "lateral_worse", "fired", "not_renewed"],
        weights=weights
    )[0]

    # Se já assinou: bloqueia tudo exceto promoção para série acima da assinada
    if already_signed:
        if offer_type != "step_up":
            return None
        next_s = _series_above(current)
        if not next_s:
            return None
        # Se assinou F3 mas recebe F2: permite. Se assinou F2 e recebe F3: bloqueia.
        signed_idx = SERIES_PROGRESSION.index(signed_series) if signed_series in SERIES_PROGRESSION else 0
        next_idx   = SERIES_PROGRESSION.index(next_s)
        if next_idx <= signed_idx:
            return None

    pt = career.player_team

    # ── Step up ──────────────────────────────────────────────────────────────
    if offer_type == "step_up":
        next_s = _series_above(current)
        if not next_s:
            return None

        # Super Licence gate: cannot get F1 offer if driver is ineligible
        if next_s == "formula_1" and p_driver:
            eligible, reason = sl.check_f1_eligibility(p_driver)
            if not eligible:
                # Downgrade to lateral offer instead
                offer_type = "lateral_better"
            else:
                # Build F1 offer
                teams = load_teams_for_series(next_s)
                # Score-rank teams, pick a proportional one based on driver's score
                sc = _driver_score(p_driver) if p_driver else 70
                if sc >= 90:
                    target = random.choice(teams[:4])   # top teams
                elif sc >= 80:
                    target = random.choice(teams[2:7])
                else:
                    target = random.choice(teams[5:])
                salary = _estimate_salary(p_driver, target, next_s)
                return _build_offer("step_up", target, next_s, salary,
                                    random.randint(1, 3), pt)

        if offer_type == "step_up":  # non-F1 step up
            teams = load_teams_for_series(next_s)
            sc = _driver_score(p_driver) if p_driver else 70
            if sc >= 85:
                target = random.choice(teams[:3])
            else:
                target = random.choice(teams[2:7])
            salary = _estimate_salary(p_driver, target, next_s)
            return _build_offer("step_up", target, next_s, salary,
                                random.randint(1, 2), pt)

    # ── Step down ────────────────────────────────────────────────────────────
    if offer_type == "step_down":
        prev_s = _series_below(current)
        if not prev_s:
            return None
        teams = load_teams_for_series(prev_s)
        target = random.choice(teams[:4])
        salary = _estimate_salary(p_driver, target, prev_s, premium=1.3)
        return _build_offer("step_down", target, prev_s, salary,
                            random.randint(1, 2), pt)

    # ── Fired ────────────────────────────────────────────────────────────────
    if offer_type == "fired":
        msg_options = [
            _t("offer.fired_msg1", "{team}'s sponsor threatened to pull funding — they need a new driver.", team=pt.name),
            _t("offer.fired_msg2", "{team}'s board decided to change the driver lineup.", team=pt.name),
            _t("offer.fired_msg3", "{team} received a pay-driver offer and needs to free up a seat.", team=pt.name),
        ]
        others = [t for t in career.all_teams if t.id != pt.id]
        target = random.choice(others[-3:])
        salary = _estimate_salary(p_driver, target, current, premium=0.9)
        offer = _build_offer("fired", target, current, salary, 1, pt)
        offer["description"] = random.choice(msg_options)
        offer["forced"] = True
        offer["is_dismissal"] = True
        offer["dismissal_type"] = "fired"
        remaining = p_driver.contract_years if p_driver else 0
        offer["penalty_to_player"] = (p_driver.salary if p_driver else 0) * max(1, remaining)
        return offer

    # ── Lateral better ───────────────────────────────────────────────────────
    if offer_type == "lateral_better":
        better = [t for t in career.all_teams
                  if t.id != pt.id and t.car_performance > pt.car_performance]
        if not better:
            return None
        # Score-rank and pick
        if p_driver:
            better.sort(key=lambda t: _team_interest_score(t, p_driver, current),
                        reverse=True)
        target = better[0] if len(better) == 1 else random.choice(better[:3])
        salary = _estimate_salary(p_driver, target, current)
        return _build_offer("lateral_better", target, current, salary,
                            random.randint(1, 2), pt)

    # ── Not renewed ──────────────────────────────────────────────────────────────
    if offer_type == "not_renewed":
        msg_options = [
            _t("offer.not_ren_msg1", "{team} informs that your contract will not be renewed at season end.", team=pt.name),
            _t("offer.not_ren_msg2", "{team}'s board decided to pursue a different driver lineup.", team=pt.name),
            _t("offer.not_ren_msg3", "{team} will look for alternatives — your contract will not be renewed.", team=pt.name),
        ]
        offer = _build_offer("not_renewed", pt, current, p_driver.salary if p_driver else 0, 0, pt)
        offer["description"] = random.choice(msg_options)
        offer["forced"] = False
        offer["is_dismissal"] = True
        offer["dismissal_type"] = "not_renewed"
        return offer

    # ── Lateral worse ────────────────────────────────────────────────────────
    worse = [t for t in career.all_teams
             if t.id != pt.id and t.car_performance <= pt.car_performance]
    if not worse:
        return None
    target = random.choice(worse)
    salary = _estimate_salary(p_driver, target, current, premium=1.3)
    return _build_offer("lateral_worse", target, current, salary,
                        random.randint(1, 2), pt)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _estimate_salary(driver: Optional[Driver], team: Team,
                     series_id: str, premium: float = 1.0) -> int:
    """Estimate a realistic salary offer based on driver ability and team budget."""
    base = driver.salary if driver else 100000
    # Salary scales with team budget capacity
    budget_factor = min(2.0, team.budget / max(1, base * 12))
    score_factor  = (_driver_score(driver) / 80.0) if driver else 1.0
    estimated = int(base * budget_factor * score_factor * premium *
                    random.uniform(0.90, 1.15))
    # Never offer less than series minimum (valores realistas 2025)
    series_min = {
        "formula_4":          5_000,
        "formula_regional":  15_000,
        "formula_3":         30_000,
        "formula_2":         80_000,
        "formula_1":        500_000,
    }
    return max(estimated, series_min.get(series_id, 5_000))


def _build_offer(otype: str, team: Team, series_id: str,
                 salary: int, years: int, pt: Team) -> dict:
    label = _series_label(series_id)
    descriptions = {
        "step_up":        _t("offer.desc_step_up",       team=team.name, series=label),
        "step_down":      _t("offer.desc_step_down",      team=team.name, series=label),
        "lateral_better": _t("offer.desc_lateral_better", team=team.name, perf=f"{team.car_performance:.0f}"),
        "lateral_worse":  _t("offer.desc_lateral_worse",  team=team.name),
        "fired":          _t("offer.desc_fired",           team=team.name),
    }
    return {
        "type":               otype,
        "from_team":          team.name,
        "from_team_id":       team.id,
        "from_series":        series_id,
        "from_series_label":  label,
        "salary":             salary,
        "years":              years,
        "description":        descriptions.get(otype, ""),
        "team_chassis":       team.chassis,
        "team_rep":           team.reputation,
        "team_car_perf":      team.car_performance,
    }


def _offer_weights(pos: int, total: int, rounds_done: int, total_rounds: int,
                   current_series: str) -> List[float]:
    """Weights for [step_up, step_down, lateral_better, lateral_worse, fired, not_renewed]."""
    top_half    = pos <= total // 2
    late_season = rounds_done >= total_rounds * 0.6
    has_above   = _series_above(current_series) is not None
    has_below   = _series_below(current_series) is not None

    w_up       = (4.0 if top_half else 0.5) * (1.0 if has_above else 0.0)
    w_down     = (0.3 if top_half else 2.0) * (1.0 if has_below else 0.0)
    w_lat_b    = 2.5 if late_season else 1.5
    w_lat_w    = 1.0 if late_season else 0.5
    w_fired    = 0.2 if top_half else (2.5 if not late_season else 1.0)
    # not_renewed é mais comum no fim da temporada e quando estiver no fundo da tabela
    w_not_ren  = (1.5 if late_season and not top_half else 0.3)

    return [w_up, w_down, w_lat_b, w_lat_w, w_fired, w_not_ren]


# ─── Offer type labels ────────────────────────────────────────────────────────

OFFER_TYPE_LABEL = {
    "step_up":        "PROMOCAO",
    "step_down":      "PROPOSTA DE REBAIXAMENTO",
    "lateral_better": "OFERTA LATERAL (carro melhor)",
    "lateral_worse":  "OFERTA LATERAL (salario maior)",
    "fired":          "ATENCAO — DISPENSA IMEDIATA",
    "not_renewed":    "AVISO — CONTRATO NAO SERA RENOVADO",
}
