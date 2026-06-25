from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Driver:
    id: str
    name: str
    age: int
    nationality: str
    speed: int
    consistency: int
    rain: int
    overtaking: int
    defence: int
    tyre_mgmt: int
    feedback: int
    potential: int
    salary: int
    popularity: int
    aggressiveness: int
    team_id: Optional[str] = None
    contract_years: int = 0
    total_points: int = 0
    total_wins: int = 0
    total_podiums: int = 0
    # Super Licence
    super_licence_points: int = 0
    sl_points_history: dict = field(default_factory=dict)  # {season_year: pts_earned}
    fp1_sessions: int = 0          # bonus SL points from FP1
    # Academy
    academy_id: Optional[str] = None
    # Health / injuries
    health: int = 100              # 0-100; 100 = fit
    injury_races_remaining: int = 0
    injury_type: str = ""          # "", "minor", "moderate", "serious"
    # Career stats
    series_history: list = field(default_factory=list)  # [{"year":2027,"series":"f3","pos":1}]
    experience: int = 0            # XP acumulado (corridas, quali, FP1, temporadas)
    races_completed: int = 0

    @property
    def overall(self) -> float:
        return (self.speed * 0.30 + self.consistency * 0.20 + self.overtaking * 0.15 +
                self.tyre_mgmt * 0.15 + self.defence * 0.10 + self.rain * 0.10)

    @property
    def is_injured(self) -> bool:
        return self.injury_races_remaining > 0

    @property
    def sl_eligible_f1(self) -> bool:
        return self.super_licence_points >= 40 and self.age >= 18

    def effective_pace(self) -> float:
        """Pace adjusted for health (injuries reduce pace)."""
        health_factor = max(0.70, self.health / 100.0)
        return self.overall * health_factor

    _GROWTH_ATTRS = ("speed", "consistency", "tyre_mgmt", "overtaking",
                     "defence", "rain", "feedback")

    def gain_race_xp(self, amount: int = 10):
        """Chamado a cada corrida/quali/FP1/treino. XP eleva potencial e habilidades."""
        self.experience += amount
        # Experiência empurra o teto de potencial lentamente (técnica/feedback)
        if self.experience % 120 == 0 and self.age < 32:
            self.potential = min(99, self.potential + 1)

    def age_up(self) -> dict:
        """Avança 1 ano. Retorna {atributo: delta} para exibição na UI."""
        before = {a: getattr(self, a) for a in self._GROWTH_ATTRS}
        self.age += 1

        # Crescimento: jovens crescem rápido; veteranos ainda evoluem feedback/consistência.
        gap = self.potential - self.overall
        # fator de idade — pico de aprendizado até ~24, decai até ~30
        if self.age <= 24:
            age_factor = 1.0
        elif self.age <= 28:
            age_factor = 0.6
        elif self.age <= 31:
            age_factor = 0.3
        else:
            age_factor = 0.0
        # bônus de experiência (mesmo sem vencer, correr melhora)
        xp_factor = min(1.5, 1.0 + self.experience / 800.0)

        if gap > 0 and age_factor > 0:
            growth = gap * 0.22 * age_factor * xp_factor
            self.speed       = min(99, self.speed       + max(0, round(growth * 0.30)))
            self.consistency = min(99, self.consistency + max(0, round(growth * 0.24)))
            self.tyre_mgmt   = min(99, self.tyre_mgmt   + max(0, round(growth * 0.18)))
            self.overtaking  = min(99, self.overtaking  + max(0, round(growth * 0.14)))
            self.defence     = min(99, self.defence     + max(0, round(growth * 0.08)))
            self.rain        = min(99, self.rain        + max(0, round(growth * 0.06)))
        # feedback técnico sempre melhora um pouco com experiência (até veterano)
        if self.age <= 34 and self.feedback < 99:
            self.feedback = min(99, self.feedback + (1 if self.experience >= 60 else 0))

        # declínio dos veteranos
        if self.age >= 34:
            self.speed       = max(45, self.speed       - 1)
            self.consistency = max(50, self.consistency - 1)
        if self.age >= 37:
            self.overtaking  = max(45, self.overtaking  - 1)
            self.rain        = max(45, self.rain        - 1)

        return {a: getattr(self, a) - before[a] for a in self._GROWTH_ATTRS
                if getattr(self, a) != before[a]}

    def recover(self):
        """Call each missed race. Returns True when fully recovered."""
        if self.injury_races_remaining > 0:
            self.injury_races_remaining -= 1
            self.health = min(100, self.health + 25)
        if self.injury_races_remaining <= 0:
            self.health = 100
            self.injury_type = ""
            return True
        return False


