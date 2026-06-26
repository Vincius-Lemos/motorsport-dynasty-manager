#!/usr/bin/env python3
"""Motorsport Dynasty Manager — v0.4"""
import os
import sys
import time

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from game.player_profile import PlayerProfile, MANAGER_ENTRY_COST, DRIVER_AGE_GATE
from game.driver_career  import DriverCareer
from game.manager_career import ManagerCareer
from game.career import (
    SERIES_PROGRESSION, load_drivers_for_series, load_teams_for_series, load_series
)
from game.transfer_market import TransferMarket, driver_market_value
from game.offers import generate_offer, OFFER_TYPE_LABEL
from game.save_load import save_game, load_game, list_saves
from game import super_licence as sl
from game import academies as acad
from game import injuries as inj

console = Console() if HAS_RICH else None

SERIES_LABEL = {
    "formula_4":        "[F4]",
    "formula_regional": "[FR]",
    "formula_3":        "[F3]",
    "formula_2":        "[F2]",
    "formula_1":        "[F1]",
}

CLT_MESSAGES = {
    "formula_4":        "Voce virou fiscal de patio no Autodromo de Interlagos.",
    "formula_regional": "Agora e comentarista voluntario de F4 no YouTube.",
    "formula_3":        "Comentarista de YouTube sobre F1 — de graca.",
    "formula_2":        "Analista de telemetria para uma equipe de kart em Cascavel.",
    "formula_1":        "Embaixador de marca de relogios suicos. Boa aposentadoria.",
}


# ─── UI helpers ──────────────────────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def pr(msg, style=""):
    if HAS_RICH and style:
        console.print(msg, style=style)
    else:
        print(msg)

def hr(c="-", w=72):
    print(c * w)

def header(title, sub=""):
    clear()
    if HAS_RICH:
        body = f"[bold yellow]{title}[/bold yellow]"
        if sub:
            body += f"\n[dim]{sub}[/dim]"
        console.print(Panel(body, border_style="yellow"))
    else:
        hr("="); print(f"  {title}")
        if sub: print(f"  {sub}")
        hr("=")

def pause(msg="\nENTER para continuar..."):
    input(msg)

def ask(prompt, options=None, default=None):
    while True:
        val = input(f"  {prompt}: ").strip()
        if not val and default:
            return default
        if options is None or val.lower() in [o.lower() for o in options]:
            return val.lower() if options else val
        print(f"  Opcoes: {', '.join(options)}")

def pick(items, label_fn, title="Escolha"):
    print(f"\n  {title}:")
    for i, item in enumerate(items, 1):
        print(f"  [{i:>2}] {label_fn(item)}")
    while True:
        try:
            n = int(input("  > "))
            if 1 <= n <= len(items):
                return n - 1
        except ValueError:
            pass
        print(f"  Digite 1-{len(items)}")


# ─── CLT game over ────────────────────────────────────────────────────────────

def clt_game_over(series_id, history):
    clear(); hr("!")
    pr("  SITUACAO CRITICA — VOCE ESTA MAL", "bold red"); hr("!")
    pr(f"\n  >>> {CLT_MESSAGES.get(series_id, 'Virou CLT do automobilismo.')} <<<", "bold yellow")
    print("\n  Historico:")
    for h in history:
        print(f"    {h.year}  {h.series:<32} P{h.position}")
    pause("  ENTER para encerrar...")
    sys.exit(0)


# ─── Shared race display ──────────────────────────────────────────────────────

def show_race_results(results, events, track_name):
    header(f"Resultado: {track_name}")
    inj_evs = [e for e in events if e.event_type == "injury"]
    fp1_evs = [e for e in events if e.event_type == "fp1_bonus"]
    if inj_evs or fp1_evs:
        print("\n  EVENTOS PRE-CORRIDA:")
        for e in inj_evs:  pr(f"   [LESAO] {e.description}", "red")
        for e in fp1_evs:  pr(f"   [FP1]   {e.description}", "cyan")
    race_evs = [e for e in events if e.event_type not in ("injury","fp1_bonus")]
    if race_evs:
        print("\n  DURANTE A CORRIDA:")
        icons = {"safety_car":"SC","engine_failure":"DNF","crash":"DNF",
                 "puncture":"!","spin":"~","safety_car_end":"SC-end"}
        for e in race_evs[:8]:
            print(f"   V{e.lap:>2}: [{icons.get(e.event_type,'?')}] {e.description}")
    print()
    if HAS_RICH:
        tbl = Table(box=box.SIMPLE_HEAVY)
        for col in ["Pos","Piloto","Equipe","Pts","Pit","Pneus","Status"]:
            tbl.add_column(col, justify="right" if col in ("Pos","Pts","Pit") else "left")
        for r in results:
            pos = f"P{r.position}" if not r.dnf else "DNF"
            fl  = " *" if r.fastest_lap else ""
            st  = f"[red]DNF({r.dnf_reason})[/red]" if r.dnf else "[green]OK[/green]"
            tbl.add_row(pos, r.driver_name+fl, r.team_name,
                        str(r.points), str(r.pit_stops), "|".join(r.tyre_strategy), st)
        console.print(tbl)
    else:
        hr()
        for r in results:
            pos = f"P{r.position}" if not r.dnf else "DNF"
            st  = f"DNF:{r.dnf_reason}" if r.dnf else "OK"
            print(f"{pos:<4} {r.driver_name:<22} {r.team_name:<20} "
                  f"{r.points:>4}  {r.pit_stops}pit  {'|'.join(r.tyre_strategy)}  {st}")
        hr()


