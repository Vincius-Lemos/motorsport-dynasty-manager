"""
Super Licence FIA — Appendix L 2026
Points accumulated per season based on championship finish position in each series.
Need 40 pts total + age >= 18 to be eligible for F1.
"""

from typing import Optional

# Points awarded per championship finish position, per series
SL_POINTS_TABLE = {
    "formula_1": {},        # Already in F1, no SL accumulation needed
    "formula_2": {
        1: 40, 2: 30, 3: 20, 4: 14, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1
    },
    "formula_3": {
        1: 30, 2: 22, 3: 16, 4: 12, 5: 8, 6: 6, 7: 5, 8: 4, 9: 3, 10: 2
    },
    "formula_regional": {
        1: 20, 2: 14, 3: 10, 4: 7, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1, 10: 1
    },
    "formula_4": {
        1: 12, 2: 10, 3: 8, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1, 10: 1
    },
}

# Bônus de SL por sessão de FP1 (FIA: 1 pt por FP1, máx 10 no total)
FP1_POINTS_PER_SESSION = 1
FP1_POINTS_CAP = 10

# Teto de pontos acumuláveis POR categoria — força o piloto a subir de nível.
# Ex.: só Regional nunca passa de 20 (precisa ir pra F3/F2 para chegar aos 40).
SL_CATEGORY_CAP = {
    "formula_4":        10,
    "formula_regional": 20,
    "formula_3":        34,
    "formula_2":        999,
    "formula_1":        999,
}

# Pontos necessários (FIA) + idade mínima + temporadas em monopostos
# (Appendix L 2026: >=80% de 2 temporadas completas em monopostos)
SL_MAX_NEEDED = 40
SL_MIN_AGE = 18
SL_MIN_SEASONS = 2


def sl_points_for_position(series_id: str, position: int) -> int:
    """Return SL points earned for finishing a championship in the given position."""
    table = SL_POINTS_TABLE.get(series_id, {})
    return table.get(position, 0)


def _earned_in_series(driver, series_id: str) -> int:
    """Total de pontos já creditados nesta categoria (todas as temporadas)."""
    total = 0
    for _yr, sd in driver.sl_points_history.items():
        if isinstance(sd, dict):
            total += sd.get(series_id, 0)
    return total


def award_season_sl_points(driver, series_id: str, championship_position: int, year: int) -> int:
    """
    Credita pontos de SL após a temporada, respeitando o teto por categoria.
    Atualiza driver.super_licence_points e sl_points_history. Retorna pontos creditados.
    """
    pts = sl_points_for_position(series_id, championship_position)
    # Aplica teto por categoria
    cap = SL_CATEGORY_CAP.get(series_id, 999)
    already = _earned_in_series(driver, series_id)
    pts = max(0, min(pts, cap - already))
    if pts <= 0:
        return 0
    driver.super_licence_points += pts
    driver.sl_points_history.setdefault(str(year), {})
    driver.sl_points_history[str(year)][series_id] = \
        driver.sl_points_history[str(year)].get(series_id, 0) + pts
    return pts


def award_fp1_bonus(driver) -> int:
    """Credita 1 pt de SL por FP1, respeitando o teto total de FP1. Retorna pontos creditados."""
    earned = min(driver.fp1_sessions, FP1_POINTS_CAP)
    driver.fp1_sessions += 1
    if earned >= FP1_POINTS_CAP:
        return 0
    driver.super_licence_points += FP1_POINTS_PER_SESSION
    return FP1_POINTS_PER_SESSION


def completed_seasons(driver) -> int:
    """Temporadas em monopostos concluídas (history + experiência de veterano)."""
    hist = len(getattr(driver, "series_history", []) or [])
    # NPCs experientes contam como veteranos mesmo sem histórico detalhado
    by_xp = getattr(driver, "experience", 0) // 250
    return max(hist, by_xp)


def check_f1_eligibility(driver) -> tuple[bool, str]:
    """
    Verifica elegibilidade à Super Licença F1.
    Requisitos: 40 pts + idade 18+ + ao menos 2 temporadas em monopostos.
    """
    if driver.age < SL_MIN_AGE:
        deficit = SL_MIN_AGE - driver.age
        return False, f"Idade minima 18 anos (faltam {deficit} ano(s))"
    if driver.super_licence_points < SL_MAX_NEEDED:
        deficit = SL_MAX_NEEDED - driver.super_licence_points
        return False, f"Pontos insuficientes: {driver.super_licence_points}/40 (faltam {deficit})"
    seasons = completed_seasons(driver)
    if seasons < SL_MIN_SEASONS:
        return False, f"Experiencia insuficiente: {seasons}/2 temporadas em monopostos"
    return True, "Super Licenca aprovada"


def sl_summary(driver) -> dict:
    """Return a summary dict for display."""
    eligible, reason = check_f1_eligibility(driver)
    history_flat = []
    for yr, series_dict in sorted(driver.sl_points_history.items()):
        for sid, pts in series_dict.items():
            history_flat.append({"year": yr, "series": sid, "points": pts})
    return {
        "total_points": driver.super_licence_points,
        "needed": SL_MAX_NEEDED,
        "age": driver.age,
        "min_age": SL_MIN_AGE,
        "fp1_sessions": driver.fp1_sessions,
        "fp1_points": min(driver.fp1_sessions, FP1_POINTS_CAP) * FP1_POINTS_PER_SESSION,
        "eligible": eligible,
        "reason": reason,
        "history": history_flat,
    }
