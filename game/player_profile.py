"""
PlayerProfile — estado central do jogador, persiste entre modos e transições.

Modos:
  "driver"  — jogador É um piloto
  "manager" — jogador GERENCIA uma equipe

Transições:
  driver  → manager: qualquer idade, custo de entrada proporcional à categoria
  manager → driver:  quase impossível; gate de idade ≤ 22 (F4), ≤ 20 (FR), bloqueado em F3+
"""
from dataclasses import dataclass, field
from typing import Optional


# Custo mínimo para comprar entrada em uma equipe como manager (por categoria)
MANAGER_ENTRY_COST = {
    "formula_4":        150_000,
    "formula_regional": 400_000,
    "formula_3":      1_000_000,
    "formula_2":      2_500_000,
    "formula_1":     15_000_000,
}

# Idade máxima para um manager virar piloto em cada categoria
DRIVER_AGE_GATE = {
    "formula_4":        22,
    "formula_regional": 20,
    "formula_3":        -1,   # bloqueado
    "formula_2":        -1,
    "formula_1":        -1,
}

# Stats base de um manager que resolve virar piloto (medíocres — não treinou)
MANAGER_AS_DRIVER_STATS = dict(
    speed=42, consistency=38, rain=35, overtaking=40,
    defence=36, tyre_mgmt=34, feedback=45, potential=50,
    popularity=30, aggressiveness=5,
)


@dataclass
class CareerEntry:
    year: int
    mode: str           # "driver" | "manager"
    series: str
    team: str
    position: int       # campeonato
    promoted: bool = False
    note: str = ""


@dataclass
class PlayerProfile:
    # Identidade
    name: str
    age: int
    nationality: str

    # Modo atual
    mode: str = "driver"          # "driver" | "manager"

    # Finanças pessoais (salário acumulado / dividendos de equipe)
    personal_money: int = 0

    # Reputação global (cresce em ambos os modos)
    reputation: int = 30

    # Histórico de temporadas em ambos os modos
    history: list = field(default_factory=list)   # lista de CareerEntry

    # Referência ao ID do piloto (modo driver) ou ID da equipe (modo manager)
    driver_id: Optional[str] = None
    team_id: Optional[str] = None

    # Moradia — chave de HOUSING_OPTIONS em game/housing.py
    housing: str = "origin"

    def add_history(self, year: int, series: str, team: str,
                    position: int, promoted: bool = False, note: str = ""):
        self.history.append(CareerEntry(
            year=year, mode=self.mode, series=series,
            team=team, position=position, promoted=promoted, note=note,
        ))
        self._update_reputation(position)

    def _update_reputation(self, position: int):
        gain = max(0, 12 - position)  # P1=+11, P5=+7, P10=+2, P11+=0
        self.reputation = min(100, self.reputation + gain)

    # ── Transição driver → manager ────────────────────────────────────────────

    def can_retire_to_manager(self) -> tuple[bool, str]:
        if self.mode != "driver":
            return False, "Ja e chefe de equipe"
        return True, "Aposentadoria disponivel"

    def retire_to_manager(self, entry_series: str) -> tuple[bool, str]:
        ok, msg = self.can_retire_to_manager()
        if not ok:
            return False, msg
        cost = MANAGER_ENTRY_COST.get(entry_series, 500_000)
        if self.personal_money < cost:
            return False, (f"Dinheiro insuficiente: EUR {self.personal_money:,} "
                           f"(minimo EUR {cost:,} para {entry_series})")
        self.personal_money -= cost
        self.mode = "manager"
        self.driver_id = None
        return True, f"Aposentado. Investiu EUR {cost:,} para entrar como chefe de equipe."

    # ── Transição manager → driver ────────────────────────────────────────────

    def can_become_driver(self, target_series: str) -> tuple[bool, str]:
        if self.mode != "manager":
            return False, "Ja e piloto"
        age_limit = DRIVER_AGE_GATE.get(target_series, -1)
        if age_limit == -1:
            return False, f"Impossivel virar piloto em {target_series} — categoria muito elevada"
        if self.age > age_limit:
            return False, (f"Tarde demais: idade {self.age} > limite {age_limit} "
                           f"para {target_series}. Isso e quase impossivel.")
        return True, f"Tecnicamente possivel (idade {self.age} <= {age_limit})"

    def become_driver(self, target_series: str,
                      driver_name: str = "") -> tuple[bool, str, Optional[dict]]:
        """
        Retorna (ok, msg, driver_kwargs) onde driver_kwargs pode ser usado para
        criar um Driver com stats baixos.
        """
        ok, msg = self.can_become_driver(target_series)
        if not ok:
            return False, msg, None
        stats = dict(MANAGER_AS_DRIVER_STATS)
        stats["name"]        = driver_name or self.name
        stats["age"]         = self.age
        stats["nationality"] = self.nationality
        stats["salary"]      = 0    # sem salário ainda
        self.mode = "manager_turned_driver"
        return True, "Boa sorte. Vai precisar.", stats

    # ── Helpers ───────────────────────────────────────────────────────────────

    def receive_salary(self, amount: int):
        self.personal_money += amount

    def pay_expense(self, amount: int) -> bool:
        if self.personal_money < amount:
            return False
        self.personal_money -= amount
        return True

    def summary(self) -> str:
        mode_label = {"driver": "Piloto", "manager": "Chefe de Equipe",
                      "manager_turned_driver": "Piloto (ex-gerente)"}.get(self.mode, self.mode)
        return (f"{self.name} | {self.age} anos | {self.nationality} | "
                f"{mode_label} | Rep:{self.reputation} | EUR {self.personal_money:,}")