def show_driver_standings(standings, all_teams, player_id=None, player_team=None):
    if HAS_RICH:
        tbl = Table(title="Pilotos", box=box.SIMPLE_HEAVY)
        tbl.add_column("Pos", width=4, justify="right")
        tbl.add_column("Piloto", min_width=22)
        tbl.add_column("Equipe", min_width=18)
        tbl.add_column("Pts", justify="right", style="bold green")
        for pos, d, pts in standings[:15]:
            team = next((t for t in all_teams if d.id in t.drivers), None)
            is_player = (d.id == player_id) or (team and team.is_player_team)
            mark = " <" if is_player else ""
            style = "bold yellow" if is_player else ""
            tbl.add_row(str(pos), d.name+mark, team.name if team else "—",
                        str(pts), style=style)
        console.print(tbl)
    else:
        hr(); print("PILOTOS"); hr()
        for pos, d, pts in standings[:15]:
            team = next((t for t in all_teams if d.id in t.drivers), None)
            mark = " <" if (d.id == player_id or (team and team.is_player_team)) else ""
            print(f"  {pos:>2}. {d.name+mark:<24} {team.short if team else '---':<6} {pts:>4}")
        hr()


def show_team_standings(standings, player_team=None):
    if HAS_RICH:
        tbl = Table(title="Equipes", box=box.SIMPLE_HEAVY)
        tbl.add_column("Pos", width=4, justify="right")
        tbl.add_column("Equipe", min_width=22)
        tbl.add_column("Pts", justify="right", style="bold green")
        for pos, t, pts in standings:
            mark = " <" if t.is_player_team else ""
            tbl.add_row(str(pos), t.name+mark, str(pts))
        console.print(tbl)
    else:
        hr(); print("EQUIPES"); hr()
        for pos, t, pts in standings:
            mark = " <" if t.is_player_team else ""
            print(f"  {pos:>2}. {t.name+mark:<24} {pts:>4}")
        hr()


# ═══════════════════════════════════════════════════════════════════════════════
#  MODO PILOTO
# ═══════════════════════════════════════════════════════════════════════════════

def driver_new_career(profile: PlayerProfile) -> DriverCareer:
    header("NOVA CARREIRA — PILOTO", f"{profile.name}  |  {profile.age} anos  |  {profile.nationality}")
    teams   = load_teams_for_series("formula_4")
    drivers = load_drivers_for_series("formula_4")

    print("\n  Sua carreira começa na Formula 4.")
    team_idx = pick(teams,
        lambda t: f"{t.name:<22}  Rep:{t.reputation}  Chassi:{t.chassis}/100",
        "Escolha a equipe")
    pt = teams[team_idx]

    career = DriverCareer(profile)
    msg = career.new_career("formula_4", pt.id)
    pr(f"\n  {msg}", "green")
    pause()
    return career


def driver_race_menu(profile: PlayerProfile, career: DriverCareer):
    track = career.current_round()
    if not track:
        pr("  Temporada encerrada.", "yellow"); pause(); return
    total = len(career.season.rounds)
    cat   = SERIES_LABEL.get(career.current_series_id, "")
    header(f"{cat} Corrida {track.round_number}/{total} — {track.track_name}")

    pd = career.player_driver
    if pd.is_injured:
        pr(f"\n  VOCE ESTA LESIONADO ({pd.injury_type}) — "
           f"{pd.injury_races_remaining} corrida(s) de fora.", "red")
        pause(); return

    print(f"\n  Pista: {track.track_name} ({track.track_type})  "
          f"Desgaste:{track.tyre_wear_index}/10")
    print("  [1] Escolher pneus  [2] Auto  [0] Voltar")
    opt = ask("Opcao", ["0","1","2"], "2")
    if opt == "0": return

    strategy = {}
    if opt == "1":
        print(f"\n  {pd.name} — ex: S,M  ou  M,H  (ENTER=auto)")
        raw = input("  > ").strip().upper()
        mapping = {"S":"soft","M":"medium","H":"hard"}
        parts = [mapping[p] for p in raw.split(",") if p.strip() in mapping]
        if parts:
            strategy[pd.id] = parts

    print("\n  Simulando", end="", flush=True)
    for _ in range(6): time.sleep(0.25); print(".", end="", flush=True)
    print()
    results, events = career.simulate_next_race(strategy or None)
    show_race_results(results, events, track.track_name)

    # Posição do jogador
    player_result = next((r for r in results if r.driver_id == pd.id), None)
    if player_result:
        pr(f"\n  Voce terminou em P{player_result.position} — {player_result.points} pts", "bold")

    # Oferta dinâmica
    offer = generate_offer_driver(career)
    if offer:
        accepted = show_offer(offer)
        if accepted:
            career._pending_offer = offer
            pr(f"\n  Oferta aceita: {offer['from_team']} em {offer['from_series_label']}.", "green")
        else:
            pr("\n  Recusado.", "dim")

    pause()


def generate_offer_driver(career: DriverCareer) -> dict | None:
    """Gera oferta para o piloto (wrapper simples sobre offers.py)."""
    import random
    from game.career import series_above, series_below
    pd  = career.player_driver
    pos = career.player_position()
    total = len(career.all_teams)
    rounds_done  = career.season.current_round
    total_rounds = len(career.season.rounds)

    if random.random() > 0.28:
        return None

    top_half    = pos <= total // 2
    late_season = rounds_done >= total_rounds * 0.6
    has_above   = series_above(career.current_series_id) is not None
    has_below   = series_below(career.current_series_id) is not None

    weights = [
        (4.0 if top_half else 0.5) * (1.0 if has_above else 0.0),
        (0.3 if top_half else 2.0) * (1.0 if has_below else 0.0),
        2.5 if late_season else 1.5,
        1.0 if late_season else 0.5,
        0.2 if top_half else (2.5 if not late_season else 1.0),
    ]
    otype = random.choices(
        ["step_up","step_down","lateral_better","lateral_worse","fired"],
        weights=weights)[0]

    if otype == "step_up":
        next_s = series_above(career.current_series_id)
        if not next_s: return None
        if next_s == "formula_1":
            ok, reason = sl.check_f1_eligibility(pd)
            if not ok:
                pr(f"\n  [SL] Oferta de F1 bloqueada: {reason}", "dim")
                return None
        teams = load_teams_for_series(next_s)
        target = random.choice(teams[2:7] if len(teams) > 7 else teams)
        salary = max(pd.salary, int(target.budget * 0.12))
        return _build_offer_dict(otype, target, next_s, salary, random.randint(1,2))

    if otype == "step_down":
        prev_s = series_below(career.current_series_id)
        if not prev_s: return None
        teams = load_teams_for_series(prev_s)
        target = random.choice(teams[:4])
        salary = int(pd.salary * 1.2)
        return _build_offer_dict(otype, target, prev_s, salary, random.randint(1,2))

    if otype == "fired":
        others = [t for t in career.all_teams if t.id != (career.current_team.id if career.current_team else "")]
        if not others: return None
        target = random.choice(others[-3:])
        return _build_offer_dict(otype, target, career.current_series_id,
                                 int(pd.salary * 0.85), 1, forced=True)

    if otype == "lateral_better":
        better = [t for t in career.all_teams
                  if t.id != (career.current_team.id if career.current_team else "")
                  and t.car_performance > (career.current_team.car_performance if career.current_team else 0)]
        if not better: return None
        target = random.choice(better)
        salary = int(pd.salary * random.uniform(1.0, 1.2))
        return _build_offer_dict(otype, target, career.current_series_id, salary, random.randint(1,2))

    worse = [t for t in career.all_teams
             if t.id != (career.current_team.id if career.current_team else "")]
    if not worse: return None
    target = random.choice(worse)
    salary = int(pd.salary * random.uniform(1.2, 1.6))
    return _build_offer_dict(otype, target, career.current_series_id, salary, random.randint(1,2))


