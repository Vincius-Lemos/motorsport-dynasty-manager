import random
import math
from typing import List, Dict, Tuple, Optional
from .models import Driver, Team, RaceResult, RaceEvent, SeasonRound

TYRE_DATA = {
    "soft":   {"pace_bonus": 1.8,  "wear_rate": 2.2, "min_laps": 8,  "max_laps": 18, "color": "S"},
    "medium": {"pace_bonus": 0.0,  "wear_rate": 1.4, "min_laps": 14, "max_laps": 28, "color": "M"},
    "hard":   {"pace_bonus": -1.2, "wear_rate": 0.9, "min_laps": 20, "max_laps": 40, "color": "H"},
}

SCORING = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]

EVENT_CHANCES = {
    "safety_car": 0.20,
    "engine_failure": 0.03,
    "puncture": 0.04,
    "crash": 0.03,
    "spin": 0.05,
}


class DriverRaceState:
    def __init__(self, driver: Driver, team: Team, strategy: List[str], base_lap: float):
        self.driver = driver
        self.team = team
        self.strategy = list(strategy)
        self.current_tyre_idx = 0
        self.current_tyre = strategy[0]
        self.tyre_age = 0
        self.total_time = 0.0
        self.pit_stops = 0
        self.tyre_history = []
        self.position = 0
        self.gap_to_leader = 0.0
        self.dnf = False
        self.dnf_reason = ""
        self.base_lap = base_lap
        self.fastest_lap_time = float("inf")
        self.laps_completed = 0

    def pace_rating(self, is_wet: bool = False) -> float:
        drv = self.driver
        team = self.team
        driver_component = drv.speed * 0.55 + drv.consistency * 0.30 + drv.tyre_mgmt * 0.15
        if is_wet:
            driver_component = drv.rain * 0.55 + drv.consistency * 0.25 + drv.tyre_mgmt * 0.20
        car_component = team.car_performance
        return driver_component * 0.40 + car_component * 0.60

    def lap_time(self, track: SeasonRound, safety_car: bool = False, is_wet: bool = False) -> float:
        tyre_info = TYRE_DATA[self.current_tyre]
        wear_factor = self.tyre_age / tyre_info["max_laps"]
        tyre_penalty = wear_factor ** 1.5 * 2.5
        pace_bonus = tyre_info["pace_bonus"]
        pace = self.pace_rating(is_wet)
        pace_offset = (90.0 - pace) * 0.04
        noise = random.gauss(0, 0.25)
        lap = self.base_lap + pace_offset - pace_bonus * 0.1 + tyre_penalty + noise
        if safety_car:
            lap = self.base_lap * 1.30 + random.uniform(-0.1, 0.1)
        return max(self.base_lap * 0.92, lap)

    def needs_pit(self, laps_left: int) -> bool:
        tyre_info = TYRE_DATA[self.current_tyre]
        tyre_over_limit = self.tyre_age >= tyre_info["max_laps"]
        next_stop_idx = self.current_tyre_idx + 1
        if next_stop_idx >= len(self.strategy):
            return tyre_over_limit
        laps_on_next = laps_left
        next_tyre = self.strategy[next_stop_idx]
        next_max = TYRE_DATA[next_tyre]["max_laps"]
        if laps_on_next <= next_max and self.tyre_age >= tyre_info["min_laps"]:
            lap_threshold = tyre_info["max_laps"] - random.randint(0, 4)
            return self.tyre_age >= lap_threshold or tyre_over_limit
        return tyre_over_limit

    def do_pit(self, pit_time: float):
        self.tyre_history.append((self.current_tyre, self.tyre_age))
        self.current_tyre_idx += 1
        if self.current_tyre_idx < len(self.strategy):
            self.current_tyre = self.strategy[self.current_tyre_idx]
        self.tyre_age = 0
        self.pit_stops += 1
        self.total_time += pit_time + random.gauss(0, 0.3)


def pick_strategy(driver: Driver, team: Team, track: SeasonRound) -> List[str]:
    wear = track.tyre_wear_index
    feed = driver.feedback / 100.0
    mgmt = driver.tyre_mgmt / 100.0
    options = []
    if wear <= 4:
        options = [["soft", "medium"], ["soft", "hard"], ["medium", "soft"]]
    elif wear <= 6:
        options = [["medium", "hard"], ["soft", "medium"], ["medium", "medium"]]
    else:
        options = [["hard", "medium"], ["medium", "hard"], ["hard", "hard"]]
    weights = [3 + (mgmt + feed) * 2, 2, 1]
    return random.choices(options, weights=weights[:len(options)])[0]