@dataclass
class Facilities:
    factory: int = 1       # 1-5: car development speed multiplier
    simulator: int = 1     # 1-5: reduces R&D cost, improves feedback effect
    r_and_d: int = 1       # 1-5: aero/chassis gain per upgrade
    pit_crew: int = 1      # 1-5: reduces pit stop time
    marketing: int = 1     # 1-5: sponsor income multiplier

    def pit_time_bonus(self) -> float:
        """Seconds saved in pit vs base time."""
        return (self.pit_crew - 1) * 0.8   # up to -3.2s at level 5

    def dev_speed_multiplier(self) -> float:
        """Multiplier for how fast upgrades develop."""
        return 1.0 + (self.factory - 1) * 0.20  # 1.0x … 1.8x

    def sponsor_multiplier(self) -> float:
        return 1.0 + (self.marketing - 1) * 0.10  # 1.0x … 1.4x

    def upgrade_cost(self, facility: str) -> int:
        costs = {"factory": 400000, "simulator": 300000,
                 "r_and_d": 350000, "pit_crew": 250000, "marketing": 200000}
        level = getattr(self, facility, 1)
        return int(costs.get(facility, 300000) * (level ** 1.4))


@dataclass
class Team:
    id: str
    name: str
    short: str
    color: str
    chassis: int
    aerodynamics: int
    reliability: int
    pit_crew: int
    engineers: int
    factory: int
    reputation: int
    budget: int
    base_cost_per_race: int
    sponsors: list = field(default_factory=list)
    is_player_team: bool = False
    drivers: list = field(default_factory=list)
    season_points: int = 0
    season_wins: int = 0
    season_podiums: int = 0
    academy: Optional[str] = None
    # Facility levels (separate from car attributes)
    fac_factory: int = 1
    fac_simulator: int = 1
    fac_r_and_d: int = 1
    fac_pit_crew: int = 1
    fac_marketing: int = 1

    @property
    def car_performance(self) -> float:
        return (self.chassis * 0.35 + self.aerodynamics * 0.30 +
                self.reliability * 0.20 + self.engineers * 0.15)

    @property
    def facilities(self) -> Facilities:
        return Facilities(self.fac_factory, self.fac_simulator,
                          self.fac_r_and_d, self.fac_pit_crew, self.fac_marketing)

    @property
    def annual_sponsor_income(self) -> int:
        base = sum(s["value"] for s in self.sponsors if isinstance(s, dict))
        return int(base * self.facilities.sponsor_multiplier())

    def race_expense(self) -> int:
        return self.base_cost_per_race

    def can_afford_race(self) -> bool:
        return self.budget >= self.base_cost_per_race


@dataclass
class Academy:
    id: str
    name: str
    short: str
    affiliated_team_f1: Optional[str]
    pipeline_teams: list
    benefits: dict
    restrictions: dict
    prestige: int
    annual_stipend: int


@dataclass
class RaceResult:
    driver_id: str
    driver_name: str
    team_id: str
    team_name: str
    position: int
    laps_completed: int
    total_time: float
    pit_stops: int
    tyre_strategy: list
    fastest_lap: bool = False
    dnf: bool = False
    dnf_reason: str = ""
    points: int = 0


@dataclass
class RaceEvent:
    lap: int
    event_type: str
    description: str
    affects_driver: Optional[str] = None


@dataclass
class SeasonRound:
    round_number: int
    track_name: str
    country: str
    laps: int
    length_km: float
    track_type: str
    overtaking_index: int
    tyre_wear_index: int
    completed: bool = False
    results: list = field(default_factory=list)


@dataclass
class Season:
    year: int
    series_id: str
    series_name: str
    rounds: list = field(default_factory=list)
    current_round: int = 0
    teams: list = field(default_factory=list)
    drivers: list = field(default_factory=list)
