"""
Cenas do Motorsport Dynasty Manager (pygame).

Fluxo:
  MenuScene → CreateScene → CareerScene
                                 ├─ RaceResultScene (overlay por corrida)
                                 └─ SeasonEndScene → CareerScene (nova temporada)
  MenuScene → LoadScene → CareerScene
"""
import random
import pygame
from . import theme as T
from .app import Scene
from .widgets import (draw_text, panel, accent_strip, stat_bar, chip,
                      Button, TextInput, SelectList, draw_icon)

from game.player_profile import (PlayerProfile, MANAGER_ENTRY_COST,
                                 DRIVER_AGE_GATE)
from game.driver_career import DriverCareer
from game.manager_career import ManagerCareer
from game.career import (SERIES_PROGRESSION, load_series,
                         load_teams_for_series, load_drivers_for_series,
                         series_above, series_below, assign_ai_drivers,
                         build_season)
from game.offers import generate_offer, OFFER_TYPE_LABEL
from game.transfer_market import TransferMarket, driver_market_value
from game import super_licence as sl
from game import academies as acad
from game import save_load

CLT_MESSAGES = {
    "formula_4":        "Você virou fiscal de pátio no Autódromo de Interlagos.",
    "formula_regional": "Agora é comentarista voluntário de F4 no YouTube.",
    "formula_3":        "Comentarista de YouTube sobre F1 — de graça.",
    "formula_2":        "Analista de telemetria para uma equipe de kart em Cascavel.",
    "formula_1":        "Embaixador de marca de relógios suíços. Boa aposentadoria.",
}

SERIES_LABEL = {
    "formula_4": "Fórmula 4", "formula_regional": "Fórmula Regional",
    "formula_3": "Fórmula 3", "formula_2": "Fórmula 2", "formula_1": "Fórmula 1",
}


def gradient_bg(surf):
    """Fundo com leve gradiente vertical."""
    top = T.BG
    bot = (10, 9, 16)
    h = surf.get_height()
    for y in range(0, h, 4):
        t = y / h
        pygame.draw.rect(surf, T.lerp(top, bot, t), (0, y, surf.get_width(), 4))


def header(surf, app, subtitle=""):
    pygame.draw.rect(surf, T.BG_PANEL, (0, 0, T.WIDTH, 64))
    pygame.draw.rect(surf, T.ACCENT, (0, 64, T.WIDTH, 3))
    draw_text(surf, "MOTORSPORT", app.fonts.h2, T.ACCENT, (28, 12))
    draw_text(surf, "DYNASTY", app.fonts.h2, T.TEXT, (28, 34))
    if subtitle:
        draw_text(surf, subtitle, app.fonts.body, T.TEXT_DIM, (230, 22))
    p = app.profile
    if p:
        money = f"€ {p.personal_money:,}".replace(",", ".")
        info = f"{p.name}  ·  {p.age} anos  ·  Rep {p.reputation}"
        draw_text(surf, info, app.fonts.small, T.TEXT, (T.WIDTH - 28, 12), right=True)
        draw_text(surf, money, app.fonts.body, T.GOLD, (T.WIDTH - 28, 34), right=True)