def simulate_race(
    track: SeasonRound,
    drivers: List[Driver],
    teams: Dict[str, Team],
    base_lap_time: float = 95.0,
    pit_stop_time: float = 25.0,
    player_strategy: Optional[Dict[str, List[str]]] = None,
) -> Tuple[List[RaceResult], List[RaceEvent]]:

    states: List[DriverRaceState] = []
    for drv in drivers:
        team = teams.get(drv.team_id)
        if not team:
            continue
        if player_strategy and drv.id in player_strategy:
            strategy = player_strategy[drv.id]
        else:
            strategy = pick_strategy(drv, team, track)
        st = DriverRaceState(drv, team, strategy, base_lap_time)
        qual_noise = random.gauss(0, 0.4)
        pace_penalty = (90.0 - st.pace_rating()) * 0.05
        st.total_time = qual_noise + pace_penalty
        states.append(st)

    states.sort(key=lambda s: s.total_time)
    for i, st in enumerate(states):
        st.position = i + 1
        st.gap_to_leader = st.total_time - states[0].total_time if i > 0 else 0.0

    events: List[RaceEvent] = []
    safety_car_laps_left = 0

    for lap in range(1, track.laps + 1):
        safety_car = safety_car_laps_left > 0
        if not safety_car and random.random() < EVENT_CHANCES["safety_car"]:
            safety_car_laps_left = random.randint(3, 6)
            events.append(RaceEvent(lap, "safety_car", f"Safety Car deployed on lap {lap}!"))

        if safety_car_laps_left > 0:
            safety_car_laps_left -= 1
            if safety_car_laps_left == 0:
                events.append(RaceEvent(lap, "safety_car_end", f"Safety Car withdrawn, lap {lap}"))

        for st in states:
            if st.dnf:
                continue

            # Random DNF events
            for ev_type, chance in [("engine_failure", EVENT_CHANCES["engine_failure"]),
                                     ("puncture", EVENT_CHANCES["puncture"]),
                                     ("crash", EVENT_CHANCES["crash"])]:
                if random.random() < chance / track.laps:
                    st.dnf = True
                    st.dnf_reason = ev_type.replace("_", " ").title()
                    events.append(RaceEvent(lap, ev_type, f"{st.driver.name} — {st.dnf_reason} on lap {lap}", st.driver.id))
                    break

            if st.dnf:
                st.laps_completed = lap - 1
                continue

            laps_left = track.laps - lap
            if st.needs_pit(laps_left) and laps_left > 0:
                st.do_pit(pit_stop_time)

            lt = st.lap_time(track, safety_car)
            st.total_time += lt
            st.tyre_age += 1
            st.laps_completed = lap
            if lt < st.fastest_lap_time:
                st.fastest_lap_time = lt

    states.sort(key=lambda s: (s.dnf, s.total_time))
    for i, st in enumerate(states):
        st.position = i + 1

    # Award fastest lap bonus point
    active = [s for s in states if not s.dnf]
    if active:
        fl_driver = min(active, key=lambda s: s.fastest_lap_time)
        fl_driver.fastest_lap_time = fl_driver.fastest_lap_time  # marker below

    results: List[RaceResult] = []
    fl_state = min(active, key=lambda s: s.fastest_lap_time) if active else None

    for st in states:
        pts = 0
        if not st.dnf and st.position <= len(SCORING):
            pts = SCORING[st.position - 1]
        is_fl = (fl_state and st.driver.id == fl_state.driver.id and st.position <= 10)
        if is_fl:
            pts += 1

        tyre_hist = st.tyre_history + [(st.current_tyre, st.tyre_age)]
        results.append(RaceResult(
            driver_id=st.driver.id,
            driver_name=st.driver.name,
            team_id=st.team.id,
            team_name=st.team.name,
            position=st.position,
            laps_completed=st.laps_completed,
            total_time=st.total_time,
            pit_stops=st.pit_stops,
            tyre_strategy=[f"{t}({a}L)" for t, a in tyre_hist],
            fastest_lap=is_fl,
            dnf=st.dnf,
            dnf_reason=st.dnf_reason,
            points=pts,
        ))

    return results, events
