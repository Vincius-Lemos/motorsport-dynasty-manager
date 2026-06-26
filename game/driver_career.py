"""
DriverCareer — carreira onde o jogador É o piloto.

O jogador controla um Driver específico (player_driver).
Não possui uma equipe — apenas assina contratos com equipes.
Acumula Super Licença, entra em academias, recebe lesões, envelhece.
Ofertas chegam para o PILOTO (mudar de equipe/categoria).
"""
import random
from typing import Dict, List, Optional, Tuple

from .models import Driver, Team, Season, SeasonRound, RaceResult, NewsItem
from .player_profile import PlayerProfile
from .career import (
    SERIES_PROGRESSION, load_series, load_drivers_for_series,
    load_teams_for_series, build_season, assign_ai_drivers,
    series_above, series_below, prize_money,
    RACE_WEEKEND_FORMAT, SPRINT_SCORING, FEATURE_SCORING, sprint_grid_from_quali,
)
from .race_engine import simulate_race
from . import super_licence as sl
from . import injuries as inj
from . import academies as acad
from . import housing as hsng


class DriverCareer:
    def __init__(self, profile: PlayerProfile):
        self.profile = profile

        # Mundo atual
        self.all_drivers: List[Driver] = []
        self.all_teams: List[Team] = []
        self.season: Optional[Season] = None
        self.series_rules: dict = {}
        self.current_series_id: str = "formula_4"
        self.career_year: int = 2027
        self.season_number: int = 1

        # O piloto do jogador
        self.player_driver: Optional[Driver] = None
        self.current_team: Optional[Team] = None   # equipe onde está assinado

        # Pontuação da temporada
        self.standings_drivers: Dict[str, int] = {}
        self.standings_teams: Dict[str, int] = {}

        # Log de lesões e FP1 da temporada
        self.injury_log: list = []

        # Oferta pendente aceita durante a temporada
        self._pending_offer: Optional[dict] = None

        # Contrato assinado para próxima temporada (previne ofertas duplicadas)
        self._contract_next_year: Optional[str] = None   # team_id assinado
        self._contract_next_series: Optional[str] = None  # series_id assinado

        # Feed de notícias (últimas 40)
        self.news_feed: List[dict] = []

        # Estado persistente de NPCs entre temporadas {driver_id: {sl_pts, experience, age}}
        self._npc_state: Dict[str, dict] = {}

    # ── Setup inicial ─────────────────────────────────────────────────────────

    def new_career(self, series_id: str, team_id: str,
                   driver_kwargs: Optional[dict] = None) -> str:
        """
        Inicia carreira.
        driver_kwargs: se None, cria piloto baseado no profile.
        Se fornecido (ex: manager virando piloto), usa esses stats.
        """
        self.current_series_id = series_id
        self.career_year = 2027
        self.season_number = 1
        self._load_world(series_id)

        # Cria ou injeta o Driver do jogador
        if driver_kwargs:
            # Manager virando piloto — stats medíocres
            pid = f"player_{self.profile.name.lower().replace(' ', '_')}"
            self.player_driver = Driver(
                id=pid,
                name=driver_kwargs["name"],
                age=driver_kwargs["age"],
                nationality=driver_kwargs["nationality"],
                speed=driver_kwargs.get("speed", 42),
                consistency=driver_kwargs.get("consistency", 38),
                rain=driver_kwargs.get("rain", 35),
                overtaking=driver_kwargs.get("overtaking", 40),
                defence=driver_kwargs.get("defence", 36),
                tyre_mgmt=driver_kwargs.get("tyre_mgmt", 34),
                feedback=driver_kwargs.get("feedback", 45),
                potential=driver_kwargs.get("potential", 50),
                salary=driver_kwargs.get("salary", 0),
                popularity=driver_kwargs.get("popularity", 30),
                aggressiveness=driver_kwargs.get("aggressiveness", 5),
            )
        else:
            # Piloto novato — stats baseados em potencial do profile
            pid = f"player_{self.profile.name.lower().replace(' ', '_')}"
            base = 55 + min(20, self.profile.reputation // 3)
            self.player_driver = Driver(
                id=pid,
                name=self.profile.name,
                age=self.profile.age,
                nationality=self.profile.nationality,
                speed=base, consistency=base - 5, rain=base - 8,
                overtaking=base - 3, defence=base - 6,
                tyre_mgmt=base - 4, feedback=base + 2,
                potential=min(99, base + 25),
                salary=20_000,
                popularity=max(20, self.profile.reputation // 2),
                aggressiveness=5,
            )

        self.player_driver.team_id = team_id
        self.player_driver.contract_years = 1
        self.profile.driver_id = self.player_driver.id

        # Injeta driver do jogador no mundo
        self.all_drivers.append(self.player_driver)

        # Liga à equipe
        self.current_team = next((t for t in self.all_teams if t.id == team_id), None)
        if self.current_team:
            self.current_team.is_player_team = True
            if self.player_driver.id not in self.current_team.drivers:
                self.current_team.drivers.insert(0, self.player_driver.id)

        assign_ai_drivers(self.all_teams, self.all_drivers,
                          exclude_ids=[self.player_driver.id])
        self._start_season()

        return (f"Carreira iniciada: {self.player_driver.name} em "
                f"{self.current_team.name if self.current_team else '?'} — "
                f"{self.series_rules['name']} {self.career_year}")

    def _load_world(self, series_id: str):
        self.series_rules  = load_series(series_id)
        self.all_drivers   = load_drivers_for_series(series_id, self.career_year)
        self.all_teams     = load_teams_for_series(series_id)

    def _start_season(self):
        sid = self.current_series_id
        # Salário do jogador coerente com a categoria (corrige valores incompatíveis)
        from .career import SALARY_BAND, realistic_salary
        lo, hi = SALARY_BAND.get(sid, (20_000, 200_000))
        band_target = realistic_salary(sid, self.player_driver.overall)
        self.player_driver.salary = max(lo, min(hi, max(self.player_driver.salary, band_target)))
        self.season = build_season(sid, self.career_year, self.series_rules,
                                   self.all_teams, self.all_drivers)
        self.standings_drivers = {d.id: 0 for d in self.all_drivers}
        self.standings_teams   = {t.id: 0 for t in self.all_teams}
        self.standings_drivers[self.player_driver.id] = 0
        self.injury_log = []

    # ── Corrida ───────────────────────────────────────────────────────────────

    def current_round(self) -> Optional[SeasonRound]:
        if not self.season:
            return None
        cr = self.season.current_round
        return self.season.rounds[cr] if cr < len(self.season.rounds) else None

    def run_qualifying(self, is_wet: bool = False) -> Optional[dict]:
        """Roda a classificação e guarda o grid para a próxima corrida."""
        from . import qualifying as q
        track = self.current_round()
        if not track:
            return None
        active = [d for d in self.all_drivers if not d.is_injured]
        teams = {t.id: t for t in self.all_teams}
        res = q.simulate_qualifying(active, teams, self.current_series_id, track,
                                    self.series_rules["base_lap_time_seconds"], is_wet)
        self._grid_order = res["order"]
        # XP por classificar
        for d in active:
            d.gain_race_xp(3)
        return res

    def player_quali_position(self, quali: dict) -> int:
        for r in quali["rows"]:
            if r["driver_id"] == self.player_driver.id:
                return r["pos"]
        return len(quali["rows"])

    def simulate_next_race(self, player_strategy=None) -> Tuple[list, list]:
        track = self.current_round()
        if not track:
            return [], []

        injury_events = []
        fp1_events    = []

        # Recuperação de lesionados antes da corrida
        for d in self.all_drivers:
            if d.is_injured:
                inj.process_recovery(d)

        # Rola lesão para piloto do jogador
        if not self.player_driver.is_injured:
            sev = inj.roll_injury(self.player_driver, track.track_type)
            if sev:
                ev = inj.apply_injury(self.player_driver, sev)
                injury_events.append(ev)
                self.injury_log.append(ev)

        # FP1 da academia (não para titular de F1)
        if (self.player_driver.academy_id and
                self.current_series_id != "formula_1"):
            if acad.roll_fp1_session(self.player_driver, self.player_driver.academy_id,
                                     self.current_series_id):
                pts = sl.award_fp1_bonus(self.player_driver)
                self.player_driver.gain_race_xp(8)
                fp1_events.append({
                    "driver": self.player_driver.name,
                    "sl_pts": pts,
                    "academy": self.player_driver.academy_id,
                })

        active_drivers = [d for d in self.all_drivers if not d.is_injured]
        teams_dict = {t.id: t for t in self.all_teams}
        results, events = simulate_race(
            track=track,
            drivers=active_drivers,
            teams=teams_dict,
            base_lap_time=self.series_rules["base_lap_time_seconds"],
            pit_stop_time=self.series_rules["pit_stop_time_seconds"],
            player_strategy=player_strategy,
            grid_order=getattr(self, "_grid_order", None),
        )
        self._grid_order = None

        for r in results:
            self.standings_drivers[r.driver_id] = (
                self.standings_drivers.get(r.driver_id, 0) + r.points)
            self.standings_teams[r.team_id] = (
                self.standings_teams.get(r.team_id, 0) + r.points)
            d = next((x for x in self.all_drivers if x.id == r.driver_id), None)
            if d:
                d.total_points += r.points
                d.races_completed += 1
                # XP por corrida concluída (mesmo sem vencer); bônus por bom resultado
                d.gain_race_xp(10 + max(0, 6 - r.position) if not r.dnf else 4)
                if r.position == 1 and not r.dnf: d.total_wins    += 1
                if r.position <= 3 and not r.dnf: d.total_podiums += 1

        # Custo de corrida pago pela equipe (não pelo jogador)
        for t in self.all_teams:
            t.season_points = self.standings_teams.get(t.id, 0)
            if t.can_afford_race():
                t.budget -= t.race_expense()

        # Salário líquido por corrida (após imposto e moradia)
        if not self.player_driver.is_injured:
            races = max(1, len(self.season.rounds))
            net = hsng.net_per_race(self.player_driver.salary,
                                    self.profile.housing, races)
            self.profile.receive_salary(net)
            # Bônus de XP por moradia (ex: UK +2 XP)
            opt = hsng.HOUSING_OPTIONS.get(self.profile.housing, {})
            if opt.get("xp_bonus", 0) > 0 and not self.player_driver.is_injured:
                self.player_driver.gain_race_xp(opt["xp_bonus"])

        track.completed = True
        track.results   = results
        self.season.current_round += 1

        meta_events = list(events)
        for ev in injury_events:
            meta_events.append(
                type("Ev", (), {"lap": 0, "event_type": "injury",
                                "description": ev["description"],
                                "affects_driver": ev["driver_id"]})())
            self._push_news("injury", ev["description"],
                            driver_id=ev["driver_id"],
                            round_number=self.season.current_round)
        for ev in fp1_events:
            meta_events.append(
                type("Ev", (), {"lap": 0, "event_type": "fp1_bonus",
                                "description": f"FP1: {ev['driver']} +{ev['sl_pts']} pts SL",
                                "affects_driver": None})())
        self._add_news_from_race(results, events, "race")
        return results, meta_events

    def is_sprint_feature_weekend(self) -> bool:
        return RACE_WEEKEND_FORMAT.get(self.current_series_id) == "sprint_feature"

    def simulate_sprint_race(self, is_wet: bool = False) -> Tuple[list, list]:
        """Simula a sprint race com grid invertido do topo da classificação."""
        track = self.current_round()
        if not track:
            return [], []
        grid = sprint_grid_from_quali(getattr(self, "_grid_order", []) or [], self.current_series_id)
        scoring = SPRINT_SCORING.get(self.current_series_id, [8, 7, 6, 5, 4, 3, 2, 1])
        sprint_laps = max(10, track.laps // 3)
        active_drivers = [d for d in self.all_drivers if not d.is_injured]
        teams_dict = {t.id: t for t in self.all_teams}
        results, events = simulate_race(
            track=track,
            drivers=active_drivers,
            teams=teams_dict,
            base_lap_time=self.series_rules["base_lap_time_seconds"],
            pit_stop_time=self.series_rules["pit_stop_time_seconds"],
            grid_order=grid,
            scoring_override=scoring,
            laps_override=sprint_laps,
            fastest_lap_bonus=False,   # sprint não tem bonus de FL
        )
        # Acumula pontos da sprint sem avançar a rodada
        for r in results:
            self.standings_drivers[r.driver_id] = (
                self.standings_drivers.get(r.driver_id, 0) + r.points)
            self.standings_teams[r.team_id] = (
                self.standings_teams.get(r.team_id, 0) + r.points)
            d = next((x for x in self.all_drivers if x.id == r.driver_id), None)
            if d:
                d.total_points += r.points
                d.gain_race_xp(6 if not r.dnf else 2)
        # Feature grid = ordem da sprint
        self._feature_grid = [r.driver_id for r in sorted(results, key=lambda r: r.position)]
        self._add_news_from_race(results, events, "sprint")
        return results, events

    def simulate_feature_race(self, player_strategy=None) -> Tuple[list, list]:
        """Simula a feature race com grid = resultado da sprint."""
        grid = getattr(self, "_feature_grid", None) or getattr(self, "_grid_order", None)
        scoring = FEATURE_SCORING.get(self.current_series_id, [25, 18, 15, 12, 10, 8, 6, 4, 2, 1])
        track = self.current_round()
        if not track:
            return [], []
        active_drivers = [d for d in self.all_drivers if not d.is_injured]
        teams_dict = {t.id: t for t in self.all_teams}
        results, events = simulate_race(
            track=track,
            drivers=active_drivers,
            teams=teams_dict,
            base_lap_time=self.series_rules["base_lap_time_seconds"],
            pit_stop_time=self.series_rules["pit_stop_time_seconds"],
            player_strategy=player_strategy,
            grid_order=grid,
            scoring_override=scoring,
        )
        self._feature_grid = None
        # Acumula pontos e avança rodada (mesma lógica de simulate_next_race)
        for r in results:
            self.standings_drivers[r.driver_id] = (
                self.standings_drivers.get(r.driver_id, 0) + r.points)
            self.standings_teams[r.team_id] = (
                self.standings_teams.get(r.team_id, 0) + r.points)
            d = next((x for x in self.all_drivers if x.id == r.driver_id), None)
            if d:
                d.total_points += r.points
                d.races_completed += 1
                d.gain_race_xp(10 + max(0, 6 - r.position) if not r.dnf else 4)
                if r.position == 1 and not r.dnf: d.total_wins    += 1
                if r.position <= 3 and not r.dnf: d.total_podiums += 1
        for t in self.all_teams:
            t.season_points = self.standings_teams.get(t.id, 0)
            if t.can_afford_race():
                t.budget -= t.race_expense()
        if not self.player_driver.is_injured:
            races = max(1, len(self.season.rounds))
            net = hsng.net_per_race(self.player_driver.salary,
                                    self.profile.housing, races)
            self.profile.receive_salary(net)
            opt = hsng.HOUSING_OPTIONS.get(self.profile.housing, {})
            if opt.get("xp_bonus", 0) > 0:
                self.player_driver.gain_race_xp(opt["xp_bonus"])
        track.completed = True
        track.results = results
        self.season.current_round += 1
        self._add_news_from_race(results, events, "feature")
        return results, events

    def _add_news_from_race(self, results: list, events: list, race_type: str = "race"):
        """Gera notícias automáticas baseadas no resultado."""
        rnd = self.season.current_round if self.season else 0
        winner = next((r for r in results if r.position == 1 and not r.dnf), None)
        if winner:
            label = {"sprint": "Sprint", "feature": "Feature Race"}.get(race_type, "Corrida")
            self._push_news("race", f"{winner.driver_name} vence a {label} em {self.current_round().track_name if self.current_round() else '?'}!",
                           driver_id=winner.driver_id, team_id=winner.team_id, round_number=rnd)
        for ev in events:
            etype = getattr(ev, "event_type", "")
            if etype in ("engine_failure", "crash", "puncture"):
                desc = getattr(ev, "description", "")
                self._push_news("race", desc, round_number=rnd)
        # Acidente grave: tira piloto da próxima rodada
        for d in self.all_drivers:
            if d.is_injured:
                self._push_news("injury",
                    f"{d.name} lesionado — fora por {d.injury_races_remaining} corrida(s).",
                    driver_id=d.id, round_number=rnd)

    def _push_news(self, category: str, headline: str, body: str = "",
                   driver_id=None, team_id=None, round_number: int = 0):
        item = {"year": self.career_year, "round": round_number,
                "category": category, "headline": headline, "body": body,
                "driver_id": driver_id, "team_id": team_id}
        self.news_feed.append(item)
        if len(self.news_feed) > 50:
            self.news_feed = self.news_feed[-50:]

    # ── Standings ─────────────────────────────────────────────────────────────

    def driver_standings(self) -> List[Tuple[int, Driver, int]]:
        ranked = sorted(
            [(d, self.standings_drivers.get(d.id, 0)) for d in self.all_drivers],
            key=lambda x: x[1], reverse=True,
        )
        return [(i + 1, d, pts) for i, (d, pts) in enumerate(ranked)]

    def team_standings(self) -> List[Tuple[int, Team, int]]:
        ranked = sorted(
            [(t, self.standings_teams.get(t.id, 0)) for t in self.all_teams],
            key=lambda x: x[1], reverse=True,
        )
        return [(i + 1, t, pts) for i, (t, pts) in enumerate(ranked)]

    def player_position(self) -> int:
        for pos, d, _ in self.driver_standings():
            if d.id == self.player_driver.id:
                return pos
        return 99

    def season_complete(self) -> bool:
        return (self.season is not None and
                self.season.current_round >= len(self.season.rounds))

    def is_top_series(self) -> bool:
        return self.current_series_id == SERIES_PROGRESSION[-1]

    # ── Fim de temporada ──────────────────────────────────────────────────────

    # Categorias onde o campeão é obrigado a subir
    _CHAMPION_MUST_PROMOTE = {"formula_3", "formula_2"}

    def end_of_season(self) -> dict:
        drv_st  = self.driver_standings()
        team_st = self.team_standings()
        pos     = self.player_position()
        promo_spots = self.series_rules.get("promotion_spots", 3)
        can_promote = (pos <= promo_spots and not self.is_top_series())

        # Regra do campeão: F2/F3 campeão NÃO pode ficar na mesma categoria
        is_champion = (pos == 1)
        champion_must_promote = (
            is_champion
            and self.current_series_id in self._CHAMPION_MUST_PROMOTE
            and not self.is_top_series()
        )
        if champion_must_promote:
            can_promote = True  # força promoção mesmo que bloqueado por spots

        # Gate de Super Licença para F1
        sl_blocked = False
        sl_block_reason = ""
        if self.current_series_id == "formula_2" and can_promote:
            ok, reason = sl.check_f1_eligibility(self.player_driver)
            if not ok:
                can_promote = False
                sl_blocked  = True
                sl_block_reason = reason

        # Acumula pontos SL
        sl_earned = sl.award_season_sl_points(
            self.player_driver, self.current_series_id, pos, self.career_year)

        # Academia: bônus de potencial + estipêndio
        if self.player_driver.academy_id:
            acad.apply_potential_bonus(self.player_driver, self.player_driver.academy_id)
            ac = acad.get_academy(self.player_driver.academy_id)
            if ac:
                self.profile.receive_salary(ac.annual_stipend)

        # Salário restante (FDS)
        self.profile.receive_salary(self.player_driver.salary // 10)

        # Prêmio por posição (vai para dinheiro pessoal do piloto)
        pm = prize_money(pos)
        self.profile.receive_salary(pm)

        # Desenvolvimento do piloto (deltas para mostrar na UI)
        skill_deltas = self.player_driver.age_up()
        self.profile.age += 1

        # Histórico
        self.player_driver.series_history.append({
            "year": self.current_series_id, "series": self.current_series_id,
            "pos": pos,
        })
        self.profile.add_history(
            year=self.career_year,
            series=self.series_rules["name"],
            team=self.current_team.name if self.current_team else "?",
            position=pos,
            promoted=can_promote,
        )

        # Avança NPCs: SL, XP, idade (ecossistema vivo)
        self._advance_npcs()

        # Notícia de fim de temporada
        self._push_news("promotion",
            f"Temporada {self.career_year} encerrada — {self.player_driver.name} terminou em P{pos}.",
            driver_id=self.player_driver.id, round_number=len(self.season.rounds))

        if is_champion and self.current_series_id in self._CHAMPION_MUST_PROMOTE:
            self._push_news("promotion",
                f"{self.player_driver.name} e campeao de {self.series_rules['name']}! "
                f"Obrigado a subir de categoria.",
                driver_id=self.player_driver.id, round_number=len(self.season.rounds))

        return {
            "champion_driver":      drv_st[0][1].name if drv_st else "?",
            "champion_team":        team_st[0][1].name if team_st else "?",
            "player_position":      pos,
            "promoted":             can_promote,
            "champion_must_promote": champion_must_promote,
            "is_champion":          is_champion,
            "sl_earned":            sl_earned,
            "sl_total":             self.player_driver.super_licence_points,
            "sl_blocked":           sl_blocked,
            "sl_block_reason":      sl_block_reason,
            "prize_money":          pm,
            "personal_money":       self.profile.personal_money,
            "promotes_to":          self.series_rules.get("promotes_to", ""),
            "skill_deltas":         skill_deltas,
        }

    def _advance_npcs(self):
        """Avança NPCs ao fim de temporada: SL, XP, idade."""
        drv_st = self.driver_standings()
        for rank, d, _pts in drv_st:
            if d.id == self.player_driver.id:
                continue
            # SL baseado na posição final
            sl.award_season_sl_points(d, self.current_series_id, rank, self.career_year)
            d.age_up()
            d.gain_race_xp(30)
            # Salva estado para próxima temporada
            self._npc_state[d.id] = {
                "sl_pts": d.super_licence_points,
                "sl_history": dict(d.sl_points_history),
                "experience": d.experience,
                "age": d.age,
                "speed": d.speed,
                "consistency": d.consistency,
                "rain": d.rain,
                "overtaking": d.overtaking,
                "defence": d.defence,
                "tyre_mgmt": d.tyre_mgmt,
                "feedback": d.feedback,
                "potential": d.potential,
            }

    def breaking_contract_penalty(self) -> int:
        """Multa que o piloto paga ao sair de contrato ativo: salário × anos restantes."""
        pd = self.player_driver
        if not pd or pd.contract_years <= 0:
            return 0
        return pd.salary * pd.contract_years

    def pay_breaking_penalty(self) -> int:
        """Debita a multa do dinheiro pessoal. Retorna valor pago (pode ir negativo)."""
        penalty = self.breaking_contract_penalty()
        if penalty > 0:
            self.profile.personal_money -= penalty
            self._push_news("contract",
                f"Multa de quebra de contrato: -€{penalty:,.0f}",
                driver_id=self.player_driver.id if self.player_driver else None,
                round_number=self.season.current_round if self.season else 0)
        return penalty

    def receive_firing_penalty(self, amount: int):
        """Equipe paga multa ao piloto por demissão imediata."""
        self.profile.receive_salary(amount)
        self._push_news("contract",
            f"Multa de demissão recebida: +€{amount:,.0f}",
            driver_id=self.player_driver.id if self.player_driver else None,
            round_number=self.season.current_round if self.season else 0)

    def contract_signed(self) -> bool:
        return self._contract_next_year is not None

    def sign_contract(self, team_id: str, series_id: str):
        self._contract_next_year = team_id
        self._contract_next_series = series_id
        self._push_news("contract",
            f"{self.player_driver.name} assina contrato com {team_id} para {series_id}.",
            driver_id=self.player_driver.id, round_number=self.season.current_round if self.season else 0)

    def start_new_season(self, promote: bool, new_team_id: Optional[str] = None):
        """Carrega próxima temporada. new_team_id: se oferta foi aceita."""
        old_series = self.current_series_id

        if promote and not self.is_top_series():
            idx = SERIES_PROGRESSION.index(old_series)
            self.current_series_id = SERIES_PROGRESSION[idx + 1]

        self.career_year  += 1
        self.season_number += 1

        # Usa equipe assinada se existir, senão usa oferta pendente ou permanece
        effective_team_id = (
            self._contract_next_year or
            new_team_id or
            (self.current_team.id if self.current_team else None)
        )
        # Limpa contrato assinado
        self._contract_next_year = None
        self._contract_next_series = None

        # Salva estado do piloto do jogador
        pd = self.player_driver

        self._load_world(self.current_series_id)

        # Aplica estado salvo de NPCs (ecossistema vivo)
        for d in self.all_drivers:
            if d.id in self._npc_state:
                st = self._npc_state[d.id]
                d.super_licence_points = max(d.super_licence_points, st["sl_pts"])
                d.sl_points_history.update(st["sl_history"])
                d.experience = max(d.experience, st["experience"])
                d.age = max(d.age, st["age"])
                for attr in ("speed", "consistency", "rain", "overtaking",
                             "defence", "tyre_mgmt", "feedback", "potential"):
                    setattr(d, attr, max(getattr(d, attr), st.get(attr, 0)))

        # Reinjeta jogador
        self.player_driver = pd
        self.all_drivers.append(pd)

        # Determina equipe
        target_team_id = effective_team_id or self.all_teams[0].id
        self.current_team = next(
            (t for t in self.all_teams if t.id == target_team_id), self.all_teams[0])
        self.current_team.is_player_team = True
        self.player_driver.team_id = self.current_team.id
        if pd.id not in self.current_team.drivers:
            self.current_team.drivers.insert(0, pd.id)

        assign_ai_drivers(self.all_teams, self.all_drivers, exclude_ids=[pd.id])
        self._start_season()
