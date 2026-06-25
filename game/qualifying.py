"""
Classificação (qualifying) — define o grid de largada antes da corrida.

Formatos:
  - "single"  : sessão única e curta (categorias de base: F4, Regional, F3, F2)
  - "q1q2q3"  : eliminatório em três partes (Fórmula 1), como o modelo atual da F1.

Retorna uma grade ordenada com tempos, gaps e em qual parte cada piloto parou.
"""
import random
from typing import List, Dict, Optional
from .models import Driver, Team, SeasonRound

# Formato por categoria
QUALI_FORMAT = {
    "formula_1": "q1q2q3",
    "formula_2": "single",
    "formula_3": "single",
    "formula_regional": "single",
    "formula_4": "single",
}

# Duração (min) de cada sessão — apenas informativo na UI
QUALI_DURATION = {
    "q1q2q3": {"Q1": 18, "Q2": 15, "Q3": 12},
    "single": {"Q": 15},
}


def _qpace(driver: Driver, team: Team, is_wet: bool) -> float:
    """Ritmo de classificação (volta única) — privilegia velocidade pura e o carro."""
    if is_wet:
        drv = driver.rain * 0.45 + driver.consistency * 0.20 + driver.speed * 0.20
    else:
        drv = driver.speed * 0.55 + driver.consistency * 0.20 + driver.tyre_mgmt * 0.05
    health = max(0.80, driver.health / 100.0)
    return (drv * 0.42 + team.car_performance * 0.58) * health


def _lap_time(driver: Driver, team: Team, base_lap: float, is_wet: bool) -> float:
    """Tempo de uma volta lançada (menor = melhor)."""
    pace = _qpace(driver, team, is_wet)
    offset = (95.0 - pace) * 0.035          # ~0..2.5s entre o melhor e o pior
    noise = random.gauss(0, 0.18)            # variação de volta
    wet_pen = random.uniform(0.0, 3.0) if is_wet else 0.0
    return max(base_lap * 0.90, base_lap + offset + noise + wet_pen)


def _session(drivers_states, base_lap, is_wet):
    """Roda uma sessão: retorna lista (driver_id -> melhor tempo) ordenada."""
    times = []
    for d, t in drivers_states:
        # melhor de 2 voltas lançadas
        best = min(_lap_time(d, t, base_lap, is_wet), _lap_time(d, t, base_lap, is_wet))
        times.append((d, t, best))
    times.sort(key=lambda x: x[2])
    return times


def simulate_qualifying(drivers: List[Driver], teams: Dict[str, Team],
                        series_id: str, track: SeasonRound,
                        base_lap: float = 95.0,
                        is_wet: bool = False) -> dict:
    """
    Simula a classificação. Retorna:
      {
        "format": "single"|"q1q2q3",
        "is_wet": bool,
        "rows": [ {pos, driver_id, name, team_name, time, gap, segment} ... ],
        "order": [driver_id ...],   # ordem do grid
      }
    """
    pairs = [(d, teams.get(d.team_id)) for d in drivers if teams.get(d.team_id)]
    fmt = QUALI_FORMAT.get(series_id, "single")
    rows: List[dict] = []

    def make_row(pos, d, t, time, segment):
        return {"pos": pos, "driver_id": d.id, "name": d.name,
                "team_name": t.name if t else "—", "time": time, "segment": segment}

    if fmt == "single" or len(pairs) <= 12:
        res = _session(pairs, base_lap, is_wet)
        for i, (d, t, tm) in enumerate(res):
            rows.append(make_row(i + 1, d, t, tm, "Q"))
    else:
        n = len(pairs)
        # quantos avançam em cada corte (estilo F1: 15 / 10)
        adv2 = min(15, n - 1)
        adv3 = min(10, adv2 - 1)
        # Q1
        q1 = _session(pairs, base_lap, is_wet)
        eliminated_q1 = q1[adv2:]
        for j, (d, t, tm) in enumerate(eliminated_q1):
            rows.append(make_row(adv2 + 1 + j, d, t, tm, "Q1"))
        # Q2
        q2_field = [(d, t) for d, t, _ in q1[:adv2]]
        q2 = _session(q2_field, base_lap, is_wet)
        eliminated_q2 = q2[adv3:]
        for j, (d, t, tm) in enumerate(eliminated_q2):
            rows.append(make_row(adv3 + 1 + j, d, t, tm, "Q2"))
        # Q3 (pole shootout)
        q3_field = [(d, t) for d, t, _ in q2[:adv3]]
        q3 = _session(q3_field, base_lap, is_wet)
        for i, (d, t, tm) in enumerate(q3):
            rows.append(make_row(i + 1, d, t, tm, "Q3"))

    rows.sort(key=lambda r: r["pos"])
    pole = rows[0]["time"] if rows else 0.0
    for r in rows:
        r["gap"] = r["time"] - pole
    return {
        "format": fmt,
        "is_wet": is_wet,
        "rows": rows,
        "order": [r["driver_id"] for r in rows],
    }