def _build_offer_dict(otype, team, series_id, salary, years, forced=False):
    labels = {
        "formula_4":"Formula 4","formula_regional":"Formula Regional",
        "formula_3":"Formula 3","formula_2":"Formula 2","formula_1":"Formula 1",
    }
    descs = {
        "step_up":        f"{team.name} quer voce na {labels.get(series_id,'?')}!",
        "step_down":      f"{team.name} oferece lideranca em {labels.get(series_id,'?')}.",
        "lateral_better": f"{team.name} quer voce (carro melhor: {team.car_performance:.0f}).",
        "lateral_worse":  f"{team.name} oferece mais salario.",
        "fired":          f"Sua equipe dispensa voce. {team.name} pode absorver.",
    }
    return {
        "type": otype, "from_team": team.name, "from_team_id": team.id,
        "from_series": series_id, "from_series_label": labels.get(series_id, series_id),
        "salary": salary, "years": years,
        "description": descs.get(otype, ""),
        "team_chassis": team.chassis, "team_rep": team.reputation,
        "forced": forced,
    }


def show_offer(offer: dict) -> bool:
    label = OFFER_TYPE_LABEL.get(offer["type"], "PROPOSTA")
    print(); hr("*")
    pr(f"  *** {label} ***", "bold yellow"); hr("*")
    print(f"\n  {offer['description']}")
    print(f"\n  Equipe:    {offer['from_team']}")
    print(f"  Categoria: {offer['from_series_label']}")
    print(f"  Chassi:    {offer.get('team_chassis','?')}/100")
    print(f"  Salario:   EUR {offer['salary']:,.0f}/ano")
    print(f"  Contrato:  {offer['years']} ano(s)")
    if offer.get("forced"):
        pr("  ** ATENCAO: Sua equipe esta te dispensando **", "red")
    return ask("Aceitar? [s/n]", ["s","n"], "n") == "s"


