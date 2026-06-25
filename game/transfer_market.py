import random
from typing import List, Optional, Tuple
from .models import Driver, Team


SERIES_ORDER = ["formula_regional", "formula_3", "formula_2"]


def driver_market_value(driver: Driver, season_points: int) -> int:
    base = driver.salary
    perf_bonus = season_points * 800
    age_factor = 1.0
    if driver.age < 21:
        age_factor = 1.15
    elif driver.age > 28:
        age_factor = max(0.7, 1.0 - (driver.age - 28) * 0.05)
    potential_factor = 1.0 + (driver.potential - driver.overall) / 300
    return int(base * age_factor * potential_factor + perf_bonus)


def generate_ai_offers(
    free_agents: List[Driver],
    ai_teams: List[Team],
    driver_points: dict,
    slots_per_team: int = 2,
) -> dict:
    """Returns dict: driver_id -> list of (team, offered_salary)."""
    offers = {d.id: [] for d in free_agents}
    for team in ai_teams:
        needed = slots_per_team - len([d for d in free_agents if d.team_id == team.id])
        needed = max(0, slots_per_team)
        candidates = sorted(
            free_agents,
            key=lambda d: -(driver_market_value(d, driver_points.get(d.id, 0))),
        )
        for drv in candidates[:needed * 3]:
            mv = driver_market_value(drv, driver_points.get(drv.id, 0))
            budget_headroom = team.budget * 0.35
            offered = min(int(mv * random.uniform(0.85, 1.10)), int(budget_headroom * 0.5))
            if offered >= drv.salary * 0.70:
                offers[drv.id].append((team, offered))
    return offers


class TransferMarket:
    def __init__(self, career):
        self.career = career

    def expiring_contracts(self) -> List[Driver]:
        """Drivers whose contracts end this season."""
        return [d for d in self.career.all_drivers if d.contract_years <= 0]

    def free_agents_after_expiry(self) -> List[Driver]:
        expired = self.expiring_contracts()
        player_ids = self.career.player_team.drivers if self.career.player_team else []
        return [d for d in expired if d.id not in player_ids]

    def release_driver(self, driver_id: str):
        drv = next((d for d in self.career.all_drivers if d.id == driver_id), None)
        if drv:
            if drv.team_id:
                team = next((t for t in self.career.all_teams if t.id == drv.team_id), None)
                if team and driver_id in team.drivers:
                    team.drivers.remove(driver_id)
            drv.team_id = None
            drv.contract_years = 0

    def sign_driver(self, driver_id: str, salary: int, years: int) -> Tuple[bool, str]:
        drv = next((d for d in self.career.all_drivers if d.id == driver_id), None)
        if not drv:
            return False, "Piloto não encontrado."
        pt = self.career.player_team
        if len(pt.drivers) >= 2:
            return False, "Equipe já tem 2 pilotos. Libere um antes."
        annual_cost = salary * years
        if pt.budget < salary:
            return False, f"Orçamento insuficiente (salário anual: €{salary:,.0f})."
        drv.team_id = pt.id
        drv.salary = salary
        drv.contract_years = years
        pt.drivers.append(driver_id)
        pt.budget -= salary
        return True, f"{drv.name} contratado por €{salary:,.0f}/ano por {years} ano(s)."

    def renew_contract(self, driver_id: str, salary: int, years: int) -> Tuple[bool, str]:
        drv = next((d for d in self.career.all_drivers if d.id == driver_id), None)
        if not drv:
            return False, "Piloto não encontrado."
        if drv.team_id != self.career.player_team.id:
            return False, "Este piloto não está na sua equipe."
        pt = self.career.player_team
        if pt.budget < salary:
            return False, f"Orçamento insuficiente para renovar (€{salary:,.0f}/ano)."
        drv.salary = salary
        drv.contract_years = years
        pt.budget -= salary
        return True, f"Contrato de {drv.name} renovado — €{drv.salary:,.0f}/ano por {years} ano(s)."

    def run_ai_transfers(self):
        """AI teams fill their vacant spots from free agents."""
        all_free = [d for d in self.career.all_drivers if not d.team_id or d.contract_years <= 0]
        for d in all_free:
            d.team_id = None

        ai_teams = [t for t in self.career.all_teams if not t.is_player_team]
        for team in ai_teams:
            team.drivers = []

        random.shuffle(all_free)
        idx = 0
        for team in ai_teams:
            while len(team.drivers) < 2 and idx < len(all_free):
                drv = all_free[idx]
                drv.team_id = team.id
                drv.contract_years = random.randint(1, 2)
                team.drivers.append(drv.id)
                idx += 1

    def tick_contracts(self):
        """Decrement contract years at season end."""
        for d in self.career.all_drivers:
            if d.contract_years > 0:
                d.contract_years -= 1