# ══════════════════════════════════════════════════════════════════════════════
# MENU
# ══════════════════════════════════════════════════════════════════════════════
class MenuScene(Scene):
    def on_enter(self):
        f = self.app.fonts
        cx = T.WIDTH // 2
        w, h, gap = 360, 58, 16
        y0 = 330
        self.buttons = [
            Button((cx - w // 2, y0,            w, h), "CARREIRA DE PILOTO",
                   lambda: self._new("driver"), f.h2, icon="helmet"),
            Button((cx - w // 2, y0 + (h+gap),  w, h), "CARREIRA DE GERENTE",
                   lambda: self._new("manager"), f.h2, kind="ghost", icon="team"),
            Button((cx - w // 2, y0 + 2*(h+gap),w, h), "CARREGAR JOGO",
                   lambda: self.app.push(LoadScene(self.app)), f.h2, kind="ghost", icon="save"),
            Button((cx - w // 2, y0 + 3*(h+gap),w, h), "SAIR",
                   self._quit, f.body, kind="ghost"),
        ]
        self._t = 0

    def _new(self, mode):
        self.app.mode = mode
        self.app.push(CreateScene(self.app, mode))

    def _quit(self):
        self.app.running = False

    def handle(self, event):
        for b in self.buttons:
            b.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for idx, r in getattr(self, "res_rects", []):
                if r.collidepoint(event.pos):
                    self.app.set_resolution(idx)
                    self.app.notify(f"Resolução: {T.RESOLUTIONS[idx][0]}")

    def update(self, dt):
        self._t += dt

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        cx = T.WIDTH // 2
        # Título com sombra
        for off, col in [((3, 3), (0, 0, 0)), ((0, 0), T.ACCENT)]:
            draw_text(surf, "MOTORSPORT", f.title,
                      col, (cx + off[0], 150 + off[1]), center=True)
        draw_text(surf, "D Y N A S T Y   M A N A G E R", f.h2, T.TEXT, (cx, 215), center=True)
        # Linha decorativa
        pygame.draw.rect(surf, T.LINE, (cx - 180, 255, 360, 2))
        draw_text(surf, "Do kart à Fórmula 1 — construa sua dinastia",
                  f.small, T.TEXT_DIM, (cx, 278), center=True)
        for b in self.buttons:
            b.draw(surf)
        # seletor de resolução
        draw_text(surf, "RESOLUÇÃO  (F11 = tela cheia)", f.tiny, T.TEXT_FAINT,
                  (cx, T.HEIGHT - 70), center=True)
        labels = [r[0] for r in T.RESOLUTIONS]
        widths = [f.tiny.size(l)[0] + 22 for l in labels]
        total = sum(widths) + 10 * (len(labels) - 1)
        x = cx - total // 2
        self.res_rects = []
        for i, (lab, w) in enumerate(zip(labels, widths)):
            r = pygame.Rect(x, T.HEIGHT - 50, w, 28)
            cur = i == self.app.res_index
            pygame.draw.rect(surf, T.ACCENT if cur else T.BG_PANEL, r, border_radius=14)
            pygame.draw.rect(surf, T.ACCENT if cur else T.LINE, r, width=1, border_radius=14)
            draw_text(surf, lab, f.tiny, T.BG if cur else T.TEXT_DIM, r.center, center=True)
            self.res_rects.append((i, r))
            x += w + 10
        draw_text(surf, "v0.4  ·  protótipo", f.tiny, T.TEXT_FAINT,
                  (T.WIDTH - 16, T.HEIGHT - 24), right=True)


# ══════════════════════════════════════════════════════════════════════════════
# CRIAÇÃO DE CARREIRA
# ══════════════════════════════════════════════════════════════════════════════
class CreateScene(Scene):
    def __init__(self, app, mode):
        super().__init__(app)
        self.mode = mode
        self.step = 0
        self.series_choices = (["formula_4", "formula_regional"]
                               if mode == "driver" else list(SERIES_PROGRESSION))
        self.series_id = self.series_choices[0]

    def on_enter(self):
        f = self.app.fonts
        self.name_in = TextInput((460, 200, 360, 46), f.body, "Seu nome")
        self.age_in  = TextInput((460, 290, 120, 46), f.body,
                                 "17" if self.mode == "driver" else "32", max_len=2, numeric=True)
        self.nat_in  = TextInput((460, 380, 280, 46), f.body, "BRA")
        self.next_btn = Button((T.WIDTH - 240, T.HEIGHT - 80, 200, 52),
                               "CONTINUAR", self._continue, f.h2)
        self.back_btn = Button((40, T.HEIGHT - 80, 160, 52),
                               "VOLTAR", self._back, f.body, kind="ghost")
        # chips de série (retângulos calculados no draw)
        self.series_rects = []
        self.team_list = None

    def _back(self):
        if self.step == 1:
            self.step = 0
        else:
            self.app.pop()

    def _continue(self):
        if self.step == 0:
            if not self.name_in.value():
                self.app.notify("Digite um nome")
                return
            self._build_team_list()
            self.step = 1
        else:
            self._start_career()

    def _build_team_list(self):
        teams = load_teams_for_series(self.series_id)
        self.team_list = SelectList((430, 175, 810, 480), teams,
                                    self.app.fonts.body, row_h=72,
                                    render_row=self._team_row)

    def _team_row(self, surf, team, row, sel, fonts):
        draw_text(surf, team.name, fonts.h2, T.TEXT, (row.x + 16, row.y + 10))
        draw_text(surf, team.short, fonts.tiny, T.TEXT_DIM, (row.x + 16, row.y + 44))
        perf = team.car_performance
        draw_text(surf, f"Carro {perf:.0f}", fonts.small, T.ACCENT_2,
                  (row.right - 18, row.y + 12), right=True)
        bud = f"€ {team.budget:,}".replace(",", ".")
        draw_text(surf, bud, fonts.tiny, T.GOLD, (row.right - 18, row.y + 42), right=True)

    def _start_career(self):
        try:
            age = int(self.age_in.value() or ("17" if self.mode == "driver" else "32"))
        except ValueError:
            age = 17
        profile = PlayerProfile(name=self.name_in.value(), age=age,
                                nationality=(self.nat_in.value() or "BRA").upper()[:3],
                                mode=self.mode)
        self.app.profile = profile
        team = self.team_list.current()
        if self.mode == "driver":
            career = DriverCareer(profile)
            career.new_career(self.series_id, team.id)
        else:
            # Gerente começa com orçamento via equipe; escolhe 2 pilotos automaticamente
            career = ManagerCareer(profile)
            from game.career import load_drivers_for_series
            pool = sorted(load_drivers_for_series(self.series_id), key=lambda d: -d.overall)
            d1, d2 = pool[0], pool[1]
            career.new_career(self.series_id, team.id, d1.id, d2.id)
            career.player_team.budget -= (d1.salary + d2.salary)
        self.app.career = career
        self.app.reset_to(CareerScene(self.app))

    def handle(self, event):
        self.next_btn.handle(event)
        self.back_btn.handle(event)
        if self.step == 0:
            self.name_in.handle(event)
            self.age_in.handle(event)
            self.nat_in.handle(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for sid, r in self.series_rects:
                    if r.collidepoint(event.pos):
                        self.series_id = sid
        else:
            if self.team_list:
                self.team_list.handle(event)

    def update(self, dt):
        pass

    def draw(self, surf):
        gradient_bg(surf)
        role = "PILOTO" if self.mode == "driver" else "GERENTE"
        header(surf, self.app, f"Nova carreira · {role}")
        f = self.app.fonts
        if self.step == 0:
            draw_text(surf, "Quem é você?", f.h1, T.TEXT, (440, 130))
            draw_text(surf, "NOME", f.small, T.TEXT_DIM, (460, 175))
            self.name_in.draw(surf)
            draw_text(surf, "IDADE", f.small, T.TEXT_DIM, (460, 265))
            self.age_in.draw(surf)
            draw_text(surf, "NACIONALIDADE (3 letras)", f.small, T.TEXT_DIM, (460, 355))
            self.nat_in.draw(surf)
            # escolha de categoria inicial
            draw_text(surf, "ONDE COMEÇAR", f.small, T.TEXT_DIM, (460, 460))
            self.series_rects = []
            x = 460
            for sid in self.series_choices:
                col = T.SERIES_COLOR.get(sid, T.ACCENT)
                seld = sid == self.series_id
                label = SERIES_LABEL[sid]
                w = f.body.size(label)[0] + 28
                r = pygame.Rect(x, 495, w, 44)
                pygame.draw.rect(surf, T.BG_PANEL_2 if seld else T.BG_PANEL, r, border_radius=8)
                pygame.draw.rect(surf, col if seld else T.LINE, r, width=2, border_radius=8)
                draw_text(surf, label, f.body, T.TEXT if seld else T.TEXT_DIM,
                          r.center, center=True)
                self.series_rects.append((sid, r))
                x += w + 14
            if self.mode == "driver":
                draw_text(surf, "Começar na Regional é mais arriscado — carros mais rápidos, rivais mais fortes.",
                          f.tiny, T.TEXT_FAINT, (460, 552))
        else:
            draw_text(surf, f"Escolha a equipe · {SERIES_LABEL[self.series_id]}",
                      f.h1, T.TEXT, (430, 120))
            panel(surf, (420, 165, 830, 500), T.BG_PANEL)
            self.team_list.draw(surf, f)
        self.next_btn.draw(surf)
        self.back_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# PAINEL DA CARREIRA (piloto ou gerente)
# ══════════════════════════════════════════════════════════════════════════════
class CareerScene(Scene):
    def on_enter(self):
        f = self.app.fonts
        self.mode = self.app.profile.mode
        self.reveal = 0.0
        sf = f.small
        # ── linha secundária (navegação) ──────────────────────────────────────
        sy = T.HEIGHT - 122
        self.nav = []
        x = 28
        if self.mode == "driver":
            items = [("Classificação", "chart", lambda: self.app.push(StandingsScene(self.app))),
                     ("Super Licença", "star",  lambda: self.app.push(SuperLicenceScene(self.app))),
                     ("Academia",      "cap",   lambda: self.app.push(AcademyScene(self.app))),
                     ("Aposentar",     "door",  lambda: self.app.push(RetireScene(self.app)))]
        else:
            items = [("Desenvolvimento", "dev",      lambda: self.app.push(DevelopmentScene(self.app))),
                     ("Transferências",  "transfer", lambda: self.app.push(TransferScene(self.app))),
                     ("Equipe",          "team",     lambda: self.app.push(TeamInfoScene(self.app))),
                     ("Classificação",   "chart",    lambda: self.app.push(StandingsScene(self.app))),
                     ("Virar Piloto",    "helmet",   lambda: self.app.push(BecomeDriverScene(self.app)))]
        for label, icon, cb in items:
            w = sf.size(label)[0] + 64
            self.nav.append(Button((x, sy, w, 40), label, cb, sf, kind="ghost", icon=icon))
            x += w + 10
        # ── linha primária (ações) ────────────────────────────────────────────
        by = T.HEIGHT - 70
        self.run_btn  = Button((28, by, 250, 52), "CORRER PRÓXIMA", self._race, f.h2, icon="play")
        self.end_btn  = Button((28, by, 320, 52), "ENCERRAR TEMPORADA", self._end_season, f.h2,
                               color=T.GOLD)
        self.save_btn = Button((T.WIDTH - 360, by, 160, 52), "SALVAR", self._save,
                               f.body, kind="ghost", icon="save")
        self.menu_btn = Button((T.WIDTH - 188, by, 160, 52), "MENU", self._menu,
                               f.body, kind="ghost", icon="menu")

    def _menu(self):
        self.app.reset_to(MenuScene(self.app))

    def _save(self):
        try:
            save_load.save_game(self.app.profile, self.app.career, "save1")
            self.app.notify("Jogo salvo em save1")
        except Exception as e:
            self.app.notify(f"Erro ao salvar: {e}")

    def _race(self):
        car = self.app.career
        if car.season_complete():
            return
        self.app.push(SimulatingScene(self.app))

    def _end_season(self):
        summary = self.app.career.end_of_season()
        self.app.push(SeasonEndScene(self.app, summary))

    def on_enter_refresh(self):
        # rebuild nav (mode pode mudar após transição)
        self.on_enter()

    def handle(self, event):
        car = self.app.career
        if car.season_complete():
            self.end_btn.handle(event)
        else:
            self.run_btn.handle(event)
        self.save_btn.handle(event)
        self.menu_btn.handle(event)
        for b in self.nav:
            b.handle(event)

    def update(self, dt):
        self.reveal = min(1.0, self.reveal + dt * 2.2)

    def draw(self, surf):
        gradient_bg(surf)
        car = self.app.career
        header(surf, self.app,
                f"{SERIES_LABEL.get(car.current_series_id, '')} · Temporada {car.season_number} · {car.career_year}")
        if self.mode == "driver":
            self._draw_driver(surf)
        else:
            self._draw_manager(surf)
        # botões
        for b in self.nav:
            b.draw(surf)
        if car.season_complete():
            self.end_btn.draw(surf)
        else:
            self.run_btn.draw(surf)
        self.save_btn.draw(surf)
        self.menu_btn.draw(surf)

    # ── painel piloto ─────────────────────────────────────────────────────────
    def _draw_driver(self, surf):
        f = self.app.fonts
        car = self.app.career
        d = car.player_driver
        if d is None:
            draw_text(surf, "Erro: piloto do jogador não encontrado neste save.",
                      f.h2, T.RED, (440, 300))
            return
        col = T.SERIES_COLOR.get(car.current_series_id, T.ACCENT)

        # Card do piloto (esquerda)
        accent_strip(surf, (28, 84, 380, 500), col)
        draw_text(surf, d.name, f.h1, T.TEXT, (54, 100))
        team_name = car.current_team.name if car.current_team else "Sem equipe"
        draw_text(surf, team_name, f.body, T.TEXT_DIM, (54, 140))
        chip(surf, SERIES_LABEL.get(car.current_series_id, ""), (54, 172), f.tiny, T.BG, col)

        # Overall grande
        draw_text(surf, "OVERALL", f.tiny, T.TEXT_DIM, (300, 110))
        draw_text(surf, f"{d.overall:.0f}", f.big_num, col, (370, 96), right=True)

        # Barras de atributos
        x, y, w = 54, 230, 320
        rv = self.reveal
        for label, val in [("Velocidade", d.speed), ("Consistência", d.consistency),
                           ("Ultrapassagem", d.overtaking), ("Pneus", d.tyre_mgmt),
                           ("Defesa", d.defence), ("Chuva", d.rain)]:
            y = stat_bar(surf, x, y, w, label, val, color=col, fonts=f, anim=rv) + 14

        # Super Licença
        y += 6
        draw_text(surf, "SUPER LICENÇA", f.tiny, T.TEXT_DIM, (x, y))
        draw_text(surf, f"{d.super_licence_points}/40", f.small, T.GOLD, (x + w, y - 2), right=True)
        pygame.draw.rect(surf, T.BG_INPUT, (x, y + 18, w, 7), border_radius=4)
        frac = min(1.0, d.super_licence_points / 40) * rv
        if frac > 0.002:
            pygame.draw.rect(surf, T.GOLD, (x, y + 18, max(4, int(w * frac)), 7), border_radius=4)

        # Saúde
        y += 38
        hcol = T.GREEN if d.health > 70 else (T.GOLD if d.health > 40 else T.RED)
        draw_text(surf, "SAÚDE", f.tiny, T.TEXT_DIM, (x, y))
        draw_text(surf, f"{d.health}%" + ("  LESIONADO" if d.is_injured else ""),
                  f.small, hcol, (x + w, y - 2), right=True)
        pygame.draw.rect(surf, T.BG_INPUT, (x, y + 18, w, 7), border_radius=4)
        if rv > 0.002:
            pygame.draw.rect(surf, hcol, (x, y + 18, max(4, int(w * d.health / 100 * rv)), 7),
                             border_radius=4)

        self._draw_next_round(surf, 430, 84)
        self._draw_standings(surf, 430, 250, car.driver_standings(),
                             highlight=d.id, kind="driver")

    # ── painel gerente ────────────────────────────────────────────────────────
    def _draw_manager(self, surf):
        f = self.app.fonts
        car = self.app.career
        t = car.player_team
        if t is None:
            draw_text(surf, "Erro: equipe do jogador não encontrada neste save.",
                      f.h2, T.RED, (440, 300))
            return
        col = T.SERIES_COLOR.get(car.current_series_id, T.ACCENT)

        accent_strip(surf, (28, 84, 380, 500), col)
        draw_text(surf, t.name, f.h1, T.TEXT, (54, 100))
        chip(surf, SERIES_LABEL.get(car.current_series_id, ""), (54, 150), f.tiny, T.BG, col)
        bud = f"€ {t.budget:,}".replace(",", ".")
        draw_text(surf, "ORÇAMENTO", f.tiny, T.TEXT_DIM, (54, 190))
        draw_text(surf, bud, f.h2, T.GOLD, (54, 208))

        # Carro
        x, y, w = 54, 260, 320
        for label, val in [("Chassi", t.chassis), ("Aerodinâmica", t.aerodynamics),
                           ("Confiabilidade", t.reliability), ("Motor/Eng.", t.engineers)]:
            y = stat_bar(surf, x, y, w, label, val, color=col, fonts=f, anim=self.reveal) + 12

        # Instalações
        y += 8
        draw_text(surf, "INSTALAÇÕES", f.tiny, T.TEXT_DIM, (x, y))
        y += 22
        facs = [("Fábrica", t.fac_factory), ("Simulador", t.fac_simulator),
                ("P&D", t.fac_r_and_d), ("Pit", t.fac_pit_crew), ("Mkt", t.fac_marketing)]
        fx = x
        for name, lvl in facs:
            box = pygame.Rect(fx, y, 58, 44)
            pygame.draw.rect(surf, T.BG_PANEL_2, box, border_radius=6)
            draw_text(surf, name, f.tiny, T.TEXT_DIM, (box.centerx, box.y + 5), center=True)
            # pips de nível (5 pontos, preenchidos = nível)
            px = box.centerx - 5 * 4 + 2
            for k in range(5):
                c = T.GOLD if k < lvl else T.LINE
                pygame.draw.circle(surf, c, (px + k * 9, box.y + 30), 3)
            fx += 64

        # Pilotos contratados
        y += 56
        draw_text(surf, "PILOTOS", f.tiny, T.TEXT_DIM, (x, y))
        y += 22
        for d in car.player_drivers():
            draw_text(surf, f"{d.name}", f.small, T.TEXT, (x, y))
            draw_text(surf, f"OVR {d.overall:.0f}", f.tiny, T.ACCENT_2, (x + w, y), right=True)
            y += 26

        self._draw_next_round(surf, 430, 84)
        self._draw_standings(surf, 430, 250, car.team_standings(),
                             highlight=t.id, kind="team")

    # ── próxima corrida ───────────────────────────────────────────────────────
    def _draw_next_round(self, surf, x, y):
        f = self.app.fonts
        car = self.app.career
        rnd = car.current_round()
        total = len(car.season.rounds) if car.season else 0
        done = car.season.current_round if car.season else 0
        panel(surf, (x, y, T.WIDTH - x - 28, 150), T.BG_PANEL)
        if rnd:
            draw_text(surf, "PRÓXIMA CORRIDA", f.tiny, T.ACCENT, (x + 20, y + 16))
            draw_text(surf, rnd.track_name, f.h1, T.TEXT, (x + 20, y + 36))
            draw_text(surf, f"{rnd.country}  ·  {rnd.laps} voltas  ·  {rnd.track_type}",
                      f.small, T.TEXT_DIM, (x + 20, y + 84))
        else:
            draw_text(surf, "TEMPORADA ENCERRADA", f.tiny, T.GOLD, (x + 20, y + 16))
            draw_text(surf, "Todas as corridas concluídas", f.h2, T.TEXT, (x + 20, y + 40))
            draw_text(surf, "Clique em ENCERRAR TEMPORADA para o balanço final",
                      f.small, T.TEXT_DIM, (x + 20, y + 84))
        # progresso de rodadas
        draw_text(surf, f"Rodada {min(done+1, total)}/{total}", f.small, T.TEXT,
                  (T.WIDTH - 44, y + 16), right=True)
        bx, bw = x + 20, T.WIDTH - x - 28 - 40
        pygame.draw.rect(surf, T.BG_INPUT, (bx, y + 122, bw, 8), border_radius=4)
        if total:
            pygame.draw.rect(surf, T.ACCENT, (bx, y + 122, int(bw * done / total), 8),
                             border_radius=4)

    # ── tabela de classificação ───────────────────────────────────────────────
    def _draw_standings(self, surf, x, y, standings, highlight, kind):
        f = self.app.fonts
        w = T.WIDTH - x - 28
        panel(surf, (x, y, w, 334), T.BG_PANEL)
        title = "CLASSIFICAÇÃO — PILOTOS" if kind == "driver" else "CLASSIFICAÇÃO — EQUIPES"
        draw_text(surf, title, f.tiny, T.ACCENT, (x + 20, y + 14))
        ry = y + 44
        for pos, obj, pts in standings[:8]:
            is_me = obj.id == highlight
            row = pygame.Rect(x + 12, ry - 4, w - 24, 32)
            if is_me:
                pygame.draw.rect(surf, T.BG_PANEL_2, row, border_radius=6)
                pygame.draw.rect(surf, T.ACCENT, row, width=1, border_radius=6)
            pcol = T.GOLD if pos == 1 else (T.TEXT if is_me else T.TEXT_DIM)
            draw_text(surf, f"P{pos}", f.small, pcol, (x + 24, ry))
            name = obj.name
            draw_text(surf, name, f.body if is_me else f.small,
                      T.TEXT if is_me else T.TEXT_DIM, (x + 78, ry - 1))
            draw_text(surf, f"{pts} pts", f.small, pcol, (x + w - 24, ry), right=True)
            ry += 36


# ══════════════════════════════════════════════════════════════════════════════
# SIMULANDO (tela de espera animada)
# ══════════════════════════════════════════════════════════════════════════════
class SimulatingScene(Scene):
    DURATION = 1.0

    def on_enter(self):
        self.t = 0.0
        self.done = False
        self.track = self.app.career.current_round()
        random.seed()
        self.lines = [(random.randint(0, T.WIDTH), random.randint(120, T.HEIGHT - 120),
                       random.randint(60, 180), random.uniform(0.6, 1.4))
                      for _ in range(26)]

    def update(self, dt):
        self.t += dt
        if self.t >= self.DURATION and not self.done:
            self.done = True
            res, ev = self.app.career.simulate_next_race()
            self.app.replace(RaceResultScene(self.app, res, ev))

    def handle(self, event):
        pass

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        cx, cy = T.WIDTH // 2, T.HEIGHT // 2
        # speed lines correndo
        for i, (lx, ly, ln, spd) in enumerate(self.lines):
            px = (lx - self.t * 900 * spd) % (T.WIDTH + 200) - 100
            shade = T.lerp(T.BG_PANEL, T.ACCENT, min(1.0, spd / 1.4) * 0.5)
            pygame.draw.line(surf, shade, (px, ly), (px + ln, ly), 2)
        name = self.track.track_name if self.track else ""
        country = self.track.country if self.track else ""
        draw_text(surf, "SIMULANDO CORRIDA", f.h1, T.ACCENT, (cx, cy - 110), center=True)
        draw_text(surf, name, f.title, T.TEXT, (cx, cy - 50), center=True)
        if country:
            draw_text(surf, country, f.body, T.TEXT_DIM, (cx, cy + 12), center=True)
        # barra de progresso com carrinho
        bw = 560
        bx, by = cx - bw // 2, cy + 60
        pygame.draw.rect(surf, T.BG_PANEL, (bx, by, bw, 12), border_radius=6)
        prog = min(1.0, self.t / self.DURATION)
        pygame.draw.rect(surf, T.ACCENT, (bx, by, int(bw * prog), 12), border_radius=6)
        draw_icon(surf, "play", bx + int(bw * prog), by + 6, 18, T.GOLD)
        dots = "." * (int(self.t * 4) % 4)
        draw_text(surf, "Aquecendo os pneus" + dots, f.small, T.TEXT_DIM, (cx, cy + 100), center=True)


# ══════════════════════════════════════════════════════════════════════════════
# RESULTADO DA CORRIDA
# ══════════════════════════════════════════════════════════════════════════════
EVENT_PT = {
    "safety_car":      ("Safety Car", T.GOLD),
    "safety_car_end":  ("SC recolhido", T.TEXT_DIM),
    "virtual_safety":  ("Virtual Safety Car", T.GOLD),
    "engine_failure":  ("Quebra de motor", T.RED),
    "puncture":        ("Pneu furado", T.RED),
    "crash":           ("Batida", T.RED),
    "spin":            ("Rodada/erro", T.ACCENT),
    "injury":          ("Lesão", T.RED),
    "fp1_bonus":       ("FP1", T.ACCENT_2),
    "penalty":         ("Punição", T.RED),
}

# layout da tabela
_RT_X, _RT_Y, _RT_W, _RT_H = 60, 96, 880, 560
_RT_ROW = 34
_RT_HEAD = 44


class RaceResultScene(Scene):
    def __init__(self, app, results, events):
        super().__init__(app)
        self.results = results
        self.events = events

    def on_enter(self):
        f = self.app.fonts
        self.ok_btn = Button((T.WIDTH // 2 - 130, T.HEIGHT - 64, 260, 50),
                             "CONTINUAR", self._continue, f.h2, icon="play")
        car = self.app.career
        self.my_id = (car.player_driver.id if self.app.profile.mode == "driver"
                      else None)
        self.my_team = (car.player_team.id if self.app.profile.mode != "driver" else None)
        self.t = 0.0
        self.scroll = 0
        # tempo do vencedor (para gaps)
        fin = [r for r in self.results if not r.dnf]
        self.winner_time = min((r.total_time for r in fin), default=0.0)
        self.visible = (_RT_H - _RT_HEAD - 6) // _RT_ROW
        self.max_scroll = max(0, len(self.results) - self.visible)
        # rola até o jogador na primeira exibição
        idx = next((i for i, r in enumerate(self.results)
                    if r.driver_id == self.my_id or
                    (self.my_team and r.team_id == self.my_team)), 0)
        self.scroll = max(0, min(self.max_scroll, idx - self.visible // 2))

    def update(self, dt):
        self.t += dt

    def _continue(self):
        self.app.pop()
        offer = make_offer(self.app)
        if offer:
            self.app.push(OfferScene(self.app, offer))

    def handle(self, event):
        self.ok_btn.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll = max(0, self.scroll - 1)
            elif event.button == 5:
                self.scroll = min(self.max_scroll, self.scroll + 1)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_PAGEUP):
                self.scroll = max(0, self.scroll - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                self.scroll = min(self.max_scroll, self.scroll + 1)

    def _gap_text(self, r):
        if r.dnf:
            return ("DNF" + (f" · {r.dnf_reason}" if r.dnf_reason else ""), T.RED)
        if r.position == 1:
            return ("LÍDER", T.GOLD)
        gap = r.total_time - self.winner_time
        return (f"+{gap:.1f}s", T.TEXT_DIM)

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        x, y, w, h = _RT_X, _RT_Y, _RT_W, _RT_H
        draw_text(surf, "RESULTADO DA CORRIDA", f.h1, T.ACCENT, (x, 44))
        draw_text(surf, "role para ver toda a grade", f.tiny, T.TEXT_FAINT, (x + 360, 58))

        panel(surf, (x, y, w, h), T.BG_PANEL)
        # cabeçalho de colunas
        cP, cN, cT, cG, cTy, cPt = x+22, x+70, x+330, x+560, x+690, x+w-24
        draw_text(surf, "POS", f.tiny, T.TEXT_DIM, (cP, y+16))
        draw_text(surf, "PILOTO", f.tiny, T.TEXT_DIM, (cN, y+16))
        draw_text(surf, "EQUIPE", f.tiny, T.TEXT_DIM, (cT, y+16))
        draw_text(surf, "GAP / STATUS", f.tiny, T.TEXT_DIM, (cG, y+16))
        draw_text(surf, "PNEUS", f.tiny, T.TEXT_DIM, (cTy, y+16))
        draw_text(surf, "PTS", f.tiny, T.TEXT_DIM, (cPt, y+16), right=True)
        pygame.draw.line(surf, T.LINE, (x+14, y+_RT_HEAD-4), (x+w-14, y+_RT_HEAD-4), 1)

        prev = surf.get_clip()
        surf.set_clip(pygame.Rect(x, y+_RT_HEAD, w, h-_RT_HEAD))
        ry = y + _RT_HEAD + 4
        fade = min(1.0, self.t * 2.2)
        for r in self.results[self.scroll:self.scroll + self.visible + 1]:
            is_me = (r.driver_id == self.my_id) or (self.my_team and r.team_id == self.my_team)
            row = pygame.Rect(x+12, ry-3, w-24, _RT_ROW-2)
            if is_me:
                pygame.draw.rect(surf, T.BG_PANEL_2, row, border_radius=6)
                pygame.draw.rect(surf, T.ACCENT, row, width=2, border_radius=6)
            pcol = T.GOLD if r.position == 1 else (T.TEXT if is_me else T.TEXT_DIM)
            ptxt = "DNF" if r.dnf else f"{r.position}"
            draw_text(surf, ptxt, f.small, T.RED if r.dnf else pcol, (cP, ry))
            nm = r.driver_name + ("  ·VR" if r.fastest_lap else "")
            draw_text(surf, nm, f.small,
                      T.PURPLE if r.fastest_lap else (T.TEXT if is_me else T.TEXT),
                      (cN, ry))
            draw_text(surf, r.team_name, f.tiny, T.TEXT_FAINT, (cT, ry+2))
            gtxt, gcol = self._gap_text(r)
            draw_text(surf, gtxt, f.small, gcol, (cG, ry))
            tyres = "·".join(s.split("(")[0][0].upper() for s in r.tyre_strategy) or "-"
            draw_text(surf, f"{tyres}  {r.pit_stops}p", f.tiny, T.TEXT_FAINT, (cTy, ry+2))
            draw_text(surf, f"{r.points}", f.body if is_me else f.small,
                      pcol, (cPt, ry), right=True)
            ry += _RT_ROW
        surf.set_clip(prev)

        # barra de rolagem
        if self.max_scroll > 0:
            track_h = h - _RT_HEAD - 8
            knob_h = max(24, int(track_h * self.visible / len(self.results)))
            knob_y = y + _RT_HEAD + 4 + int((track_h - knob_h) * self.scroll / self.max_scroll)
            pygame.draw.rect(surf, T.LINE, (x+w-8, y+_RT_HEAD+4, 4, track_h), border_radius=2)
            pygame.draw.rect(surf, T.ACCENT, (x+w-8, knob_y, 4, knob_h), border_radius=2)

        # painel de eventos da corrida
        ex, ew = x + w + 20, T.WIDTH - (x + w + 20) - 40
        panel(surf, (ex, y, ew, h), T.BG_PANEL)
        draw_text(surf, "O QUE ACONTECEU", f.tiny, T.ACCENT, (ex+18, y+16))
        ev_list = [e for e in self.events
                   if getattr(e, "event_type", "") in EVENT_PT]
        ev_list.sort(key=lambda e: getattr(e, "lap", 0))
        ey = y + 48
        if not ev_list:
            draw_text(surf, "Corrida limpa, sem incidentes.", f.small, T.TEXT_DIM, (ex+18, ey))
        for e in ev_list[:14]:
            label, col = EVENT_PT.get(e.event_type, (e.event_type, T.TEXT_DIM))
            lap = getattr(e, "lap", 0)
            tag = f"V{lap}" if lap else "—"
            draw_text(surf, tag, f.tiny, T.TEXT_FAINT, (ex+18, ey+2))
            draw_text(surf, label, f.small, col, (ex+58, ey))
            # nome do piloto afetado
            did = getattr(e, "affects_driver", None)
            if did:
                drv = next((r.driver_name for r in self.results if r.driver_id == did), "")
                if drv:
                    draw_text(surf, drv, f.tiny, T.TEXT_DIM, (ex+58, ey+20))
                    ey += 18
            ey += 30
        self.ok_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# FIM DE TEMPORADA
# ══════════════════════════════════════════════════════════════════════════════
class SeasonEndScene(Scene):
    def __init__(self, app, summary):
        super().__init__(app)
        self.s = summary

    def on_enter(self):
        f = self.app.fonts
        self.promoted = self.s.get("promoted", False)
        label = "SUBIR DE CATEGORIA ▶" if self.promoted else "PRÓXIMA TEMPORADA ▶"
        self.go_btn = Button((T.WIDTH // 2 - 160, T.HEIGHT - 90, 320, 54),
                             label, self._next, f.h2,
                             color=T.GOLD if self.promoted else T.ACCENT)
        self.menu_btn = Button((40, T.HEIGHT - 90, 160, 52), "MENU",
                               lambda: self.app.reset_to(MenuScene(self.app)),
                               f.body, kind="ghost")

    def _next(self):
        car = self.app.career
        profile = self.app.profile
        if profile.mode == "driver":
            clt = apply_driver_season_transition(car, self.s, profile)
            if clt:
                self.app.reset_to(CLTScene(self.app, car.current_series_id))
                return
        else:
            car.start_new_season(promote=self.promoted)
        self.app.reset_to(CareerScene(self.app))

    def handle(self, event):
        self.go_btn.handle(event)
        self.menu_btn.handle(event)

    def update(self, dt):
        pass

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        s = self.s
        cx = T.WIDTH // 2
        draw_text(surf, "FIM DE TEMPORADA", f.h1, T.ACCENT, (cx, 50), center=True)

        panel(surf, (cx - 380, 110, 760, 460), T.BG_PANEL)
        x = cx - 340
        y = 140

        is_driver = self.app.profile.mode == "driver"
        pos = s.get("player_position") if is_driver else s.get("team_position")
        pcol = T.GOLD if pos == 1 else T.TEXT
        draw_text(surf, "SUA POSIÇÃO FINAL", f.small, T.TEXT_DIM, (x, y))
        draw_text(surf, f"P{pos}", f.big_num, pcol, (x, y + 22))

        draw_text(surf, "CAMPEÃO", f.small, T.TEXT_DIM, (cx + 60, y))
        draw_text(surf, s.get("champion_driver", "?"), f.h2, T.TEXT, (cx + 60, y + 26))
        draw_text(surf, s.get("champion_team", ""), f.small, T.TEXT_DIM, (cx + 60, y + 60))

        y += 130
        pygame.draw.rect(surf, T.LINE, (x, y, 680, 1))
        y += 20

        rows = []
        if is_driver:
            rows.append(("Pontos de Super Licença ganhos", f"+{s.get('sl_earned', 0)}"))
            rows.append(("Total Super Licença", f"{s.get('sl_total', 0)}/40"))
            rows.append(("Prêmio em dinheiro", f"€ {s.get('prize_money', 0):,}".replace(",", ".")))
            rows.append(("Dinheiro pessoal", f"€ {s.get('personal_money', 0):,}".replace(",", ".")))
            if s.get("sl_blocked"):
                rows.append(("Promoção bloqueada", s.get("sl_block_reason", "")))
        else:
            rows.append(("Renda de patrocinadores", f"€ {s.get('sponsor_income', 0):,}".replace(",", ".")))
            rows.append(("Prêmio em dinheiro", f"€ {s.get('prize_money', 0):,}".replace(",", ".")))
            rows.append(("Dividendo pessoal", f"€ {s.get('dividend', 0):,}".replace(",", ".")))
            rows.append(("Orçamento final", f"€ {s.get('final_budget', 0):,}".replace(",", ".")))
        for label, val in rows:
            draw_text(surf, label, f.body, T.TEXT_DIM, (x, y))
            draw_text(surf, val, f.body, T.TEXT, (x + 680, y), right=True)
            y += 36

        # Evolução de habilidades (modo piloto)
        deltas = s.get("skill_deltas") or {}
        if is_driver and deltas:
            y += 6
            draw_text(surf, "EVOLUÇÃO", f.tiny, T.ACCENT, (x, y)); y += 26
            labels = {"speed": "Velocidade", "consistency": "Consistência",
                      "tyre_mgmt": "Pneus", "overtaking": "Ultrapassagem",
                      "defence": "Defesa", "rain": "Chuva", "feedback": "Feedback técnico"}
            dx = x
            for attr, dv in deltas.items():
                if dv == 0:
                    continue
                txt = f"{labels.get(attr, attr)} {'+' if dv > 0 else ''}{dv}"
                col = T.GREEN if dv > 0 else T.RED
                rect = chip(surf, txt, (dx, y), f.small, T.BG, col)
                dx += rect.width + 8
                if dx > x + 560:
                    dx = x; y += 34
            if not any(deltas.values()):
                draw_text(surf, "Sem mudanças neste ano", f.small, T.TEXT_FAINT, (x, y))

        if self.promoted:
            draw_text(surf, f"PROMOVIDO PARA {SERIES_LABEL.get(s.get('promotes_to',''), '')}",
                      f.h2, T.GREEN, (cx, 548), center=True)
        elif not s.get("sl_blocked"):
            draw_text(surf, "Continua na mesma categoria", f.small, T.TEXT_DIM,
                      (cx, 550), center=True)

        self.go_btn.draw(surf)
        self.menu_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# CARREGAR JOGO
# ══════════════════════════════════════════════════════════════════════════════
class LoadScene(Scene):
    def on_enter(self):
        f = self.app.fonts
        self.saves = save_load.list_saves()
        self.list = SelectList((cx_center(), 180, 700, 380), self.saves, f.body,
                               row_h=70, render_row=self._row)
        self.load_btn = Button((T.WIDTH // 2 - 230, T.HEIGHT - 90, 220, 52),
                               "CARREGAR  ▶", self._load, f.h2)
        self.back_btn = Button((T.WIDTH // 2 + 20, T.HEIGHT - 90, 200, 52),
                               "VOLTAR", self.app.pop, f.body, kind="ghost")

    def _row(self, surf, sv, row, sel, fonts):
        mode = "Piloto" if sv.get("mode") == "driver" else "Gerente"
        draw_text(surf, f"{sv.get('name','?')}  ·  {mode}", fonts.h2, T.TEXT, (row.x + 16, row.y + 8))
        sub = f"{SERIES_LABEL.get(sv.get('series',''), sv.get('series',''))} · {sv.get('year','?')} · slot {sv.get('slot','')}"
        draw_text(surf, sub, fonts.small, T.TEXT_DIM, (row.x + 16, row.y + 40))

    def _load(self):
        if not self.saves:
            return
        sv = self.list.current()
        profile, career = save_load.load_game(sv["slot"])
        if profile and career:
            self.app.profile = profile
            self.app.career = career
            self.app.reset_to(CareerScene(self.app))
        else:
            self.app.notify("Falha ao carregar")

    def handle(self, event):
        if self.saves:
            self.list.handle(event)
            self.load_btn.handle(event)
        self.back_btn.handle(event)

    def update(self, dt):
        pass

    def draw(self, surf):
        gradient_bg(surf)
        header(surf, self.app, "Carregar jogo")
        f = self.app.fonts
        draw_text(surf, "Saves disponíveis", f.h1, T.TEXT, (cx_center(), 120))
        if not self.saves:
            draw_text(surf, "Nenhum save encontrado.", f.body, T.TEXT_DIM,
                      (T.WIDTH // 2, 300), center=True)
        else:
            panel(surf, (cx_center() - 10, 170, 720, 400), T.BG_PANEL)
            self.list.draw(surf, f)
            self.load_btn.draw(surf)
        self.back_btn.draw(surf)


def cx_center():
    return (T.WIDTH - 700) // 2


# ══════════════════════════════════════════════════════════════════════════════
# OFERTAS (portado de main.py)
# ══════════════════════════════════════════════════════════════════════════════
def _build_offer_dict(otype, team, series_id, salary, years, forced=False):
    descs = {
        "step_up":        f"{team.name} quer você na {SERIES_LABEL.get(series_id,'?')}!",
        "step_down":      f"{team.name} oferece liderança em {SERIES_LABEL.get(series_id,'?')}.",
        "lateral_better": f"{team.name} quer você (carro melhor: {team.car_performance:.0f}).",
        "lateral_worse":  f"{team.name} oferece mais salário.",
        "fired":          f"Sua equipe te dispensa. {team.name} pode absorver.",
    }
    return {
        "type": otype, "from_team": team.name, "from_team_id": team.id,
        "from_series": series_id, "from_series_label": SERIES_LABEL.get(series_id, series_id),
        "salary": salary, "years": years, "description": descs.get(otype, ""),
        "team_chassis": team.chassis, "team_rep": team.reputation, "forced": forced,
    }


def _gen_driver_offer(career):
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
        ["step_up", "step_down", "lateral_better", "lateral_worse", "fired"],
        weights=weights)[0]
    cur_id = career.current_team.id if career.current_team else ""
    if otype == "step_up":
        next_s = series_above(career.current_series_id)
        if not next_s:
            return None
        if next_s == "formula_1":
            ok, _ = sl.check_f1_eligibility(pd)
            if not ok:
                return None
        teams = load_teams_for_series(next_s)
        target = random.choice(teams[2:7] if len(teams) > 7 else teams)
        return _build_offer_dict(otype, target, next_s,
                                 max(pd.salary, int(target.budget * 0.12)), random.randint(1, 2))
    if otype == "step_down":
        prev_s = series_below(career.current_series_id)
        if not prev_s:
            return None
        teams = load_teams_for_series(prev_s)
        return _build_offer_dict(otype, random.choice(teams[:4]), prev_s,
                                 int(pd.salary * 1.2), random.randint(1, 2))
    if otype == "fired":
        others = [t for t in career.all_teams if t.id != cur_id]
        if not others:
            return None
        return _build_offer_dict(otype, random.choice(others[-3:]),
                                 career.current_series_id, int(pd.salary * 0.85), 1, forced=True)
    if otype == "lateral_better":
        cur_perf = career.current_team.car_performance if career.current_team else 0
        better = [t for t in career.all_teams if t.id != cur_id and t.car_performance > cur_perf]
        if not better:
            return None
        return _build_offer_dict(otype, random.choice(better), career.current_series_id,
                                 int(pd.salary * random.uniform(1.0, 1.2)), random.randint(1, 2))
    worse = [t for t in career.all_teams if t.id != cur_id]
    if not worse:
        return None
    return _build_offer_dict(otype, random.choice(worse), career.current_series_id,
                             int(pd.salary * random.uniform(1.2, 1.6)), random.randint(1, 2))


class _ManagerCareerCompat:
    def __init__(self, c): self._c = c
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


def make_offer(app):
    car = app.career
    try:
        if app.profile.mode == "driver":
            offer = _gen_driver_offer(car)
        else:
            offer = generate_offer(_ManagerCareerCompat(car))
    except Exception:
        return None
    if not offer:
        return None
    # Já assinou para o ano que vem? Só aceita proposta de categoria ESTRITAMENTE superior.
    pending = getattr(car, "_pending_offer", None)
    if pending:
        try:
            new_i = SERIES_PROGRESSION.index(offer["from_series"])
            cur_i = SERIES_PROGRESSION.index(pending["from_series"])
        except ValueError:
            return None
        if new_i <= cur_i:
            return None
        offer["has_pending"] = True  # haverá multa de quebra de contrato
    return offer


def apply_driver_season_transition(career, report, profile):
    """Aplica oferta pendente / demissão pós-temporada. Retorna True se virou CLT."""
    # Demissão se mal posicionado e sem oferta
    if report["player_position"] > 8 and not career._pending_offer:
        if random.random() < (report["player_position"] - 8) * 0.15:
            others = [t for t in career.all_teams
                      if t.id != (career.current_team.id if career.current_team else "")]
            if not others or random.random() < 0.3:
                return True  # CLT
            target = random.choice(others)
            career._pending_offer = _build_offer_dict(
                "fired", target, career.current_series_id,
                max(20000, career.player_driver.salary // 2), 1, forced=True)

    pending = career._pending_offer
    career._pending_offer = None
    if pending:
        new_team_id = pending["from_team_id"]
        career.current_series_id = pending["from_series"]
        career.career_year  += 1
        career.season_number += 1
        career.series_rules = load_series(career.current_series_id)
        career.all_drivers  = load_drivers_for_series(career.current_series_id)
        career.all_teams    = load_teams_for_series(career.current_series_id)
        pd_saved = career.player_driver
        career.all_drivers.append(pd_saved)
        career.current_team = next((t for t in career.all_teams if t.id == new_team_id),
                                   career.all_teams[0])
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
        career.start_new_season(report["promoted"], None)
    return False


# ══════════════════════════════════════════════════════════════════════════════
# SUB-TELA BASE
# ══════════════════════════════════════════════════════════════════════════════
class SubScene(Scene):
    """Tela com cabeçalho + botão Voltar padronizado."""
    title = "Tela"
    subtitle = ""

    def on_enter(self):
        self.back_btn = Button((40, T.HEIGHT - 70, 180, 52), "VOLTAR",
                               self._close, self.app.fonts.body, kind="ghost", icon="menu")
        self.setup()

    def setup(self): ...
    def _close(self):
        self.app.pop()

    def body(self, surf): ...

    def handle(self, event):
        self.back_btn.handle(event)
        self.body_handle(event)

    def body_handle(self, event): ...
    def update(self, dt): ...

    def draw(self, surf):
        gradient_bg(surf)
        header(surf, self.app, self.title)
        if self.subtitle:
            draw_text(surf, self.subtitle, self.app.fonts.small, T.TEXT_DIM, (40, 80))
        self.body(surf)
        self.back_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO COMPLETA
# ══════════════════════════════════════════════════════════════════════════════
class StandingsScene(SubScene):
    title = "Classificação"
    subtitle = "role com o mouse para ver toda a grade"
    ROW = 34
    TOP = 154
    PANEL_Y, PANEL_H = 110, 540

    def setup(self):
        self.scroll_d = 0
        self.scroll_t = 0
        self.visible = (self.PANEL_H - (self.TOP - self.PANEL_Y) - 12) // self.ROW

    def body_handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
            car = self.app.career
            n_d = len(car.driver_standings())
            n_t = len(car.team_standings())
            on_teams = event.pos[0] > 650
            d = -1 if event.button == 4 else 1
            if on_teams:
                self.scroll_t = max(0, min(max(0, n_t - self.visible), self.scroll_t + d))
            else:
                self.scroll_d = max(0, min(max(0, n_d - self.visible), self.scroll_d + d))

    def _draw_col(self, surf, f, rows, x, w, title, scroll, my_id_fn, name_fn, short_fn):
        panel(surf, (x, self.PANEL_Y, w, self.PANEL_H), T.BG_PANEL)
        draw_text(surf, title, f.tiny, T.ACCENT, (x + 20, 124))
        prev = surf.get_clip()
        surf.set_clip(pygame.Rect(x, self.TOP - 6, w, self.PANEL_H - (self.TOP - self.PANEL_Y) - 6))
        ry = self.TOP
        for pos, obj, pts in rows[scroll:scroll + self.visible + 1]:
            mine = my_id_fn(obj)
            if mine:
                r = pygame.Rect(x + 12, ry - 3, w - 24, 30)
                pygame.draw.rect(surf, T.BG_PANEL_2, r, border_radius=5)
                pygame.draw.rect(surf, T.ACCENT, r, width=1, border_radius=5)
            c = T.GOLD if pos == 1 else (T.TEXT if mine else T.TEXT_DIM)
            draw_text(surf, f"{pos}", f.small, c, (x + 24, ry))
            draw_text(surf, name_fn(obj), f.small, c, (x + 64, ry))
            if short_fn:
                draw_text(surf, short_fn(obj), f.tiny, T.TEXT_FAINT, (x + w - 130, ry + 2))
            draw_text(surf, f"{pts}", f.small, c, (x + w - 24, ry), right=True)
            ry += self.ROW
        surf.set_clip(prev)
        # barra de rolagem
        total = len(rows)
        if total > self.visible:
            th = self.PANEL_H - (self.TOP - self.PANEL_Y) - 12
            kh = max(24, int(th * self.visible / total))
            ky = self.TOP + int((th - kh) * scroll / max(1, total - self.visible))
            pygame.draw.rect(surf, T.ACCENT, (x + w - 7, ky, 4, kh), border_radius=2)

    def body(self, surf):
        f = self.app.fonts
        car = self.app.career
        is_driver = self.app.profile.mode == "driver"
        my_did = car.player_driver.id if is_driver else None
        my_tid = None if is_driver else car.player_team.id

        def driver_mine(d):
            team = next((t for t in car.all_teams if d.id in t.drivers), None)
            return (d.id == my_did) or (team and team.is_player_team)

        def driver_short(d):
            team = next((t for t in car.all_teams if d.id in t.drivers), None)
            return team.short if team else "—"

        self._draw_col(surf, f, car.driver_standings(), 40, 600, "PILOTOS",
                       self.scroll_d, driver_mine, lambda d: d.name, driver_short)
        self._draw_col(surf, f, car.team_standings(), 660, T.WIDTH - 660 - 40, "EQUIPES",
                       self.scroll_t, lambda t: (t.id == my_tid) or t.is_player_team,
                       lambda t: t.name, None)


# ══════════════════════════════════════════════════════════════════════════════
# SUPER LICENÇA
# ══════════════════════════════════════════════════════════════════════════════
class SuperLicenceScene(SubScene):
    title = "Super Licença FIA"
    subtitle = "Requisito F1: 40 pontos + idade 18+"

    def body(self, surf):
        f = self.app.fonts
        pd = self.app.career.player_driver
        s = sl.sl_summary(pd)
        panel(surf, (40, 130, 700, 480), T.BG_PANEL)
        x = 70
        draw_text(surf, pd.name, f.h1, T.TEXT, (x, 150))
        draw_text(surf, f"{pd.age} anos · {pd.nationality}", f.small, T.TEXT_DIM, (x, 192))
        elig = s["eligible"]
        chip(surf, "ELEGÍVEL PARA F1" if elig else "NÃO ELEGÍVEL", (x, 228), f.small,
             T.BG, T.GREEN if elig else T.RED)
        # barra
        draw_text(surf, f"PONTOS  {s['total_points']}/40", f.small, T.GOLD, (x, 280))
        pygame.draw.rect(surf, T.BG_INPUT, (x, 308, 640, 14), border_radius=7)
        pygame.draw.rect(surf, T.GOLD, (x, 308, int(640 * min(1, s['total_points']/40)), 14),
                         border_radius=7)
        draw_text(surf, f"Sessões FP1: {s['fp1_sessions']}  (+{s['fp1_points']} pts)",
                  f.small, T.ACCENT_2, (x, 340))
        if not elig:
            draw_text(surf, s["reason"], f.small, T.RED, (x, 372))
        # histórico
        draw_text(surf, "HISTÓRICO", f.tiny, T.ACCENT, (x, 416))
        ry = 444
        for h in s["history"]:
            draw_text(surf, f"{h['year']}", f.small, T.TEXT_DIM, (x, ry))
            draw_text(surf, h['series'].replace('_', ' ').title(), f.small, T.TEXT, (x + 70, ry))
            draw_text(surf, f"+{h['points']} pts", f.small, T.GOLD, (x + 600, ry), right=True)
            ry += 30


# ══════════════════════════════════════════════════════════════════════════════
# ACADEMIA
# ══════════════════════════════════════════════════════════════════════════════
class AcademyScene(SubScene):
    title = "Academias de Pilotos"

    def setup(self):
        self.ac_list = list(acad.load_academies().values())
        f = self.app.fonts
        self.list = SelectList((40, 130, 760, 420), self.ac_list, f.body, row_h=66,
                               render_row=self._row)
        self.join_btn = Button((820, 150, 250, 50), "JUNTAR-SE", self._join, f.body, icon="cap")
        self.leave_btn = Button((820, 215, 250, 50), "SAIR DA ACADEMIA", self._leave,
                                f.body, kind="ghost")

    def _row(self, surf, a, row, sel, fonts):
        pd = self.app.career.player_driver
        cur = pd.academy_id == a.id
        draw_text(surf, a.name + ("  ✓" if cur else ""), fonts.h2,
                  T.GREEN if cur else T.TEXT, (row.x + 14, row.y + 6))
        disc = int(a.benefits.get("salary_discount", 0) * 100)
        pot  = a.benefits.get("potential_bonus_per_season", 0)
        fp1  = int(a.benefits.get("fp1_access_chance", 0) * 100)
        draw_text(surf, f"Prestígio {a.prestige}  ·  Desc {disc}%  ·  Pot +{pot}/ano  ·  FP1 {fp1}%",
                  fonts.tiny, T.TEXT_DIM, (row.x + 14, row.y + 38))

    def _join(self):
        pd = self.app.career.player_driver
        if pd.academy_id:
            self.app.notify("Saia da atual primeiro"); return
        a = self.list.current()
        ok, msg = acad.join_academy(pd, a.id, {"budget": self.app.profile.personal_money})
        self.app.notify(msg)

    def _leave(self):
        pd = self.app.career.player_driver
        if not pd.academy_id:
            self.app.notify("Não está em academia"); return
        fee = acad.buyout_fee(pd.academy_id)
        ok, msg = acad.leave_academy(pd, fee <= self.app.profile.personal_money,
                                     {"budget": self.app.profile.personal_money})
        self.app.notify(msg)

    def body_handle(self, event):
        self.list.handle(event)
        self.join_btn.handle(event)
        self.leave_btn.handle(event)

    def body(self, surf):
        f = self.app.fonts
        pd = self.app.career.player_driver
        panel(surf, (40, 120, 770, 440), T.BG_PANEL)
        self.list.draw(surf, f)
        draw_text(surf, f"Academia atual: {pd.academy_id or 'Nenhuma'}", f.small,
                  T.TEXT_DIM, (820, 290))
        self.join_btn.draw(surf)
        self.leave_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# DESENVOLVIMENTO / INSTALAÇÕES (melhoria de carro)
# ══════════════════════════════════════════════════════════════════════════════
class DevelopmentScene(SubScene):
    title = "Desenvolvimento & Instalações"

    FAC = [("Fábrica", "fac_factory", "factory"),
           ("Simulador", "fac_simulator", "simulator"),
           ("P&D", "fac_r_and_d", "r_and_d"),
           ("Pit Crew", "fac_pit_crew", "pit_crew"),
           ("Marketing", "fac_marketing", "marketing")]
    CAR = [("Chassi", "chassis", 150_000, 3),
           ("Aerodinâmica", "aerodynamics", 180_000, 3),
           ("Confiabilidade", "reliability", 120_000, 4),
           ("Pit Crew (carro)", "pit_crew", 80_000, 3),
           ("Engenheiros", "engineers", 100_000, 2),
           ("Fábrica (carro)", "factory", 200_000, 3)]

    def setup(self):
        self.fac_btns = []
        self.car_btns = []

    def _upgrade_fac(self, attr, key, lbl):
        t = self.app.career.player_team
        lvl = getattr(t, attr, 1)
        cost = t.facilities.upgrade_cost(key)
        if lvl >= 5:
            self.app.notify(f"{lbl} já no máximo")
        elif t.budget < cost:
            self.app.notify("Sem orçamento")
        else:
            setattr(t, attr, lvl + 1); t.budget -= cost
            self.app.notify(f"{lbl}: nível {lvl}→{lvl+1}")

    def _upgrade_car(self, attr, cost, gain, lbl):
        t = self.app.career.player_team
        cur = getattr(t, attr)
        if cur >= 99:
            self.app.notify(f"{lbl} no máximo")
        elif t.budget < cost:
            self.app.notify("Sem orçamento")
        else:
            setattr(t, attr, min(99, cur + gain)); t.budget -= cost
            self.app.notify(f"{lbl}: {cur}→{getattr(t, attr)}")

    def body_handle(self, event):
        for b in self.fac_btns + self.car_btns:
            b.handle(event)

    def body(self, surf):
        f = self.app.fonts
        t = self.app.career.player_team
        draw_text(surf, f"Orçamento: € {t.budget:,}".replace(",", "."),
                  f.h2, T.GOLD, (40, 78))
        self.fac_btns = []
        self.car_btns = []
        # Instalações (coluna esquerda)
        panel(surf, (40, 120, 580, 250), T.BG_PANEL)
        draw_text(surf, "INSTALAÇÕES", f.tiny, T.ACCENT, (60, 132))
        y = 162
        for lbl, attr, key in self.FAC:
            lvl = getattr(t, attr, 1)
            cost = t.facilities.upgrade_cost(key)
            draw_text(surf, lbl, f.body, T.TEXT, (60, y))
            # pips
            for k in range(5):
                c = T.GOLD if k < lvl else T.LINE
                pygame.draw.circle(surf, c, (250 + k * 14, y + 12), 5)
            maxed = lvl >= 5
            label = "MÁX" if maxed else f"€ {cost:,}".replace(",", ".")
            b = Button((400, y - 4, 200, 34), label,
                       (lambda a=attr, k=key, l=lbl: self._upgrade_fac(a, k, l)),
                       f.small, kind="ghost" if (maxed or t.budget < cost) else "primary")
            b.enabled = not maxed
            self.fac_btns.append(b); b.draw(surf)
            y += 42
        # Carro (coluna direita)
        panel(surf, (640, 120, T.WIDTH - 640 - 40, 430), T.BG_PANEL)
        draw_text(surf, "CARRO", f.tiny, T.ACCENT, (660, 132))
        y = 162
        for lbl, attr, cost, gain in self.CAR:
            cur = getattr(t, attr)
            draw_text(surf, lbl, f.body, T.TEXT, (660, y))
            draw_text(surf, f"{cur}/100", f.small, T.ACCENT_2, (860, y))
            can = t.budget >= cost and cur < 99
            b = Button((T.WIDTH - 40 - 230, y - 4, 230, 34),
                       f"+{gain}   € {cost:,}".replace(",", "."),
                       (lambda a=attr, c=cost, g=gain, l=lbl: self._upgrade_car(a, c, g, l)),
                       f.small, kind="primary" if can else "ghost")
            b.enabled = can
            self.car_btns.append(b); b.draw(surf)
            y += 44
        fac = t.facilities
        draw_text(surf,
                  f"Dev x{fac.dev_speed_multiplier():.2f}   Pit -{fac.pit_time_bonus():.1f}s   "
                  f"Patroc. x{fac.sponsor_multiplier():.2f}",
                  f.small, T.TEXT_DIM, (60, 392))


# ══════════════════════════════════════════════════════════════════════════════
# TRANSFERÊNCIAS
# ══════════════════════════════════════════════════════════════════════════════
class TransferScene(SubScene):
    title = "Janela de Transferências"

    def setup(self):
        self.market = TransferMarket(self.app.career)
        f = self.app.fonts
        self._refresh_free()
        self.free_list = SelectList((660, 150, T.WIDTH - 660 - 40, 360),
                                    self.free, f.body, row_h=52, render_row=self._free_row)
        self.sign_btn = Button((660, 540, 250, 46), "CONTRATAR (auto)", self._sign, f.small, icon="transfer")
        self.my_btns = []

    def _refresh_free(self):
        car = self.app.career
        pt = car.player_team
        self.free = sorted(
            [d for d in car.all_drivers
             if (not d.team_id or d.contract_years <= 0) and d.id not in pt.drivers],
            key=lambda d: -d.overall)

    def _free_row(self, surf, d, row, sel, fonts):
        draw_text(surf, d.name, fonts.body, T.TEXT, (row.x + 12, row.y + 6))
        mv = driver_market_value(d, 0)
        draw_text(surf, f"OVR {d.overall:.0f}  ·  € {mv:,}".replace(",", "."),
                  fonts.tiny, T.TEXT_DIM, (row.x + 12, row.y + 30))

    def _renew(self, d):
        mv = driver_market_value(d, self.app.career.standings_drivers.get(d.id, 0))
        ok, msg = self.market.renew_contract(d.id, int(mv * 0.9), 2)
        self.app.notify(msg)

    def _release(self, d):
        car = self.app.career
        self.market.release_driver(d.id)
        if d.id in car.player_team.drivers:
            car.player_team.drivers.remove(d.id)
        self._refresh_free()
        self.free_list.items = self.free
        self.app.notify(f"{d.name} liberado")

    def _sign(self):
        car = self.app.career
        if len(car.player_team.drivers) >= 2:
            self.app.notify("Libere um piloto primeiro"); return
        if not self.free:
            self.app.notify("Sem agentes livres"); return
        d = self.free_list.current()
        mv = driver_market_value(d, 0)
        ok, msg = self.market.sign_driver(d.id, int(mv * 0.9), 2)
        self.app.notify(msg)
        self._refresh_free(); self.free_list.items = self.free

    def body_handle(self, event):
        for b in self.my_btns:
            b.handle(event)
        self.free_list.handle(event)
        self.sign_btn.handle(event)

    def body(self, surf):
        f = self.app.fonts
        car = self.app.career
        pt = car.player_team
        draw_text(surf, f"Orçamento: € {pt.budget:,}".replace(",", "."), f.h2, T.GOLD, (40, 78))
        panel(surf, (40, 120, 600, 470), T.BG_PANEL)
        draw_text(surf, "SEUS PILOTOS", f.tiny, T.ACCENT, (60, 132))
        self.my_btns = []
        y = 164
        for d in car.player_drivers():
            mv = driver_market_value(d, car.standings_drivers.get(d.id, 0))
            draw_text(surf, d.name, f.h2, T.TEXT, (60, y))
            contr = f"{d.contract_years} ano(s)" if d.contract_years > 0 else "EXPIRADO"
            draw_text(surf, f"OVR {d.overall:.0f}  ·  Valor € {mv:,}".replace(",", ".") + f"  ·  {contr}",
                      f.tiny, T.TEXT_DIM, (60, y + 32))
            rb = Button((360, y, 120, 38), "Renovar", (lambda x=d: self._renew(x)),
                        f.small, kind="ghost")
            lb = Button((490, y, 120, 38), "Liberar", (lambda x=d: self._release(x)),
                        f.small, kind="danger")
            self.my_btns += [rb, lb]; rb.draw(surf); lb.draw(surf)
            y += 80
        panel(surf, (660, 120, T.WIDTH - 660 - 40, 500), T.BG_PANEL)
        draw_text(surf, "AGENTES LIVRES", f.tiny, T.ACCENT, (680, 132))
        self.free_list.draw(surf, f)
        self.sign_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# EQUIPE E PILOTOS (info)
# ══════════════════════════════════════════════════════════════════════════════
class TeamInfoScene(SubScene):
    title = "Equipe & Pilotos"

    def body(self, surf):
        f = self.app.fonts
        t = self.app.career.player_team
        panel(surf, (40, 110, 560, 510), T.BG_PANEL)
        x = 64
        draw_text(surf, t.name, f.h1, T.TEXT, (x, 126))
        rows = [("Orçamento", f"€ {t.budget:,}".replace(",", ".")),
                ("Custo/corrida", f"€ {t.base_cost_per_race:,}".replace(",", ".")),
                ("Reputação", f"{t.reputation}/100"),
                ("Performance", f"{t.car_performance:.1f}/100")]
        y = 180
        for lab, val in rows:
            draw_text(surf, lab, f.body, T.TEXT_DIM, (x, y))
            draw_text(surf, val, f.body, T.TEXT, (x + 510, y), right=True)
            y += 38
        draw_text(surf, "PATROCINADORES", f.tiny, T.ACCENT, (x, y + 10))
        y += 40
        for s in t.sponsors:
            name = s["name"] if isinstance(s, dict) else s.name
            val  = s["value"] if isinstance(s, dict) else s.value
            draw_text(surf, name, f.small, T.TEXT, (x, y))
            draw_text(surf, f"€ {val:,}".replace(",", "."), f.small, T.GOLD, (x + 510, y), right=True)
            y += 30
        # pilotos
        panel(surf, (620, 110, T.WIDTH - 620 - 40, 510), T.BG_PANEL)
        draw_text(surf, "PILOTOS", f.tiny, T.ACCENT, (644, 126))
        y = 162
        for d in self.app.career.player_drivers():
            draw_text(surf, d.name, f.h2, T.TEXT, (644, y))
            tags = f"OVR {d.overall:.0f}  ·  Pot {d.potential}  ·  SL {d.super_licence_points}/40"
            draw_text(surf, tags, f.small, T.TEXT_DIM, (644, y + 30))
            extra = f"Saúde {d.health}%  ·  € {d.salary:,}".replace(",", ".") + f"  ·  {d.contract_years}a"
            if d.is_injured:
                extra += f"  ·  LESIONADO {d.injury_races_remaining}c"
            if d.academy_id:
                extra += f"  ·  {d.academy_id.split('_')[0].title()}"
            draw_text(surf, extra, f.tiny, T.TEXT_FAINT, (644, y + 56))
            y += 96


# ══════════════════════════════════════════════════════════════════════════════
# APOSENTAR → GERENTE
# ══════════════════════════════════════════════════════════════════════════════
class RetireScene(SubScene):
    title = "Aposentar e virar Chefe de Equipe"

    def setup(self):
        self.series = list(MANAGER_ENTRY_COST.keys())
        self.sel = 0
        self.rects = []
        self.confirm_btn = Button((T.WIDTH - 320, T.HEIGHT - 70, 280, 52),
                                  "CONFIRMAR APOSENTADORIA", self._confirm, self.app.fonts.body,
                                  color=T.GOLD)

    def _confirm(self):
        profile = self.app.profile
        target = self.series[self.sel]
        ok, msg = profile.retire_to_manager(target)
        if not ok:
            self.app.notify(msg); return
        # cria carreira de gerente
        teams = load_teams_for_series(target)
        pool = sorted(load_drivers_for_series(target), key=lambda d: -d.overall)
        career = ManagerCareer(profile)
        career.new_career(target, teams[0].id, pool[0].id, pool[1].id)
        self.app.career = career
        self.app.reset_to(CareerScene(self.app))

    def body_handle(self, event):
        self.confirm_btn.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in self.rects:
                if r.collidepoint(event.pos):
                    self.sel = i

    def body(self, surf):
        f = self.app.fonts
        p = self.app.profile
        draw_text(surf, f"Dinheiro pessoal: € {p.personal_money:,}".replace(",", "."),
                  f.h2, T.GOLD, (40, 110))
        draw_text(surf, "Escolha a categoria onde entrar como chefe (custo de entrada):",
                  f.body, T.TEXT_DIM, (40, 160))
        self.rects = []
        y = 210
        for i, sid in enumerate(self.series):
            cost = MANAGER_ENTRY_COST[sid]
            afford = p.personal_money >= cost
            r = pygame.Rect(40, y, 700, 56)
            seld = i == self.sel
            pygame.draw.rect(surf, T.BG_PANEL_2 if seld else T.BG_PANEL, r, border_radius=8)
            pygame.draw.rect(surf, T.ACCENT if seld else T.LINE, r, width=2, border_radius=8)
            draw_text(surf, SERIES_LABEL.get(sid, sid), f.h2, T.TEXT, (60, y + 14))
            draw_text(surf, f"€ {cost:,}".replace(",", "."), f.body,
                      T.GREEN if afford else T.RED, (720, y + 16), right=True)
            self.rects.append((i, r))
            y += 64
        self.confirm_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# VIRAR PILOTO (gerente → piloto)
# ══════════════════════════════════════════════════════════════════════════════
class BecomeDriverScene(SubScene):
    title = "Virar Piloto"
    subtitle = "Quase impossível para um gerente experiente"

    def setup(self):
        p = self.app.profile
        self.possible = [s for s, lim in DRIVER_AGE_GATE.items()
                         if lim != -1 and p.age <= lim]
        self.sel = 0
        self.rects = []
        self.confirm_btn = Button((T.WIDTH - 300, T.HEIGHT - 70, 260, 52),
                                  "TENTAR MESMO ASSIM", self._confirm, self.app.fonts.body,
                                  color=T.RED, text_color=T.TEXT)
        self.confirm_btn.enabled = bool(self.possible)

    def _confirm(self):
        if not self.possible:
            return
        profile = self.app.profile
        target = self.possible[self.sel]
        ok, msg, kwargs = profile.become_driver(target)
        if not ok:
            self.app.notify(msg); return
        teams = load_teams_for_series(target)
        worst = teams[-3:] if profile.age > 20 else teams
        career = DriverCareer(profile)
        career.new_career(target, worst[0].id, kwargs)
        self.app.career = career
        self.app.reset_to(CareerScene(self.app))

    def body_handle(self, event):
        self.confirm_btn.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in self.rects:
                if r.collidepoint(event.pos):
                    self.sel = i

    def body(self, surf):
        f = self.app.fonts
        p = self.app.profile
        draw_text(surf, f"Sua idade: {p.age} anos", f.h2, T.TEXT, (40, 110))
        draw_text(surf, "Seus atributos como piloto seriam medíocres — você nunca treinou.",
                  f.small, T.RED, (40, 152))
        # limites
        y = 200
        draw_text(surf, "LIMITES POR CATEGORIA", f.tiny, T.ACCENT, (40, y)); y += 30
        for sid, lim in DRIVER_AGE_GATE.items():
            txt = "BLOQUEADO" if lim == -1 else f"até {lim} anos"
            ok = lim != -1 and p.age <= lim
            draw_text(surf, SERIES_LABEL.get(sid, sid), f.body, T.TEXT, (60, y))
            draw_text(surf, txt, f.body, T.GREEN if ok else T.TEXT_FAINT, (320, y))
            y += 34
        self.rects = []
        if not self.possible:
            draw_text(surf, "Impossível virar piloto em qualquer categoria com sua idade.",
                      f.h2, T.RED, (40, y + 20))
        else:
            y += 16
            draw_text(surf, "ESCOLHA ONDE TENTAR:", f.tiny, T.ACCENT, (40, y)); y += 30
            for i, sid in enumerate(self.possible):
                r = pygame.Rect(40, y, 400, 50)
                seld = i == self.sel
                pygame.draw.rect(surf, T.BG_PANEL_2 if seld else T.BG_PANEL, r, border_radius=8)
                pygame.draw.rect(surf, T.RED if seld else T.LINE, r, width=2, border_radius=8)
                draw_text(surf, SERIES_LABEL.get(sid, sid), f.body, T.TEXT, (60, y + 14))
                self.rects.append((i, r))
                y += 58
        self.confirm_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# OFERTA (aceitar/recusar)
# ══════════════════════════════════════════════════════════════════════════════
class OfferScene(Scene):
    def __init__(self, app, offer):
        super().__init__(app)
        self.offer = offer

    def on_enter(self):
        f = self.app.fonts
        self.yes = Button((T.WIDTH // 2 - 230, 520, 200, 54), "ACEITAR", self._accept, f.h2,
                          color=T.GREEN, text_color=T.BG)
        self.no = Button((T.WIDTH // 2 + 30, 520, 200, 54), "RECUSAR", self._reject, f.h2,
                         kind="ghost")

    def _accept(self):
        self.app.career._pending_offer = self.offer
        self.app.notify(f"Proposta aceita: {self.offer['from_team']}")
        self.app.pop()

    def _reject(self):
        self.app.pop()

    def handle(self, event):
        self.yes.handle(event)
        self.no.handle(event)

    def update(self, dt): ...

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        o = self.offer
        label = OFFER_TYPE_LABEL.get(o["type"], "PROPOSTA")
        cx = T.WIDTH // 2
        panel(surf, (cx - 360, 130, 720, 360), T.BG_PANEL, border=T.ACCENT, border_w=2)
        draw_text(surf, label, f.h1, T.ACCENT, (cx, 160), center=True)
        draw_text(surf, o["description"], f.body, T.TEXT, (cx, 215), center=True)
        x = cx - 300
        rows = [("Equipe", o["from_team"]),
                ("Categoria", o["from_series_label"]),
                ("Chassi", f"{o.get('team_chassis','?')}/100"),
                ("Salário", f"€ {o['salary']:,}".replace(",", ".") + "/ano"),
                ("Contrato", f"{o['years']} ano(s)")]
        y = 265
        for lab, val in rows:
            draw_text(surf, lab, f.body, T.TEXT_DIM, (x, y))
            draw_text(surf, val, f.body, T.TEXT, (x + 600, y), right=True)
            y += 36
        if o.get("forced"):
            draw_text(surf, "ATENÇÃO: sua equipe está te dispensando.",
                      f.small, T.RED, (cx, 460), center=True)
        self.yes.draw(surf)
        self.no.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# CLT GAME OVER
# ══════════════════════════════════════════════════════════════════════════════
class CLTScene(Scene):
    def __init__(self, app, series_id):
        super().__init__(app)
        self.series_id = series_id

    def on_enter(self):
        f = self.app.fonts
        self.btn = Button((T.WIDTH // 2 - 120, T.HEIGHT - 90, 240, 52),
                          "VOLTAR AO MENU", lambda: self.app.reset_to(MenuScene(self.app)),
                          f.h2, kind="ghost")

    def handle(self, event):
        self.btn.handle(event)

    def update(self, dt): ...

    def draw(self, surf):
        surf.fill((20, 8, 10))
        f = self.app.fonts
        cx = T.WIDTH // 2
        draw_text(surf, "SITUAÇÃO CRÍTICA", f.title, T.RED, (cx, 160), center=True)
        draw_text(surf, "Você está fora do automobilismo.", f.h2, T.TEXT, (cx, 240), center=True)
        msg = CLT_MESSAGES.get(self.series_id, "Virou CLT do automobilismo.")
        panel(surf, (cx - 400, 300, 800, 120), T.BG_PANEL, border=T.RED, border_w=2)
        draw_text(surf, msg, f.body, T.GOLD, (cx, 360), center=True)
        # histórico
        y = 460
        draw_text(surf, "HISTÓRICO", f.tiny, T.TEXT_DIM, (cx, y), center=True)
        y += 26
        for h in self.app.profile.history[-6:]:
            draw_text(surf, f"{h.year}   {h.series}   P{h.position}", f.small, T.TEXT_DIM,
                      (cx, y), center=True)
            y += 24
        self.btn.draw(surf)