def driver_end_of_season(profile: PlayerProfile, career: DriverCareer):
    header("FIM DE TEMPORADA — PILOTO")
    report = career.end_of_season()
    pd = career.player_driver

    print(f"\n  Campeo: {report['champion_driver']}")
    print(f"\n  Sua posicao: P{report['player_position']}")
    print(f"  SL pts ganhos esta temporada: +{report['sl_earned']}")
    print(f"  SL pts totais: {report['sl_total']}/40")
    print(f"  Premio: EUR {report['prize_money']:,.0f}")
    print(f"  Dinheiro pessoal: EUR {profile.personal_money:,.0f}")
    print(f"  Saude: {pd.health}%  |  Idade: {pd.age}")

    if report["sl_blocked"]:
        pr(f"\n  [SL BLOQUEADO] {report['sl_block_reason']}", "red")

    if report["promoted"]:
        next_name = report["promotes_to"].replace("_"," ").title()
        pr(f"\n  PROMOVIDO para {next_name}!", "bold green")
    else:
        pr("\n  Permanece na mesma categoria.", "yellow")

    pause()

    if len(profile.history) > 1:
        print("\n  HISTORICO:")
        for h in profile.history:
            print(f"    {h.year}  {h.series:<30} P{h.position}")
        pause()

    # Verifica se foi fired sem oferta pendente
    if report["player_position"] > 8 and not career._pending_offer:
        fired_chance = (report["player_position"] - 8) * 0.15
        import random
        if random.random() < fired_chance:
            pr("\n  Sua equipe nao renovou seu contrato.", "red")
            # Tenta encontrar outra equipe
            import random as rr
            others = [t for t in career.all_teams
                      if t.id != (career.current_team.id if career.current_team else "")]
            if not others or rr.random() < 0.3:
                clt_game_over(career.current_series_id, profile.history)
            else:
                target = rr.choice(others)
                pr(f"  {target.name} oferece uma vaga de emergencia.", "yellow")
                career._pending_offer = _build_offer_dict(
                    "fired", target, career.current_series_id,
                    max(20000, pd.salary // 2), 1, forced=True)

    # Aplica oferta pendente ou promoção normal
    pending = career._pending_offer
    career._pending_offer = None
    new_team_id = pending["from_team_id"] if pending else None
    promote = report["promoted"] if not pending else (
        pending["from_series"] != career.current_series_id and
        SERIES_PROGRESSION.index(pending["from_series"]) >
        SERIES_PROGRESSION.index(career.current_series_id))

    if pending:
        career.current_series_id = pending["from_series"]
        career.career_year  += 1
        career.season_number += 1
        from game.career import load_series, load_drivers_for_series, load_teams_for_series, assign_ai_drivers, build_season
        career.series_rules = load_series(career.current_series_id)
        career.all_drivers  = load_drivers_for_series(career.current_series_id)
        career.all_teams    = load_teams_for_series(career.current_series_id)
        pd_saved = career.player_driver
        career.all_drivers.append(pd_saved)
        career.current_team = next((t for t in career.all_teams if t.id == new_team_id), career.all_teams[0])
        career.current_team.is_player_team = True
        pd_saved.team_id = career.current_team.id
        if pd_saved.id not in career.current_team.drivers:
            career.current_team.drivers.insert(0, pd_saved.id)
        assign_ai_drivers(career.all_teams, career.all_drivers, [pd_saved.id])
        career.season = build_season(career.current_series_id, career.career_year,
                                     career.series_rules, career.all_teams, career.all_drivers)
        career.standings_drivers = {d.id: 0 for d in career.all_drivers}
        career.standings_teams   = {t.id: 0 for t in career.all_teams}
        career.injury_log = []
    else:
        career.start_new_season(promote, new_team_id)

    header("NOVA TEMPORADA")
    cat = SERIES_LABEL.get(career.current_series_id, "")
    print(f"\n  {cat} {career.series_rules['name']}  {career.career_year}")
    print(f"  Piloto: {career.player_driver.name}  OVR:{career.player_driver.overall:.0f}")
    print(f"  Equipe: {career.current_team.name if career.current_team else '?'}")
    print(f"  SL: {career.player_driver.super_licence_points}/40")
    pause()


def driver_sl_screen(career: DriverCareer):
    header("Super Licenca FIA", "40 pts + idade 18+")
    pd = career.player_driver
    summary = sl.sl_summary(pd)
    print(f"\n  {pd.name}  ({pd.age} anos  {pd.nationality})")
    hr()
    ok_str = "ELEGIVEL" if summary["eligible"] else "BLOQUEADO"
    pr(f"  Status: {ok_str}", "green" if summary["eligible"] else "red")
    print(f"  Pontos: {summary['total_points']}/40")
    print(f"  FP1 sessions: {summary['fp1_sessions']}  (+{summary['fp1_points']} pts)")
    if summary["history"]:
        print("\n  Historico:")
        for h in summary["history"]:
            print(f"    {h['year']}  {h['series'].replace('_',' ').title():<24}  +{h['points']} pts")
    if not summary["eligible"]:
        pr(f"\n  Motivo: {summary['reason']}", "red")
    pause()


def driver_academy_screen(career: DriverCareer):
    pd = career.player_driver
    while True:
        header("Academia", f"Piloto: {pd.name}  Academia atual: {pd.academy_id or 'Nenhuma'}")
        all_ac = acad.load_academies()
        ac_list = list(all_ac.values())
        for i, a in enumerate(ac_list, 1):
            disc = int(a.benefits.get("salary_discount", 0) * 100)
            pot  = a.benefits.get("potential_bonus_per_season", 0)
            fp1  = int(a.benefits.get("fp1_access_chance", 0) * 100)
            fee  = a.restrictions.get("buyout_fee", 0)
            print(f"  [{i}] {a.name:<30}  Prest:{a.prestige}  Desc:{disc}%  "
                  f"Pot:+{pot}/ano  FP1:{fp1}%  Buyout:EUR{fee:,}")
        print("\n  [J] Juntar-se  [S] Sair  [0] Voltar")
        opt = ask("Opcao", ["0","j","s"], "0")
        if opt == "0": break

        if opt == "j":
            if pd.academy_id:
                pr(f"  Ja esta em {pd.academy_id}. Saia primeiro.", "yellow"); pause(); continue
            idx = pick(ac_list, lambda a: a.name, "Qual academia?")
            budget_ref = {"budget": profile_from_career(career).personal_money}
            ok, msg = acad.join_academy(pd, ac_list[idx].id, budget_ref)
            pr(f"\n  {'OK' if ok else 'ERRO'}: {msg}", "green" if ok else "red")
            pause()

        elif opt == "s":
            if not pd.academy_id:
                pr("  Nao esta em academia.", "yellow"); pause(); continue
            fee = acad.buyout_fee(pd.academy_id)
            pay = False
            if fee > 0:
                pr(f"  Buyout: EUR {fee:,}. Pagar? [s/n]", "yellow")
                pay = ask("", ["s","n"], "n") == "s"
            budget_ref = {"budget": 999_999_999}
            ok, msg = acad.leave_academy(pd, pay, budget_ref)
            pr(f"\n  {'OK' if ok else 'ERRO'}: {msg}", "green" if ok else "red")
            pause()


def profile_from_career(career):
    return career.profile


def driver_main_menu(profile: PlayerProfile, career: DriverCareer):
    while True:
        pd    = career.player_driver
        track = career.current_round()
        cat   = SERIES_LABEL.get(career.current_series_id, "")
        total = len(career.season.rounds) if career.season else 0
        rnd   = (f"Corrida {track.round_number}/{total}: {track.track_name}"
                 if track else "Temporada encerrada")
        sub   = (f"{cat} {career.series_rules.get('name','')} {career.career_year}  |  "
                 f"{rnd}  |  SL:{pd.super_licence_points}/40  Saude:{pd.health}%")
        header(f"PILOTO — {pd.name}", sub)

        inj_tag = f"  [LESIONADO: {pd.injury_races_remaining}c restantes]" if pd.is_injured else ""
        print(f"  {pd.name}  OVR:{pd.overall:.0f}  Pot:{pd.potential}  "
              f"EUR{profile.personal_money:,.0f}{inj_tag}")
        print(f"  Equipe: {career.current_team.name if career.current_team else '?'}")
        print()
        print("  [1] Corrida")
        print("  [2] Classificacao")
        print("  [3] Super Licenca")
        print("  [4] Academia")
        print("  [R] Aposentar e virar Chefe de Equipe")
        print("  [S] Salvar")
        if career.season_complete():
            print("  [F] Fim de temporada")
        print("  [0] Sair")
        opts = ["0","1","2","3","4","r","s","f"]
        opt  = ask("Opcao", opts)

        if opt == "1":
            if career.season_complete():
                pr("  Use [F].", "yellow"); pause()
            else:
                driver_race_menu(profile, career)
        elif opt == "2":
            header(f"Classificacao {cat}")
            show_driver_standings(career.driver_standings(), career.all_teams, pd.id)
            show_team_standings(career.team_standings())
            pause()
        elif opt == "3":
            driver_sl_screen(career)
        elif opt == "4":
            driver_academy_screen(career)
        elif opt == "r":
            driver_retire_to_manager(profile, career)
            return  # sai do loop de piloto
        elif opt == "s":
            path = save_game(profile, career)
            pr(f"  Salvo: {path}", "green"); pause()
        elif opt == "f":
            if career.season_complete():
                driver_end_of_season(profile, career)
            else:
                pr("  Temporada ainda nao terminou.", "yellow"); pause()
        elif opt == "0":
            break


def driver_retire_to_manager(profile: PlayerProfile, career: DriverCareer):
    header("APOSENTADORIA", "Virar Chefe de Equipe")
    ok, msg = profile.can_retire_to_manager()
    if not ok:
        pr(f"  {msg}", "red"); pause(); return

    print(f"\n  Dinheiro pessoal: EUR {profile.personal_money:,.0f}")
    print("\n  Custos de entrada por categoria:")
    for sid, cost in MANAGER_ENTRY_COST.items():
        print(f"    {sid:<22} EUR {cost:>12,.0f}")
    series_list = list(MANAGER_ENTRY_COST.keys())
    idx = pick(series_list, lambda s: f"{s}  EUR {MANAGER_ENTRY_COST[s]:,.0f}",
               "Qual categoria entrar como gerente?")
    target_series = series_list[idx]

    ok, msg = profile.retire_to_manager(target_series)
    if not ok:
        pr(f"\n  {msg}", "red"); pause(); return

    pr(f"\n  {msg}", "green")
    pause()
    # Inicia carreira de gerente
    manager_career = manager_new_career_from_retirement(profile, target_series)
    manager_main_menu(profile, manager_career)


# ═══════════════════════════════════════════════════════════════════════════════
#  MODO GERENTE
# ═══════════════════════════════════════════════════════════════════════════════

def manager_new_career(profile: PlayerProfile) -> ManagerCareer:
    header("NOVA CARREIRA — CHEFE DE EQUIPE", f"{profile.name}  |  {profile.age} anos")
    teams   = load_teams_for_series("formula_4")
    drivers = load_drivers_for_series("formula_4")

    team_idx = pick(teams,
        lambda t: f"{t.name:<22}  EUR{t.budget:>10,.0f}  Rep:{t.reputation}  Chassi:{t.chassis}",
        "Escolha sua equipe (Formula 4)")
    pt = teams[team_idx]
    print(f"\n  {pt.name}  |  Orcamento: EUR {pt.budget:,.0f}")

    avail = sorted(drivers, key=lambda d: -d.overall)
    d1_idx = pick(avail,
        lambda d: f"{d.name:<22} {d.nationality}  OVR:{d.overall:.0f}  Pot:{d.potential}  EUR{d.salary:,.0f}",
        "Piloto #1")
    d1 = avail[d1_idx]
    avail2 = [d for d in avail if d.id != d1.id]
    d2_idx = pick(avail2,
        lambda d: f"{d.name:<22} {d.nationality}  OVR:{d.overall:.0f}  Pot:{d.potential}  EUR{d.salary:,.0f}",
        "Piloto #2")
    d2 = avail2[d2_idx]

    total_sal = d1.salary + d2.salary
    print(f"\n  Salario combinado: EUR {total_sal:,.0f}")
    if total_sal > pt.budget * 0.35:
        pr("  Atencao: salarios altos!", "yellow")
    if ask("Confirmar? [s/n]", ["s","n"], "s") != "s":
        return manager_new_career(profile)

    career = ManagerCareer(profile)
    msg = career.new_career("formula_4", pt.id, d1.id, d2.id)
    career.player_team.budget -= total_sal
    pr(f"\n  {msg}", "green")
    pause()
    return career


def manager_new_career_from_retirement(profile: PlayerProfile, series_id: str) -> ManagerCareer:
    header("NOVA CARREIRA — CHEFE DE EQUIPE (pos-aposentadoria)")
    teams   = load_teams_for_series(series_id)
    drivers = load_drivers_for_series(series_id)

    team_idx = pick(teams,
        lambda t: f"{t.name:<22}  EUR{t.budget:>10,.0f}  Rep:{t.reputation}",
        f"Escolha sua equipe ({series_id})")
    pt = teams[team_idx]

    avail = sorted(drivers, key=lambda d: -d.overall)
    d1_idx = pick(avail,
        lambda d: f"{d.name:<22} OVR:{d.overall:.0f}  Sal:EUR{d.salary:,.0f}", "Piloto #1")
    d1 = avail[d1_idx]
    avail2 = [d for d in avail if d.id != d1.id]
    d2_idx = pick(avail2,
        lambda d: f"{d.name:<22} OVR:{d.overall:.0f}  Sal:EUR{d.salary:,.0f}", "Piloto #2")
    d2 = avail2[d2_idx]

    career = ManagerCareer(profile)
    msg = career.new_career(series_id, pt.id, d1.id, d2.id)
    career.player_team.budget -= (d1.salary + d2.salary)
    pr(f"\n  {msg}", "green")
    pause()
    return career


ProfileType = PlayerProfile  # alias para type hints inline


def manager_team_info(profile: ProfileType, career: ManagerCareer):
    t = career.player_team
    cat = SERIES_LABEL.get(career.current_series_id, "")
    header(f"Equipe: {t.name}  {cat}")
    print(f"\n  Orcamento:     EUR {t.budget:>12,.0f}")
    print(f"  Custo/corrida: EUR {t.base_cost_per_race:>12,.0f}")
    print(f"  Reputacao:     {t.reputation}/100")
    print(f"  Performance:   {t.car_performance:.1f}/100")
    fac = t.facilities
    print(f"\n  INSTALACOES:  Fab:Lv{t.fac_factory}  Sim:Lv{t.fac_simulator}  "
          f"R&D:Lv{t.fac_r_and_d}  Pit:Lv{t.fac_pit_crew}  Mkt:Lv{t.fac_marketing}")
    print(f"    Dev x{fac.dev_speed_multiplier():.2f}  Pit -{fac.pit_time_bonus():.1f}s  "
          f"Sponsor x{fac.sponsor_multiplier():.2f}")
    print(f"\n  PILOTOS:")
    for d in career.player_drivers():
        sl_tag = f"SL:{d.super_licence_points}/40"
        inj_tag = f" [LESIONADO {d.injury_races_remaining}c]" if d.is_injured else ""
        ac_tag  = f" [{d.academy_id.split('_')[0].upper()}]" if d.academy_id else ""
        print(f"    {d.name:<24} OVR:{d.overall:.0f}  Pot:{d.potential}  "
              f"{sl_tag}  Saude:{d.health}%  EUR{d.salary:,.0f}  {d.contract_years}a{ac_tag}{inj_tag}")
    print(f"\n  PATROCINADORES:")
    for s in t.sponsors:
        name = s["name"] if isinstance(s, dict) else s.name
        val  = s["value"] if isinstance(s, dict) else s.value
        req  = s["requirement"] if isinstance(s, dict) else s.requirement
        print(f"    {name:<30} EUR {val:>9,.0f}  [{req}]")


def manager_facilities_menu(career: ManagerCareer):
    t = career.player_team
    fac_map = [
        ("Fabrica",    "fac_factory",   "factory"),
        ("Simulador",  "fac_simulator", "simulator"),
        ("R&D",        "fac_r_and_d",   "r_and_d"),
        ("Pit Crew",   "fac_pit_crew",  "pit_crew"),
        ("Marketing",  "fac_marketing", "marketing"),
    ]
    car_map = [
        ("Chassi",        "chassis",      150_000, 3),
        ("Aerodinamica",  "aerodynamics", 180_000, 3),
        ("Confiabilidade","reliability",  120_000, 4),
        ("Pit Crew(car)", "pit_crew",      80_000, 3),
        ("Engenheiros",   "engineers",    100_000, 2),
        ("Fabrica(car)",  "factory",      200_000, 3),
    ]
    while True:
        header("Desenvolvimento", f"Orcamento: EUR {t.budget:,.0f}")
        print("\n  INSTALACOES:")
        for i, (lbl, attr, key) in enumerate(fac_map, 1):
            lvl  = getattr(t, attr, 1)
            cost = t.facilities.upgrade_cost(key)
            ok   = "MAX" if lvl >= 5 else ("OK" if t.budget >= cost else "--")
            print(f"  [F{i}] {lbl:<14} Lv{lvl}/5  EUR{cost:>10,.0f}  {ok}")
        print("\n  CARRO:")
        for i, (lbl, attr, cost, gain) in enumerate(car_map, 1):
            cur = getattr(t, attr)
            ok  = "OK" if t.budget >= cost else "--"
            print(f"  [C{i}] {lbl:<16} {cur:>3}/100  EUR{cost:>9,.0f}  +{gain}  {ok}")
        print("  [0] Voltar")
        opt = input("  Opcao: ").strip().lower()
        if opt == "0": break
        elif opt.startswith("f") and opt[1:].isdigit():
            idx = int(opt[1:]) - 1
            if 0 <= idx < len(fac_map):
                lbl, attr, key = fac_map[idx]
                lvl = getattr(t, attr, 1)
                cost = t.facilities.upgrade_cost(key)
                if lvl >= 5: pr(f"  {lbl} ja nivel maximo.", "yellow")
                elif t.budget < cost: pr(f"  Sem orcamento (EUR {cost:,.0f}).", "red")
                else:
                    setattr(t, attr, lvl + 1); t.budget -= cost
                    pr(f"  {lbl}: Lv{lvl} -> Lv{lvl+1}  (-EUR {cost:,.0f})", "green")
                pause()
        elif opt.startswith("c") and opt[1:].isdigit():
            idx = int(opt[1:]) - 1
            if 0 <= idx < len(car_map):
                lbl, attr, cost, gain = car_map[idx]
                cur = getattr(t, attr)
                if cur >= 99: pr(f"  {lbl} ja no maximo.", "yellow")
                elif t.budget < cost: pr(f"  Sem orcamento.", "red")
                else:
                    setattr(t, attr, min(99, cur + gain)); t.budget -= cost
                    pr(f"  {lbl}: {cur} -> {getattr(t,attr)}  (-EUR {cost:,.0f})", "green")
                pause()


def manager_transfer_menu(career: ManagerCareer):
    market = TransferMarket(career)
    market.tick_contracts()
    while True:
        header("Janela de Transferencias")
        pt = career.player_team
        print(f"\n  Orcamento: EUR {pt.budget:,.0f}")
        print("\n  SEUS PILOTOS:")
        for d in career.player_drivers():
            mv = driver_market_value(d, career.standings_drivers.get(d.id, 0))
            contr = f"{d.contract_years}a" if d.contract_years > 0 else "EXPIROU"
            inj_tag = " [LESIONADO]" if d.is_injured else ""
            print(f"    {d.name:<24} OVR:{d.overall:.0f}  Valor:EUR{mv:,.0f}  {contr}{inj_tag}")
        print()
        print("  [1] Renovar contrato  [2] Liberar  [3] Contratar livre  [0] Confirmar")
        opt = ask("Opcao", ["0","1","2","3"], "0")
        if opt == "0":
            if len(pt.drivers) == 0:
                clt_game_over(career.current_series_id, career.profile.history)
            break
        elif opt == "1":
            drvs = career.player_drivers()
            if not drvs: pr("  Sem pilotos.", "yellow"); pause(); continue
            idx = pick(drvs, lambda d: f"{d.name} OVR:{d.overall:.0f}", "Renovar")
            d = drvs[idx]
            mv = driver_market_value(d, career.standings_drivers.get(d.id, 0))
            print(f"\n  {d.name} — min EUR {int(mv*0.80):,.0f}/ano")
            try:
                sal  = int(input("  Salario: EUR ").replace(",","").strip())
                anos = max(1, min(3, int(input("  Anos [1-3]: ").strip())))
            except ValueError: pr("  Invalido.", "red"); pause(); continue
            if sal >= mv * 0.80:
                ok, msg = market.renew_contract(d.id, sal, anos)
                pr(f"\n  {'OK' if ok else 'ERRO'}: {msg}", "green" if ok else "red")
            else:
                pr(f"\n  {d.name} recusou.", "red")
            pause()
        elif opt == "2":
            drvs = career.player_drivers()
            if not drvs: pr("  Sem pilotos.", "yellow"); pause(); continue
            idx = pick(drvs, lambda d: f"{d.name}", "Liberar")
            d = drvs[idx]
            if ask(f"Liberar {d.name}? [s/n]", ["s","n"], "n") == "s":
                market.release_driver(d.id)
                pt.drivers.remove(d.id)
                pr(f"  {d.name} liberado.", "yellow")
            pause()
        elif opt == "3":
            free = [d for d in career.all_drivers
                    if (not d.team_id or d.contract_years <= 0) and d.id not in pt.drivers]
            if not free: pr("  Sem agentes livres.", "yellow"); pause(); continue
            if len(pt.drivers) >= 2: pr("  Libere um piloto primeiro.", "yellow"); pause(); continue
            free_s = sorted(free, key=lambda d: -d.overall)
            idx = pick(free_s,
                lambda d: f"{d.name:<22} OVR:{d.overall:.0f}  Sal:EUR{d.salary:,.0f}", "Agentes livres")
            drv = free_s[idx]
            mv  = driver_market_value(drv, career.standings_drivers.get(drv.id, 0))
            try:
                sal  = int(input(f"  Salario (min EUR {int(mv*0.80):,.0f}): EUR ").replace(",","").strip())
                anos = max(1, min(3, int(input("  Anos [1-3]: ").strip())))
            except ValueError: pr("  Invalido.", "red"); pause(); continue
            if sal < mv * 0.80: pr(f"  {drv.name} recusou.", "red")
            else:
                ok, msg = market.sign_driver(drv.id, sal, anos)
                pr(f"\n  {'OK' if ok else 'ERRO'}: {msg}", "green" if ok else "red")
            pause()
    market.run_ai_transfers()


def manager_end_of_season(profile: PlayerProfile, career: ManagerCareer):
    header("FIM DE TEMPORADA — GERENTE")
    report = career.end_of_season()
    print(f"\n  Campeo: {report['champion_driver']}")
    print(f"\n  Posicao da equipe: P{report['team_position']}")
    print(f"  Receita patrocinadores: EUR {report['sponsor_income']:,.0f}")
    print(f"  Premio: EUR {report['prize_money']:,.0f}")
    print(f"  Dividendo pessoal: EUR {report['dividend']:,.0f}")
    print(f"  Orcamento final: EUR {report['final_budget']:,.0f}")
    if report["sl_awards"]:
        print("\n  SL dos seus pilotos:")
        for name, info in report["sl_awards"].items():
            print(f"    {name:<24} P{info['pos']}  +{info['earned']} pts  Total:{info['total']}/40")
    if report["promoted"]:
        pr(f"\n  PROMOVIDO para {report['promotes_to'].replace('_',' ').title()}!", "bold green")
    else:
        pr("\n  Permanece na mesma categoria.", "yellow")
    pause()

    if len(profile.history) > 1:
        print("\n  HISTORICO:")
        for h in profile.history:
            print(f"    {h.year}  {h.series:<30} P{h.position}")
        pause()

    manager_transfer_menu(career)
    career.start_new_season(promote=report["promoted"])

    header("NOVA TEMPORADA")
    cat = SERIES_LABEL.get(career.current_series_id, "")
    print(f"\n  {cat} {career.series_rules['name']}  {career.career_year}")
    print(f"  Equipe: {career.player_team.name}  Orcamento: EUR {career.player_team.budget:,.0f}")
    for d in career.player_drivers():
        print(f"    {d.name}  OVR:{d.overall:.0f}  SL:{d.super_licence_points}/40  {d.contract_years}a")
    pause()


def manager_become_driver(profile: PlayerProfile, career: ManagerCareer):
    header("VIRAR PILOTO — AVISO")
    pr("  Isso e quase impossivel para um gerente experiente.", "red")
    print(f"\n  Sua idade: {profile.age}")
    print("\n  Limites maximos por categoria:")
    for sid, limit in DRIVER_AGE_GATE.items():
        lbl = "BLOQUEADO" if limit == -1 else f"max {limit} anos"
        print(f"    {sid:<22} {lbl}")

    # Filtra categorias ainda possiveis
    possible = [s for s, lim in DRIVER_AGE_GATE.items() if lim != -1 and profile.age <= lim]
    if not possible:
        pr(f"\n  Com {profile.age} anos, e impossivel virar piloto em qualquer categoria.", "red")
        pause(); return

    pr(f"\n  UNICA possibilidade: {', '.join(possible)}", "yellow")
    pr("  Seus atributos como piloto serao medíocres (voce nao treinou).", "red")
    if ask("Tem certeza? [s/n]", ["s","n"], "n") != "s":
        return

    idx = pick(possible, lambda s: s, "Qual categoria?")
    target_series = possible[idx]

    ok, msg, driver_kwargs = profile.become_driver(target_series)
    if not ok:
        pr(f"\n  {msg}", "red"); pause(); return

    pr(f"\n  {msg}", "yellow"); pause()
    # Cria carreira de piloto com stats ruins
    driver_career = DriverCareer(profile)
    teams = load_teams_for_series(target_series)
    # Só as piores equipes aceitariam um gerente de 25+ anos
    worst = teams[-3:] if profile.age > 20 else teams
    team_idx = pick(worst,
        lambda t: f"{t.name:<22} Chassi:{t.chassis}  Rep:{t.reputation}", "Equipe (poucas opcoes)")
    pt = worst[team_idx]
    start_msg = driver_career.new_career(target_series, pt.id, driver_kwargs)
    pr(f"\n  {start_msg}", "green"); pause()
    driver_main_menu(profile, driver_career)


def manager_race_menu(profile: PlayerProfile, career: ManagerCareer):
    track = career.current_round()
    if not track:
        pr("  Temporada encerrada.", "yellow"); pause(); return
    total = len(career.season.rounds)
    cat   = SERIES_LABEL.get(career.current_series_id, "")
    header(f"{cat} Corrida {track.round_number}/{total} — {track.track_name}")

    for d in career.player_drivers():
        if d.is_injured:
            pr(f"  {d.name} LESIONADO — {d.injury_races_remaining}c restantes", "red")

    print(f"\n  [1] Simular  [0] Voltar")
    opt = ask("Opcao", ["0","1"], "1")
    if opt == "0": return

    print("\n  Simulando", end="", flush=True)
    for _ in range(6): time.sleep(0.25); print(".", end="", flush=True)
    print()
    results, events = career.simulate_next_race()
    show_race_results(results, events, track.track_name)

    # Oferta de categoria para a equipe
    from game.offers import generate_offer as gen_off
    # Adapta career para compatibilidade com generate_offer
    _compat = _ManagerCareerCompat(career)
    offer = gen_off(_compat)
    if offer:
        print()
        accepted = show_offer(offer)
        if accepted:
            career._pending_offer = offer
            pr(f"\n  Proposta aceita: {offer['from_team']}", "green")
        else:
            pr("\n  Recusado.", "dim")
    pause()


class _ManagerCareerCompat:
    """Adapter para compatibilidade com generate_offer (que espera a API antiga)."""
    def __init__(self, c: ManagerCareer):
        self._c = c
    @property
    def current_series_id(self): return self._c.current_series_id
    @property
    def season(self): return self._c.season
    @property
    def all_teams(self): return self._c.all_teams
    @property
    def player_team(self): return self._c.player_team
    def player_team_position(self): return self._c.player_team_position()
    def player_drivers(self): return self._c.player_drivers()


def manager_main_menu(profile: PlayerProfile, career: ManagerCareer):
    while True:
        track = career.current_round()
        cat   = SERIES_LABEL.get(career.current_series_id, "")
        total = len(career.season.rounds) if career.season else 0
        rnd   = (f"Corrida {track.round_number}/{total}: {track.track_name}"
                 if track else "Temporada encerrada")
        sub   = (f"{cat} {career.series_rules.get('name','')} {career.career_year}  |  "
                 f"{rnd}  |  EUR {career.player_team.budget:,.0f}")
        header(f"GERENTE — {career.player_team.name}", sub)

        print(f"  Dinheiro pessoal: EUR {profile.personal_money:,.0f}  |  Rep:{profile.reputation}")
        for d in career.player_drivers():
            inj_t = " [INJ]" if d.is_injured else ""
            print(f"  {d.name:<24} OVR:{d.overall:.0f}  SL:{d.super_licence_points}/40{inj_t}")
        print()
        print("  [1] Simular corrida")
        print("  [2] Classificacao")
        print("  [3] Equipe e pilotos")
        print("  [4] Desenvolvimento / Instalacoes")
        print("  [P] Virar Piloto (quase impossivel)")
        print("  [S] Salvar")
        if career.season_complete():
            print("  [F] Fim de temporada")
        print("  [0] Sair")

        opts = ["0","1","2","3","4","p","s","f"]
        opt  = ask("Opcao", opts)

        if opt == "1":
            if career.season_complete(): pr("  Use [F].", "yellow"); pause()
            else: manager_race_menu(profile, career)
        elif opt == "2":
            header(f"Classificacao {cat}")
            show_driver_standings(career.driver_standings(), career.all_teams,
                                  player_team=career.player_team)
            show_team_standings(career.team_standings(), career.player_team)
            pause()
        elif opt == "3":
            manager_team_info(profile, career); pause()
        elif opt == "4":
            manager_facilities_menu(career)
        elif opt == "p":
            manager_become_driver(profile, career)
            return
        elif opt == "s":
            path = save_game(profile, career)
            pr(f"  Salvo: {path}", "green"); pause()
        elif opt == "f":
            if career.season_complete(): manager_end_of_season(profile, career)
            else: pr("  Temporada ainda nao terminou.", "yellow"); pause()
        elif opt == "0":
            break


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════

def create_profile() -> PlayerProfile:
    header("NOVO PERFIL")
    name = input("  Seu nome: ").strip() or "Piloto"
    age_str = input("  Idade (16-45): ").strip()
    try:
        age = max(16, min(45, int(age_str)))
    except ValueError:
        age = 22
    nat = input("  Nacionalidade (ex: BRA): ").strip().upper() or "BRA"
    return PlayerProfile(name=name, age=age, nationality=nat)


def main():
    clear()
    if HAS_RICH:
        console.print(Panel(
            "[bold yellow]MOTORSPORT DYNASTY MANAGER[/bold yellow]\n"
            "[dim]v0.4 — Carreira de Piloto | Carreira de Gerente | F4->F1[/dim]",
            border_style="yellow", expand=False))
    else:
        hr("=")
        print("   MOTORSPORT DYNASTY MANAGER")
        print("   v0.4 | Piloto | Gerente | F4->F1")
        hr("=")

    print()
    print("  [1] Nova carreira — Piloto")
    print("  [2] Nova carreira — Chefe de Equipe")
    print("  [3] Carregar jogo")
    print("  [0] Sair")
    opt = ask("Opcao", ["0","1","2","3"])

    if opt == "0":
        return

    if opt == "3":
        saves = list_saves()
        if not saves:
            pr("  Nenhum save encontrado.", "yellow"); pause(); main(); return
        for s in saves:
            mode_tag = "Piloto" if s["mode"] == "driver" else "Gerente"
            print(f"  [{s['slot']}]  {s['saved_at'][:19]}  {mode_tag}  {s['name']}  "
                  f"{s['series']}  {s['year']}")
        slot = ask("Slot", [s["slot"] for s in saves])
        profile, career = load_game(slot)
        if not profile:
            pr("  Erro ao carregar!", "red"); pause(); return
        pr(f"  Carregado: {slot}", "green"); pause()
        if isinstance(career, DriverCareer):
            driver_main_menu(profile, career)
        else:
            manager_main_menu(profile, career)
        return

    profile = create_profile()

    if opt == "1":
        profile.mode = "driver"
        career = driver_new_career(profile)
        driver_main_menu(profile, career)
    else:
        profile.mode = "manager"
        career = manager_new_career(profile)
        manager_main_menu(profile, career)

    clear()
    print("  Ate a proxima corrida!")


if __name__ == "__main__":
    main()
