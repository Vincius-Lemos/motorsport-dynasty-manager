"""
ManagerCareer — carreira onde o jogador GERENCIA uma equipe.

O jogador não é um piloto. Contrata 2 pilotos da IA, gerencia
budget, facilities, sponsors, desenvolvimento do carro.
Ofertas chegam para a EQUIPE (mover de categoria).
SL/academia/lesões são mecânicas dos pilotos contratados, não do jogador.
"""
import random
from typing import Dict, List, Optional, Tuple

from .models import Driver, Team, Season, SeasonRound
from .player_profile import PlayerProfile
from .career import (
    SERIES_PROGRESSION, load_series, load_drivers_for_series,
    load_teams_for_series, build_season, assign_ai_drivers,
    series_above, series_below, prize_money,
    RACE_WEEKEND_FORMAT, SPRINT_SCORING, FEATURE_SCORING, sprint_grid_from_quali,
)
from .race_engine import simulate_race
from . import injuries as inj
from . import super_licence as sl
from . import academies as acad


class ManagerCareer:
    def __init__(self, profile: PlayerProfile):
        self.profile = profile

        self.all_drivers: List[Driver] = []
        self.all_teams:   List[Team]   = []
        self.player_team: Optional[Team] = None
        self.season: Optional[Season] = None
        self.series_rules: dict = {}
        self.current_series_id: str = "formula_4"
        self.career_year: int = 2027
        self.season_number: int = 1

        self.standings_drivers: Dict[str, int] = {}
        self.standings_teams:   Dict[str, int] = {}
        self.injury_log: list = []
        self._pending_offer: Optional[dict] = None
        self.news_feed: list = []
        self._npc_state: dict = {}

    # ── IDs dos pilotos contratados pelo jogador ──────────────────────────────

    @property
    def player_driver_ids(self) -> List[str]:
        return list(self.player_team.drivers) if self.player_team else []

    def player_drivers(self) -> List[Driver]:
        return [d for d in self.all_drivers if d.id in self.player_driver_ids]

    # ── Setup ─────────────────────────────────────────────────────────────────

    def new_career(self, series_id: str, team_id: str,
                   driver1_id: str, driver2_id: str) -> str:
        self.current_series_id = series_id
        self.career_year = 2027
        self.season_number = 1
        self._load_world(series_id)

        self.player_team = next(t for t in self.all_teams if t.id == team_id)
        self.player_team.is_player_team = True
        self.profile.team_id = team_id

        # Deduz custo de entrada do dinheiro pessoal (já pago em retire_to_manager)
        for pid in (driver1_id, driver2_id):
            d = next(d for d in self.all_drivers if d.id == pid)
            d.team_id = team_id
            d.contract_years = 1
        self.player_team.drivers = [driver1_id, driver2_id]

        assign_ai_drivers(self.all_teams, self.all_drivers,
                          exclude_ids=[driver1_id, driver2_id])
        self._start_season()
        return (f"Gestao iniciada: {self.player_team.name} — "
                f"{self.series_rules['name']} {self.career_year}")

    def _load_world(self, series_id: str):
        self.series_rules = load_series(series_id)
        self.all_drivers  = load_drivers_for_series(series_id, self.career_year)
        self.all_teams    = load_teams_for_series(series_id)

    def _start_season(self):
        self.season = build_season(
            self.current_series_id, self.career_year,
            self.series_rules, self.all_teams, self.all_drivers)
        self.standings_drivers = {d.id: 0 for d in self.all_drivers}
        self.standings_teams   = {t.id: 0 for t in self.all_teams}
        self.injury_log = []

    # ── Corrida ───────────────────────────────────────────────────────────────

    def current_round(self) -> Optional[SeasonRound]:
        if not self.season:
            return None
        cr = self.season.current_round
        return self.season.rounds[cr] if cr < len(self.season.rounds) else None

    def run_qualifying(self, is_wet: bool = False) -> Optional[dict]:
        from . import qualifying as q
        track = self.current_round()
        if not track:
            return None
        active = [d for d in self.all_drivers if not d.is_injured]
        teams = {t.id: t for t in self.all_teams}
        res = q.simulate_qualifying(active, teams, self.current_series_id, track,
                                    self.series_rules["base_lap_time_seconds"], is_wet)
        self._grid_order = res["order"]
        for d in active:
            d.gain_race_xp(3)
        return res

    def simulate_next_race(self, player_strategy=None) -> Tuple[list, list]:
        track = self.current_round()
        if not track:
            return [], []

        injury_events = []
        fp1_events    = []

        # Recuperação de lesionados
        for d in self.all_drivers:
            if d.is_injured:
                inj.process_recovery(d)

        # Lesões para todos os pilotos ativos
        for d in self.all_drivers:
            if not d.is_injured:
                sev = inj.roll_injury(d, track.track_type)
                if sev:
                    ev = inj.apply_injury(d, sev)
                    injury_events.append(ev)
                    self.injury_log.append(ev)

        # FP1 academia para pilotos do jogador (não em F1)
        if self.current_series_id != "formula_1":
            for d in self.player_drivers():
                if d.academy_id and acad.roll_fp1_session(d, d.academy_id, self.current_series_id):
                    pts = sl.award_fp1_bonus(d)
                    d.gain_race_xp(8)
                    fp1_events.append({"driver": d.name, "sl_pts": pts})

        active = [d for d in self.all_drivers if not d.is_injured]
        teams_dict = {t.id: t for t in self.all_teams}
        results, events = simulate_race(
            track=track,
            drivers=active,
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
                d.gain_race_xp(10 + max(0, 6 - r.position) if not r.dnf else 4)
                if r.position == 1 and not r.dnf: d.total_wins    += 1
                if r.position <= 3 and not r.dnf: d.total_podiums += 1

        for t in self.all_teams:
            t.season_points = self.standings_teams.get(t.id, 0)
            if t.can_afford_race():
                t.budget -= t.race_expense()

        track.completed = True
        track.results   = results
        self.season.current_round += 1

        meta_events = list(events)
        for ev in injury_events:
            meta_events.append(
                type("Ev", (), {"lap": 0, "event_type": "injury",
                                "description": ev["description"],
                                "affects_driver": ev["driver_id"]})())
        for ev in fp1_events:
            meta_events.append(
                type("Ev", (), {"lap": 0, "event_type": "fp1_bonus",
                                "description": f"FP1: {ev['driver']} +{ev['sl_pts']} pts SL",
                                "affects_driver": None})())
        return results, meta_events

    def is_sprint_feature_weekend(self) -> bool:
        return RACE_WEEKEND_FORMAT.get(self.current_series_id) == "sprint_feature"

    def simulate_sprint_race(self, is_wet: bool = False) -> Tuple[list, list]:
        """Simula a sprint race do fim de semana F2/F3."""
        track = self.current_round()
        if not track:
            return [], []
        grid = sprint_grid_from_quali(getattr(self, "_grid_order", []) or [], self.current_series_id)
        scoring = SPRINT_SCORING.get(self.current_series_id, [8, 7, 6, 5, 4, 3, 2, 1])
        sprint_laps = max(10, track.laps // 3)
        active = [d for d in self.all_drivers if not d.is_injured]
        teams_dict = {t.id: t for t in self.all_teams}
        results, events = simulate_race(
            track=track,
            drivers=active,
            teams=teams_dict,
            base_lap_time=self.series_rules["base_lap_time_seconds"],
            pit_stop_time=self.series_rules["pit_stop_time_seconds"],
            grid_order=grid,
            scoring_override=scoring,
            laps_override=sprint_laps,
            fastest_lap_bonus=False,
        )
        for r in results:
            self.standings_drivers[r.driver_id] = (
                self.standings_drivers.get(r.driver_id, 0) + r.points)
            self.standings_teams[r.team_id] = (
                self.standings_teams.get(r.team_id, 0) + r.points)
            d = next((x for x in self.all_drivers if x.id == r.driver_id), None)
            if d:
                d.total_points += r.points
                d.gain_race_xp(6 if not r.dnf else 2)
        self._feature_grid = [r.driver_id for r in sorted(results, key=lambda r: r.position)]
        self._add_news_from_race(results, events, "sprint")
        return results, events

    def simulate_feature_race(self, player_strategy=None) -> Tuple[list, list]:
        """Simula a feature race com grid = resultado da sprint."""
        track = self.current_round()
        if not track:
            return [], []
        grid = getattr(self, "_feature_grid", None) or getattr(self, "_grid_order", None)
        scoring = FEATURE_SCORING.get(self.current_series_id, [25, 18, 15, 12, 10, 8, 6, 4, 2, 1])
        active = [d for d in self.all_drivers if not d.is_injured]
        teams_dict = {t.id: t for t in self.all_teams}
        results, events = simulate_race(
            track=track,
            drivers=active,
            teams=teams_dict,
            base_lap_time=self.series_rules["base_lap_time_seconds"],
            pit_stop_time=self.series_rules["pit_stop_time_seconds"],
            player_strategy=player_strategy,
            grid_order=grid,
            scoring_override=scoring,
        )
        self._feature_grid = None
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
                d.gain_race_xp(10 + max(0, 6 - r.position) if not r.dnf else 4)
                if r.position == 1 and not r.dnf: d.total_wins    += 1
                if r.position <= 3 and not r.dnf: d.total_podiums += 1
        for t in self.all_teams:
            t.season_points = self.standings_teams.get(t.id, 0)
            if t.can_afford_race():
                t.budget -= t.race_expense()
        track.completed = True
        track.results = results
        self.season.current_round += 1
        self._add_news_from_race(results, events, "feature")
        return results, events

    def _add_news_from_race(self, results: list, events: list, race_type: str = "race"):
        rnd = self.season.current_round if self.season else 0
        winner = next((r for r in results if r.position == 1 and not r.dnf), None)
        if winner:
            label = {"sprint": "Sprint", "feature": "Feature Race"}.get(race_type, "Corrida")
            track_name = self.current_round().track_name if self.current_round() else "?"
            self._push_news("race",
                f"{winner.driver_name} vence a {label} em {track_name}!",
                driver_id=winner.driver_id, team_id=winner.team_id, round_number=rnd)
        for ev in events:
            etype = getattr(ev, "event_type", "")
            if etype in ("engine_failure", "crash", "puncture"):
                self._push_news("race", getattr(ev, "description", ""), round_number=rnd)
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

    def player_team_position(self) -> int:
        for pos, t, _ in self.team_standings():
            if t.is_player_team:
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
        pos     = self.player_team_position()
        promo_spots = self.series_rules.get("promotion_spots", 3)
        can_promote = (pos <= promo_spots and not self.is_top_series())

        # Regra do campeão de equipes: F2/F3 campeão é obrigado a subir
        is_champion = (pos == 1)
        champion_must_promote = (
            is_champion
            and self.current_series_id in self._CHAMPION_MUST_PROMOTE
            and not self.is_top_series()
        )
        if champion_must_promote:
            can_promote = True

        # Renda de patrocinadores
        sponsor_income = 0
        for s in self.player_team.sponsors:
            req = s["requirement"] if isinstance(s, dict) else s.requirement
            val = s["value"]       if isinstance(s, dict) else s.value
            if req == "none":
                sponsor_income += val
            else:
                try:
                    threshold = int(req.replace("top", "").replace("_champion", ""))
                    if pos <= threshold:
                        sponsor_income += val
                except ValueError:
                    pass

        sponsor_income = int(sponsor_income * self.player_team.facilities.sponsor_multiplier())
        self.player_team.budget += sponsor_income

        # Prêmio por posição (vai para o orçamento da equipe)
        pm = prize_money(pos)
        self.player_team.budget += pm

        # Dividendo pessoal do gerente (10% do lucro)
        dividend = int((sponsor_income + pm) * 0.10)
        self.profile.receive_salary(dividend)

        # SL e potencial para pilotos contratados
        sl_awards = {}
        for d in self.player_drivers():
            d_pos = next((p for p, drv, _ in drv_st if drv.id == d.id), 20)
            earned = sl.award_season_sl_points(d, self.current_series_id, d_pos, self.career_year)
            if d.academy_id:
                acad.apply_potential_bonus(d, d.academy_id)
            sl_awards[d.name] = {"pos": d_pos, "earned": earned, "total": d.super_licence_points}

        # Avança NPCs (ecossistema vivo) e desenvolve pilotos do jogador
        self._advance_npcs()
        for d in self.player_drivers():
            d.age_up()
        self.profile.age += 1

        self.profile.add_history(
            year=self.career_year,
            series=self.series_rules["name"],
            team=self.player_team.name,
            position=pos,
            promoted=can_promote,
        )

        return {
            "champion_driver":       drv_st[0][1].name if drv_st else "?",
            "champion_team":         team_st[0][1].name if team_st else "?",
            "team_position":         pos,
            "promoted":              can_promote,
            "champion_must_promote": champion_must_promote,
            "is_champion":           is_champion,
            "sponsor_income":        sponsor_income,
            "prize_money":           pm,
            "dividend":              dividend,
            "final_budget":          self.player_team.budget,
            "sl_awards":             sl_awards,
            "promotes_to":           self.series_rules.get("promotes_to", ""),
        }

    def start_new_season(self, promote: bool):
        old_series = self.current_series_id
        if promote and not self.is_top_series():
            idx = SERIES_PROGRESSION.index(old_series)
            self.current_series_id = SERIES_PROGRESSION[idx + 1]

        self.career_year  += 1
        self.season_number += 1

        # Preserva estado da equipe do jogador
        pt = self.player_team
        saved_drivers = list(pt.drivers)
        driver_snapshots = {}
        for d in self.all_drivers:
            if d.id in saved_drivers:
                driver_snapshots[d.id] = {
                    k: getattr(d, k)
                    for k in ("super_licence_points", "sl_points_history", "fp1_sessions",
                              "academy_id", "total_points", "total_wins", "total_podiums",
                              "series_history", "health", "age", "speed", "consistency",
                              "rain", "overtaking", "defence", "tyre_mgmt", "feedback",
                              "potential", "salary", "popularity", "aggressiveness",
                              "injury_races_remaining", "injury_type")
                }

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

        # Recria equipe do jogador preservando atributos
        new_base = next((t for t in self.all_teams if t.id == pt.id), self.all_teams[0])
        new_team = Team(
            id=pt.id, name=pt.name, short=pt.short, color=pt.color,
            chassis=pt.chassis, aerodynamics=pt.aerodynamics,
            reliability=pt.reliability, pit_crew=pt.pit_crew,
            engineers=pt.engineers, factory=pt.factory,
            reputation=pt.reputation, budget=pt.budget,
            base_cost_per_race=new_base.base_cost_per_race,
            sponsors=pt.sponsors, is_player_team=True, drivers=[],
            academy=pt.academy,
            fac_factory=pt.fac_factory, fac_simulator=pt.fac_simulator,
            fac_r_and_d=pt.fac_r_and_d, fac_pit_crew=pt.fac_pit_crew,
            fac_marketing=pt.fac_marketing,
        )
        for i, t in enumerate(self.all_teams):
            if t.id == pt.id:
                self.all_teams[i] = new_team
                break
        self.player_team = new_team

        # Reanexa pilotos do jogador
        for pid in saved_drivers:
            d = next((x for x in self.all_drivers if x.id == pid), None)
            if d and pid in driver_snapshots:
                for attr, val in driver_snapshots[pid].items():
                    setattr(d, attr, val)
                d.team_id = new_team.id
                d.health = min(100, d.health + 20)  # recuperação off-season
                d.injury_races_remaining = 0
                d.injury_type = ""
                new_team.drivers.append(pid)

        assign_ai_drivers(self.all_teams, self.all_drivers, exclude_ids=list(new_team.drivers))
        self._start_season()

    def _advance_npcs(self):
        """Avança NPCs ao fim de temporada: SL, XP, idade. Persiste estado."""
        from . import super_licence as sl_mod
        drv_st = self.driver_standings()
        player_ids = set(self.player_driver_ids)
        for rank, d, _pts in drv_st:
            if d.id in player_ids:
                continue
            sl_mod.award_season_sl_points(d, self.current_series_id, rank, self.career_year)
            d.age_up()
            d.gain_race_xp(30)
            self._npc_state[d.id] = {
                "sl_pts":      d.super_licence_points,
                "sl_history":  dict(d.sl_points_history),
                "experience":  d.experience,
                "age":         d.age,
                "speed":       d.speed,
                "consistency": d.consistency,
                "rain":        d.rain,
                "overtaking":  d.overtaking,
                "defence":     d.defence,
                "tyre_mgmt":   d.tyre_mgmt,
                "feedback":    d.feedback,
                "potential":   d.potential,
            }

    # ── CLT check ────────────────────────────────────────────────────────────

    def is_clt(self) -> bool:
        """Retorna True se equipe ficou sem pilotos e sem budget para contratar."""
        return (len(self.player_team.drivers) == 0 and
                self.player_team.budget < 20_000)
