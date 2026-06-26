"""
Busca ativa de vagas — o piloto procura equipes nas categorias abaixo, atual e acima.

Status de cada vaga:
  "green"  — Garantida: piloto tem perfil para essa equipe e há vaga provável
  "orange" — Arriscar: perfil marginal mas vale tentar
  "red"    — Indisponível: SL bloqueado, perfil muito abaixo ou sem vaga

O piloto pode se candidatar a qualquer vaga verde ou laranja.
A candidatura gera uma oferta formal que vai para a OfferScene.
"""
import random
from typing import List, Optional, Dict
from .models import Driver, Team
from .career import SERIES_PROGRESSION, load_teams_for_series, load_series
from .offers import _driver_score, _estimate_salary, _build_offer, _series_label
from . import super_licence as sl


# Threshold de pontuação do piloto vs reputação da equipe
_GREEN_RATIO  = 0.85   # piloto.score >= team.reputation * 0.85 → verde
_ORANGE_RATIO = 0.55   # piloto.score >= team.reputation * 0.55 → laranja


def _series_neighbors(current: str) -> List[str]:
    """Retorna [series_below, current, series_above] filtrando None."""
    idx = SERIES_PROGRESSION.index(current) if current in SERIES_PROGRESSION else 2
    result = []
    if idx > 0:
        result.append(SERIES_PROGRESSION[idx - 1])
    result.append(current)
    if idx < len(SERIES_PROGRESSION) - 1:
        result.append(SERIES_PROGRESSION[idx + 1])
    return result


def _vacancy_count(team: Team, all_teams: List[Team]) -> int:
    """Vagas disponíveis estimadas (0, 1 ou 2)."""
    t = next((x for x in all_teams if x.id == team.id), team)
    return max(0, 2 - len(t.drivers))


def build_vacancy_list(career) -> List[dict]:
    """
    Retorna lista de dicts representando vagas, ordenadas por série e reputação.
    Cada entry tem: series_id, series_label, team, status, reason,
                    vacancy_count, sl_ok, score, team_threshold, penalty
    """
    p_driver: Optional[Driver] = getattr(career, "player_driver", None)
    if not p_driver:
        return []

    current   = career.current_series_id
    neighbors = _series_neighbors(current)
    score     = _driver_score(p_driver)

    # Vagas reais da série atual
    current_teams_map = {t.id: t for t in career.all_teams}

    entries = []
    for series in neighbors:
        is_current = (series == current)
        rules = load_series(series)
        # Carrega times daquela série (usa os in-memory para a série atual)
        if is_current:
            teams = list(career.all_teams)
        else:
            teams = load_teams_for_series(series)

        for team in teams:
            # Pular equipe atual do jogador (já está lá)
            is_my_team = (team.id == (career.current_team.id if getattr(career, "current_team", None) else None)
                          or team.id == (career.player_team.id if getattr(career, "player_team", None) else None))

            # SL gate para F1
            sl_ok = True
            sl_reason = ""
            if series == "formula_1":
                eligible, reason = sl.check_f1_eligibility(p_driver)
                sl_ok = eligible
                sl_reason = reason if not eligible else ""

            # Calcula vagas (só série atual tem dados reais)
            if is_current:
                vac = _vacancy_count(team, career.all_teams)
                vac_label = f"{vac} vaga(s)" if vac > 0 else "sem vaga"
            else:
                # Estimativa: ~60% dos times têm ao menos 1 vaga disponível no mercado
                vac = random.choices([0, 1, 2], weights=[40, 40, 20])[0]
                vac_label = "vaga incerta"

            # Threshold: reputação da equipe como critério mínimo
            team_threshold = team.reputation  # 0-100 scale

            # Status
            if not sl_ok:
                status = "red"
                reason = f"Super Licença insuficiente — {sl_reason}"
            elif vac == 0 and is_current:
                status = "red"
                reason = "Equipe sem vagas disponíveis"
            elif score >= team_threshold * _GREEN_RATIO:
                status = "green"
                reason = "Perfil compatível — boa chance de contrato"
            elif score >= team_threshold * _ORANGE_RATIO:
                status = "orange"
                reason = "Perfil marginal — vale tentar, sem garantia"
            else:
                status = "red"
                reason = f"Perfil abaixo do esperado (nota {score:.0f} vs mín ~{team_threshold * _ORANGE_RATIO:.0f})"

            # Multa se o piloto tiver contrato ativo e mudar de equipe
            penalty = 0
            if p_driver.contract_years > 0 and not is_my_team:
                penalty = p_driver.salary * p_driver.contract_years

            entries.append({
                "series_id":     series,
                "series_label":  _series_label(series),
                "team":          team,
                "is_my_team":    is_my_team,
                "is_current_series": is_current,
                "status":        status if not is_my_team else "current",
                "reason":        reason if not is_my_team else "Sua equipe atual",
                "vacancy_count": vac,
                "vacancy_label": vac_label,
                "sl_ok":         sl_ok,
                "score":         score,
                "team_threshold": team_threshold,
                "penalty":       penalty,
            })

    # Ordena: verde primeiro, depois laranja, depois vermelho; dentro de cada cor por série
    order = {"current": 0, "green": 1, "orange": 2, "red": 3}
    entries.sort(key=lambda e: (order.get(e["status"], 9),
                                neighbors.index(e["series_id"]),
                                -e["team"].reputation))
    return entries


def apply_to_team(career, team_id: str, series_id: str) -> Optional[dict]:
    """
    O piloto se candidata a uma equipe. Retorna oferta formal ou None se rejeitado.
    Chance de aceite depende do status (verde=90%, laranja=50%).
    """
    p_driver: Optional[Driver] = getattr(career, "player_driver", None)
    if not p_driver:
        return None

    vacancies = build_vacancy_list(career)
    entry = next((e for e in vacancies
                  if e["team"].id == team_id and e["series_id"] == series_id), None)
    if not entry or entry["status"] == "red":
        return None

    accept_chance = 0.90 if entry["status"] == "green" else 0.50
    if random.random() > accept_chance:
        return None   # rejeitado

    team = entry["team"]
    salary = _estimate_salary(p_driver, team, series_id)
    offer = _build_offer("step_up" if series_id != career.current_series_id else "lateral_better",
                         team, series_id, salary, random.randint(1, 2),
                         getattr(career, "current_team", team))
    offer["description"] = (f"{team.name} aceitou sua candidatura! "
                            f"Oferta de {_series_label(series_id)}.")
    offer["from_job_search"] = True
    if entry["penalty"] > 0:
        offer["breaking_penalty"] = entry["penalty"]  # piloto paga essa multa
    return offer
