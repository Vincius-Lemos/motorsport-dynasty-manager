"""
Cenas do Motorsport Dynasty Manager (pygame).

Fluxo:
  MenuScene → CreateScene → CareerScene
                                 ├─ RaceResultScene (overlay por corrida)
                                 └─ SeasonEndScene → CareerScene (nova temporada)
  MenuScene → LoadScene → CareerScene
"""
import random
from pathlib import Path
import pygame
from . import theme as T
from .app import Scene
from .widgets import (draw_text, panel, accent_strip, stat_bar, chip,
                      Button, TextInput, SelectList, draw_icon, draw_flag, soft_rect,
                      draw_country_flag)

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
from game import housing as hsng
from game.job_search import build_vacancy_list, apply_to_team
from game.i18n import t, set_language, LANG_NAMES, current_language

CLT_MSG_KEYS = {
    "formula_4":        "clt.formula_4",
    "formula_regional": "clt.formula_regional",
    "formula_3":        "clt.formula_3",
    "formula_2":        "clt.formula_2",
    "formula_1":        "clt.formula_1",
}

SERIES_LABEL = {
    "formula_4": "Fórmula 4", "formula_regional": "Fórmula Regional",
    "formula_3": "Fórmula 3", "formula_2": "Fórmula 2", "formula_1": "Fórmula 1",
}


_bg_surf = None
_asset_icon_cache = {}


def _build_bg(w, h):
    """Renderiza o fundo gradiente com linhas diagonais sutis — cacheado."""
    s = pygame.Surface((w, h))
    top = (18, 16, 28)
    bot = (8, 7, 14)
    for y in range(h):
        pygame.draw.line(s, T.lerp(top, bot, y / h), (0, y), (w, y))
    # linhas diagonais de velocidade muito sutis
    line_col = (23, 21, 36)
    for x0 in range(-h, w + h, 160):
        pygame.draw.line(s, line_col, (x0, 0), (x0 + h, h), 1)
    return s


def gradient_bg(surf):
    """Fundo gradiente cacheado — suave, sem bands."""
    global _bg_surf
    w, h = surf.get_width(), surf.get_height()
    if _bg_surf is None or _bg_surf.get_size() != (w, h):
        _bg_surf = _build_bg(w, h)
    surf.blit(_bg_surf, (0, 0))


def premium_bg(surf, t=0.0):
    """Fundo mais cinematografico para menus e hubs."""
    gradient_bg(surf)
    w, h = surf.get_size()
    haze = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(haze, (4, 7, 14, 178), (0, 0, w, 170))
    pygame.draw.rect(haze, (0, 0, 0, 175), (0, h - 155, w, 155))
    pygame.draw.polygon(haze, (34, 51, 82, 62),
                        [(0, 405), (w, 235), (w, 355), (0, 530)])
    pygame.draw.polygon(haze, (255, 137, 6, 30),
                        [(0, 548), (w, 470), (w, 555), (0, 632)])
    surf.blit(haze, (0, 0))

    # Rodape de pista bem discreto. Evita marcas repetidas/serrilhadas no menu.
    fh = 126
    scale = 2
    foot = pygame.Surface((w * scale, fh * scale), pygame.SRCALPHA)

    def pxy(x, y):
        return int(x * scale), int(y * scale)

    pygame.draw.polygon(foot, (5, 7, 12, 238),
                        [pxy(0, 42), pxy(w, 0), pxy(w, fh), pxy(0, fh)])
    pygame.draw.polygon(foot, (22, 24, 33, 210),
                        [pxy(0, 78), pxy(w, 38), pxy(w, fh), pxy(0, fh)])
    pygame.draw.line(foot, (*T.ACCENT, 180), pxy(0, 55), pxy(w, 18), 2 * scale)
    pygame.draw.line(foot, (235, 238, 245, 90), pxy(0, 86), pxy(w, 52), 1 * scale)
    pygame.draw.rect(foot, (0, 0, 0, 85), (0, 0, w * scale, fh * scale))
    surf.blit(pygame.transform.smoothscale(foot, (w, fh)), (0, h - fh))


def glass_panel(surf, rect, accent=T.ACCENT, alpha=210, radius=10):
    """Painel translucido com borda e brilho discreto."""
    rect = pygame.Rect(rect)
    sh = pygame.Surface((rect.w + 14, rect.h + 14), pygame.SRCALPHA)
    soft_rect(sh, sh.get_rect(), (0, 0, 0, 90), radius=radius + 4)
    surf.blit(sh, (rect.x - 7, rect.y - 5))
    body = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    soft_rect(body, body.get_rect(), (*T.BG_PANEL, alpha), radius=radius)
    pygame.draw.line(body, (*T.lerp(T.BG_PANEL, (255, 255, 255), 0.16), 90),
                     (radius, 1), (rect.w - radius, 1), 1)
    surf.blit(body, rect.topleft)
    soft_rect(surf, rect, T.LINE, radius=radius, width=1)
    soft_rect(surf, (rect.x, rect.y, 5, rect.h), accent, radius=min(radius, 5))
    return rect


def draw_wrapped_text(surf, text, font, color, pos, max_width, line_gap=3, max_lines=3):
    words = str(text).split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if font.size(trial)[0] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    for i, line in enumerate(lines[:max_lines]):
        draw_text(surf, line, font, color,
                  (pos[0], pos[1] + i * (font.get_height() + line_gap)))


def draw_menu_card_art(surf, rect, accent, variant, t=0.0):
    """Supersampled card art: no cheap central icon, just racing atmosphere."""
    rect = pygame.Rect(rect)
    scale = 3
    w, h = rect.w * scale, rect.h * scale
    art = pygame.Surface((w, h), pygame.SRCALPHA)

    top = T.lerp(accent, (8, 10, 18), 0.64)
    bot = T.lerp(accent, (18, 20, 30), 0.82)
    for y in range(h):
        pygame.draw.line(art, T.lerp(top, bot, y / max(1, h - 1)), (0, y), (w, y))

    def pts(seq):
        return [(int(x * scale), int(y * scale)) for x, y in seq]

    # Broad track/light sweep, shared by all cards.
    pygame.draw.polygon(art, (*T.lerp(accent, (245, 245, 250), 0.34), 150),
                        pts([(0, h / scale * 0.78), (rect.w, h / scale * 0.30),
                             (rect.w, rect.h), (0, rect.h)]))
    pygame.draw.polygon(art, (7, 8, 13, 120),
                        pts([(0, rect.h * 0.82), (rect.w, rect.h * 0.55),
                             (rect.w, rect.h), (0, rect.h)]))

    if variant == "driver":
        # Fast racing line and a low cockpit silhouette.
        for off in (-34, 24, 82):
            pygame.draw.aaline(art, (*accent, 210),
                               (int((off) * scale), int(rect.h * 0.80 * scale)),
                               (int((off + 92) * scale), int(rect.h * 0.18 * scale)))
        pygame.draw.ellipse(art, (4, 5, 9, 210),
                            pygame.Rect(70 * scale, 47 * scale, 100 * scale, 34 * scale))
        pygame.draw.arc(art, (235, 238, 245, 230),
                        pygame.Rect(79 * scale, 35 * scale, 82 * scale, 56 * scale),
                        3.18, 6.25, 3 * scale)
        pygame.draw.line(art, (235, 238, 245, 210),
                         (88 * scale, 65 * scale), (154 * scale, 65 * scale), 2 * scale)
    elif variant == "team":
        # Garage bay lights and two cars under covers.
        for x in (26, 82, 138, 194):
            pygame.draw.rect(art, (230, 238, 250, 42),
                             pygame.Rect(x * scale, 13 * scale, 32 * scale, 8 * scale),
                             border_radius=2 * scale)
        for x in (48, 132):
            pygame.draw.ellipse(art, (5, 6, 11, 220),
                                pygame.Rect(x * scale, 58 * scale, 62 * scale, 22 * scale))
            pygame.draw.circle(art, (230, 238, 245, 210),
                               (int((x + 12) * scale), int(76 * scale)), 5 * scale, 2 * scale)
            pygame.draw.circle(art, (230, 238, 245, 210),
                               (int((x + 49) * scale), int(76 * scale)), 5 * scale, 2 * scale)
        pygame.draw.line(art, (*accent, 190), (0, 94 * scale), (w, 76 * scale), 2 * scale)
    elif variant == "load":
        # Pit lane/garage shutter, more serious than a floppy icon.
        for y in range(18, 74, 12):
            pygame.draw.line(art, (240, 244, 250, 58),
                             (22 * scale, y * scale), (210 * scale, y * scale), 1 * scale)
        pygame.draw.polygon(art, (6, 7, 12, 200),
                            pts([(30, 82), (210, 50), (226, 74), (58, 98)]))
        pygame.draw.line(art, (*accent, 230), (34 * scale, 84 * scale),
                         (218 * scale, 53 * scale), 3 * scale)
        for x in (54, 92, 130, 168):
            pygame.draw.rect(art, (245, 248, 255, 50),
                             pygame.Rect(x * scale, 34 * scale, 18 * scale, 26 * scale))
    else:
        # Setup telemetry board: clean, abstract, not a low-res gear/star.
        for y in (24, 44, 64, 84):
            pygame.draw.line(art, (235, 240, 248, 64),
                             (28 * scale, y * scale), (206 * scale, y * scale), 1 * scale)
        for i, x in enumerate((44, 88, 132, 176)):
            col = accent if i % 2 else (235, 240, 248)
            pygame.draw.circle(art, (*col, 215),
                               (x * scale, (44 + (i % 2) * 20) * scale), 5 * scale)
            pygame.draw.line(art, (*col, 120),
                             (x * scale, 24 * scale), (x * scale, 88 * scale), 1 * scale)

    # Subtle vignette and crisp polished border.
    pygame.draw.rect(art, (255, 255, 255, 70), art.get_rect(), width=scale,
                     border_radius=5 * scale)
    pygame.draw.rect(art, (0, 0, 0, 95), art.get_rect(), width=2 * scale,
                     border_radius=5 * scale)
    surf.blit(pygame.transform.smoothscale(art, rect.size), rect.topleft)


def _placeholder_icon(name, size):
    """Ícone vetorial de reserva quando o SVG em assets/icons não existe."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    palette = {"driver": T.ACCENT, "helmet": T.ACCENT, "manager": T.ACCENT_2,
               "team": T.ACCENT_2, "load": T.GOLD, "save": T.GOLD}
    col = palette.get(name, T.ACCENT)
    pygame.draw.circle(surf, (*col, 60), (size // 2, size // 2), size // 2)
    pygame.draw.circle(surf, col, (size // 2, size // 2), size // 2, max(2, size // 18))
    try:
        font = pygame.font.SysFont("arial", int(size * 0.5), bold=True)
        img = font.render((name[:1].upper() if name else "?"), True, col)
        surf.blit(img, img.get_rect(center=(size // 2, size // 2)))
    except Exception:
        pass
    return surf


def draw_downloaded_icon(surf, name, center, size=58, alpha=235):
    """Draws downloaded SVG icon assets from assets/icons (com fallback vetorial)."""
    key = (name, size)
    if key not in _asset_icon_cache:
        path = Path(__file__).resolve().parents[1] / "assets" / "icons" / f"{name}.svg"
        try:
            img = pygame.image.load(str(path)).convert_alpha()
            _asset_icon_cache[key] = pygame.transform.smoothscale(img, (size, size))
        except Exception:
            _asset_icon_cache[key] = _placeholder_icon(name, size)
    img = _asset_icon_cache[key]
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    rect = img.get_rect(center=center)
    surf.blit(img, rect)


def header(surf, app, subtitle=""):
    """Cabeçalho polido com bloco de marca e painel HUD para o perfil."""
    W = T.WIDTH
    # fundo do header
    pygame.draw.rect(surf, T.BG_PANEL, (0, 0, W, 72))
    # faixa lateral laranja
    pygame.draw.rect(surf, T.ACCENT, (0, 0, 6, 72))
    # linha inferior laranja
    pygame.draw.rect(surf, T.ACCENT, (0, 72, W, 2))
    # highlight interno no topo do painel
    hi = T.lerp(T.BG_PANEL, (255, 255, 255), 0.06)
    pygame.draw.line(surf, hi, (0, 1), (W, 1), 1)

    # logotipo
    draw_text(surf, "MOTORSPORT", app.fonts.h2, T.ACCENT, (22, 8))
    draw_text(surf, "DYNASTY", app.fonts.h2, T.TEXT, (22, 36))

    # subtítulo centrado
    if subtitle:
        draw_text(surf, subtitle, app.fonts.body, T.TEXT_DIM, (W // 2, 28), center=True)

    # perfil no lado direito (caixinha HUD)
    p = app.profile
    if p:
        money = f"€ {p.personal_money:,}".replace(",", ".")
        info  = f"{p.name}  ·  {p.age}a  ·  Rep {p.reputation}"
        iw = max(app.fonts.small.size(info)[0], app.fonts.body.size(money)[0])
        bw = iw + 28
        bx = W - bw - 12
        pygame.draw.rect(surf, T.BG_PANEL_2, (bx, 8, bw, 58), border_radius=6)
        pygame.draw.rect(surf, T.LINE, (bx, 8, bw, 58), width=1, border_radius=6)
        draw_text(surf, info,  app.fonts.small, T.TEXT, (W - 26, 14), right=True)
        draw_text(surf, money, app.fonts.body,  T.GOLD, (W - 26, 38), right=True)


# ══════════════════════════════════════════════════════════════════════════════
# MENU
# ══════════════════════════════════════════════════════════════════════════════
class MenuScene(Scene):
    def on_enter(self):
        self._rebuild()

    def _rebuild(self):
        f = self.app.fonts
        w, h, gap = 248, 238, 18
        x0, y0 = 104, 314
        self.menu_cards = [
            {"rect": pygame.Rect(x0, y0, w, h), "title": t("menu.new_driver"),
             "eyebrow": "CAREER", "desc": "Suba das bases ate o topo do automobilismo.",
             "asset": "driver", "color": T.ACCENT, "cb": lambda: self._new("driver")},
            {"rect": pygame.Rect(x0 + (w + gap), y0, w, h), "title": t("menu.new_manager"),
             "eyebrow": "TEAM", "desc": "Gerencie orcamento, pilotos e desenvolvimento.",
             "asset": "team", "color": T.ACCENT_2, "cb": lambda: self._new("manager")},
            {"rect": pygame.Rect(x0 + 2 * (w + gap), y0, w, h), "title": t("menu.load"),
             "eyebrow": "SAVE", "desc": "Continue a temporada salva na garagem.",
             "asset": "load", "color": T.GOLD, "cb": lambda: self.app.push(LoadScene(self.app))},
            {"rect": pygame.Rect(x0 + 3 * (w + gap), y0, w, h), "title": "OPÇÕES",
             "eyebrow": "SETUP", "desc": "Idioma, resolucao e tela cheia.",
             "asset": "options", "color": T.PURPLE, "cb": lambda: self.app.push(OptionsScene(self.app))},
        ]
        self.buttons = [
            Button((T.WIDTH - 178, 24, 130, 38), t("menu.quit"),
                   self._quit, f.small, kind="ghost"),
        ]
        self._t = 0
        self._lang_rects = []
        self._card_hover = -1

    def _new(self, mode):
        self.app.mode = mode
        self.app.push(CreateScene(self.app, mode))

    def _quit(self):
        self.app.running = False

    def handle(self, event):
        for b in self.buttons:
            b.handle(event)
        if event.type == pygame.MOUSEMOTION:
            self._card_hover = -1
            for i, card in enumerate(getattr(self, "menu_cards", [])):
                if card["rect"].collidepoint(event.pos):
                    self._card_hover = i
                    break
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for card in getattr(self, "menu_cards", []):
                if card["rect"].collidepoint(event.pos) and card["cb"]:
                    card["cb"]()
                    return

    def update(self, dt):
        self._t += dt

    def draw(self, surf):
        premium_bg(surf, self._t)
        f = self.app.fonts

        # Barra superior no estilo hub.
        pygame.draw.rect(surf, (8, 11, 20), (0, 0, T.WIDTH, 76))
        soft_rect(surf, (0, 0, 5, 76), T.ACCENT, radius=2)
        pygame.draw.line(surf, T.LINE, (0, 76), (T.WIDTH, 76), 1)
        draw_text(surf, "MOTORSPORT", f.h2, T.ACCENT, (24, 14))
        draw_text(surf, "DYNASTY MANAGER", f.small, T.TEXT, (24, 42))
        draw_text(surf, "GARAGEM", f.tiny, T.TEXT_DIM, (245, 30))
        draw_text(surf, "CARREIRA", f.tiny, T.ACCENT, (330, 30))
        draw_text(surf, "PADDOCK", f.tiny, T.TEXT_DIM, (430, 30))

        draw_text(surf, "MOTORSPORT", f.title, (0, 0, 0), (64, 128))
        draw_text(surf, "MOTORSPORT", f.title, T.ACCENT, (60, 124))
        draw_text(surf, "DYNASTY MANAGER", f.h1, T.TEXT, (62, 186))
        draw_text(surf, t("menu.tagline"), f.small, T.TEXT_DIM, (64, 232))
        pygame.draw.rect(surf, T.ACCENT, (64, 270, 86, 3), border_radius=2)
        pygame.draw.rect(surf, T.LINE, (158, 270, 240, 1))

        # Cards principais.
        for i, card in enumerate(self.menu_cards):
            r = card["rect"]
            hover = i == self._card_hover
            rr = r.move(0, -6 if hover else 0)
            col = card["color"]
            glass_panel(surf, rr, col, alpha=226 if hover else 205, radius=7)

            hero = pygame.Rect(rr.x + 8, rr.y + 8, rr.w - 16, 104)
            soft_rect(surf, hero, T.lerp(col, (8, 10, 18), 0.72), radius=5)
            pygame.draw.polygon(surf, T.lerp(col, (245, 247, 252), 0.18),
                                [(hero.x, hero.bottom - 22), (hero.right, hero.y + 28),
                                 (hero.right, hero.bottom), (hero.x, hero.bottom)])
            soft_rect(surf, hero, T.lerp(col, (255, 255, 255), 0.34), radius=5, width=1)
            glow = pygame.Surface((104, 104), pygame.SRCALPHA)
            soft_rect(glow, glow.get_rect(), (*col, 54 if hover else 34), radius=45)
            surf.blit(glow, (hero.centerx - 52, hero.centery - 52))
            draw_downloaded_icon(surf, card["asset"], hero.center, 72 if hover else 66)

            chip(surf, card["eyebrow"], (rr.x + 18, rr.y + 128), f.tiny, T.BG, col)
            draw_text(surf, card["title"].upper(), f.body, T.TEXT, (rr.x + 18, rr.y + 160))
            draw_wrapped_text(surf, card["desc"], f.tiny, T.TEXT_DIM,
                              (rr.x + 18, rr.y + 190), rr.w - 36, max_lines=1)
            soft_rect(surf, (rr.x + 18, rr.bottom - 14, rr.w - 36, 3), T.BG_INPUT, radius=2)
            soft_rect(surf, (rr.x + 18, rr.bottom - 14,
                             int((rr.w - 36) * (1.0 if hover else 0.82)), 3),
                      col, radius=2)

        for b in self.buttons:
            b.draw(surf)

        draw_text(surf, t("menu.version"), f.tiny, T.TEXT_FAINT,
                  (T.WIDTH - 16, T.HEIGHT - 16), right=True)


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
        self.name_in = TextInput((460, 200, 360, 46), f.body, t("create.name_ph"))
        self.age_in  = TextInput((460, 290, 120, 46), f.body,
                                 t("create.age_ph_driver") if self.mode == "driver" else t("create.age_ph_manager"),
                                 max_len=2, numeric=True)
        self.nat_in  = TextInput((460, 380, 280, 46), f.body, t("create.nat_ph"))
        self.next_btn = Button((T.WIDTH - 240, T.HEIGHT - 80, 200, 52),
                               t("common.continue"), self._continue, f.h2)
        self.back_btn = Button((40, T.HEIGHT - 80, 160, 52),
                               t("common.back"), self._back, f.body, kind="ghost")
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
                self.app.notify(t("create.no_name"))
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
        draw_text(surf, t("create.car_perf", perf=f"{perf:.0f}"), fonts.small, T.ACCENT_2,
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
        premium_bg(surf, self.app.anim_t)
        role = "PILOTO" if self.mode == "driver" else "GERENTE"
        header(surf, self.app, f"Nova carreira · {role}")
        f = self.app.fonts
        if self.step == 0:
            draw_text(surf, t("nav.profile"), f.h1, T.TEXT, (440, 130))
            draw_text(surf, "NOME", f.small, T.TEXT_DIM, (460, 175))
            self.name_in.draw(surf)
            draw_text(surf, "IDADE", f.small, T.TEXT_DIM, (460, 265))
            self.age_in.draw(surf)
            draw_text(surf, t("create.nat_ph"), f.small, T.TEXT_DIM, (460, 355))
            self.nat_in.draw(surf)
            draw_text(surf, "SÉRIE", f.small, T.TEXT_DIM, (460, 460))
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
        else:
            draw_text(surf, t("create.choose_team", series=SERIES_LABEL[self.series_id]),
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
            items = [(t("nav.profile"),  "helmet",   lambda: self.app.push(PerfilScene(self.app))),
                     (t("nav.ranking"),  "chart",    lambda: self.app.push(StandingsScene(self.app))),
                     (t("nav.sl"),       "star",     lambda: self.app.push(SuperLicenceScene(self.app))),
                     (t("nav.academy"),  "cap",      lambda: self.app.push(AcademyScene(self.app))),
                     (t("nav.vacancies"),"transfer", lambda: self.app.push(JobSearchScene(self.app))),
                     (t("nav.negotiate"),"transfer", lambda: self.app.push(NegociarEquipeScene(self.app))),
                     (t("nav.housing"),  "home",     lambda: self.app.push(HousingScene(self.app))),
                     (t("nav.news"),     "star",     lambda: self.app.push(NewsScene(self.app))),
                     (t("nav.retire"),   "door",     lambda: self.app.push(RetireScene(self.app)))]
        else:
            items = [(t("nav.profile"),       "helmet",   lambda: self.app.push(PerfilScene(self.app))),
                     (t("nav.development"),   "dev",      lambda: self.app.push(DevelopmentScene(self.app))),
                     (t("nav.transfers"),     "transfer", lambda: self.app.push(TransferScene(self.app))),
                     (t("nav.team_info"),     "team",     lambda: self.app.push(TeamInfoScene(self.app))),
                     (t("nav.ranking"),       "chart",    lambda: self.app.push(StandingsScene(self.app))),
                     (t("nav.news"),          "star",     lambda: self.app.push(NewsScene(self.app))),
                     (t("nav.become_driver"), "helmet",   lambda: self.app.push(BecomeDriverScene(self.app)))]
        pad = 52 if self.mode == "driver" else 64
        for label, icon, cb in items:
            w = sf.size(label)[0] + pad
            self.nav.append(Button((x, sy, w, 40), label, cb, sf, kind="ghost", icon=icon))
            x += w + 8
        # ── linha primária (ações) ────────────────────────────────────────────
        by = T.HEIGHT - 70
        self.run_btn  = Button((28, by, 250, 52), t("career.run_next"), self._race, f.h2, icon="play")
        self.end_btn  = Button((28, by, 320, 52), t("career.end_season"), self._end_season, f.h2,
                               color=T.GOLD)
        self.save_btn = Button((T.WIDTH - 360, by, 160, 52), t("common.save"), self._save,
                               f.body, kind="ghost", icon="save")
        self.menu_btn = Button((T.WIDTH - 188, by, 160, 52), t("common.menu"), self._menu,
                               f.body, kind="ghost", icon="menu")

    def _menu(self):
        self.app.reset_to(MenuScene(self.app))

    def _save(self):
        try:
            save_load.save_game(self.app.profile, self.app.career, "save1")
            self.app.notify(t("save.ok"))
        except Exception as e:
            self.app.notify(t("save.error", error=e))

    def _race(self):
        car = self.app.career
        if car.season_complete():
            return
        # FP1 raríssimo (academia) no início do fim de semana — com tela
        if self.app.profile.mode != "manager" and hasattr(car, "run_fp1_session"):
            fp1 = car.run_fp1_session()
            if fp1:
                self.app.push(FP1ResultScene(self.app, fp1))
                return
        self.app.push(QualifyingScene(self.app))

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
        premium_bg(surf, self.app.anim_t)
        car = self.app.career
        header(surf, self.app,
                t("career.header",
                  series=SERIES_LABEL.get(car.current_series_id, ""),
                  season=car.season_number,
                  year=car.career_year))
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
            draw_text(surf, t("career.player_error"),
                      f.h2, T.RED, (440, 300))
            return
        col = T.SERIES_COLOR.get(car.current_series_id, T.ACCENT)

        # Card do piloto (esquerda)
        glass_panel(surf, (28, 84, 380, 500), col, alpha=220, radius=10)
        pygame.draw.circle(surf, T.lerp(col, T.BG_PANEL, 0.55), (88, 142), 34)
        pygame.draw.circle(surf, col, (88, 142), 34, 2)
        draw_icon(surf, "helmet", 88, 142, 34, T.TEXT)
        draw_text(surf, d.name, f.h1, T.TEXT, (132, 100))
        team_name = car.current_team.name if car.current_team else "Sem equipe"
        draw_text(surf, team_name, f.body, T.TEXT_DIM, (132, 140))
        chip(surf, SERIES_LABEL.get(car.current_series_id, ""), (132, 172), f.tiny, T.BG, col)

        # Overall grande
        soft_rect(surf, (292, 112, 82, 78), T.BG_INPUT, radius=8)
        soft_rect(surf, (292, 112, 82, 78), col, radius=8, width=1)
        draw_text(surf, "OVR", f.tiny, T.TEXT_DIM, (333, 122), center=True)
        draw_text(surf, f"{d.overall:.0f}", f.big_num, col, (333, 158), center=True)

        # Barras de atributos
        x, y, w = 54, 230, 320
        rv = self.reveal
        for label, val in [(t("career.stat_speed"), d.speed),
                           (t("career.stat_consistency"), d.consistency),
                           (t("career.stat_overtaking"), d.overtaking),
                           (t("career.stat_tyre"), d.tyre_mgmt),
                           (t("career.stat_defence"), d.defence),
                           (t("career.stat_rain"), d.rain)]:
            y = stat_bar(surf, x, y, w, label, val, color=col, fonts=f, anim=rv) + 14

        # Super Licença
        y += 6
        draw_text(surf, t("career.super_licence"), f.tiny, T.TEXT_DIM, (x, y))
        draw_text(surf, f"{d.super_licence_points}/40", f.small, T.GOLD, (x + w, y - 2), right=True)
        pygame.draw.rect(surf, T.BG_INPUT, (x, y + 18, w, 7), border_radius=4)
        frac = min(1.0, d.super_licence_points / 40) * rv
        if frac > 0.002:
            pygame.draw.rect(surf, T.GOLD, (x, y + 18, max(4, int(w * frac)), 7), border_radius=4)

        # Saúde
        y += 38
        hcol = T.GREEN if d.health > 70 else (T.GOLD if d.health > 40 else T.RED)
        draw_text(surf, t("career.health"), f.tiny, T.TEXT_DIM, (x, y))
        inj_suffix = "  " + t("career.injured") if d.is_injured else ""
        draw_text(surf, f"{d.health}%{inj_suffix}", f.small, hcol, (x + w, y - 2), right=True)
        pygame.draw.rect(surf, T.BG_INPUT, (x, y + 18, w, 7), border_radius=4)
        if rv > 0.002:
            pygame.draw.rect(surf, hcol, (x, y + 18, max(4, int(w * d.health / 100 * rv)), 7),
                             border_radius=4)

        # XP / Experiência
        y += 38
        xp = d.experience
        next_thresh = ((xp // 120) + 1) * 120
        xp_frac = (xp % 120) / 120.0
        draw_text(surf, t("career.experience"), f.tiny, T.TEXT_DIM, (x, y))
        draw_text(surf, f"{xp} XP", f.small, T.ACCENT_2, (x + w, y - 2), right=True)
        pygame.draw.rect(surf, T.BG_INPUT, (x, y + 18, w, 7), border_radius=4)
        if rv > 0.002 and xp_frac > 0:
            pygame.draw.rect(surf, T.ACCENT_2, (x, y + 18, max(4, int(w * xp_frac * rv)), 7), border_radius=4)
        draw_text(surf, t("career.next_level", xp=next_thresh), f.tiny, T.TEXT_FAINT, (x, y + 28))

        self._draw_next_round(surf, 430, 84)
        self._draw_standings(surf, 430, 250, car.driver_standings(),
                             highlight=d.id, kind="driver")

    # ── painel gerente ────────────────────────────────────────────────────────
    def _draw_manager(self, surf):
        f = self.app.fonts
        car = self.app.career
        tm = car.player_team
        if tm is None:
            draw_text(surf, t("career.team_error"),
                      f.h2, T.RED, (440, 300))
            return
        col = T.SERIES_COLOR.get(car.current_series_id, T.ACCENT)

        glass_panel(surf, (28, 84, 380, 500), col, alpha=220, radius=10)
        pygame.draw.circle(surf, T.lerp(col, T.BG_PANEL, 0.55), (88, 142), 34)
        pygame.draw.circle(surf, col, (88, 142), 34, 2)
        draw_icon(surf, "team", 88, 142, 34, T.TEXT)
        draw_text(surf, tm.name, f.h1, T.TEXT, (132, 100))
        chip(surf, SERIES_LABEL.get(car.current_series_id, ""), (132, 150), f.tiny, T.BG, col)
        bud = f"€ {tm.budget:,}".replace(",", ".")
        soft_rect(surf, (54, 188, 320, 58), T.BG_INPUT, radius=8)
        soft_rect(surf, (54, 188, 320, 58), T.LINE, radius=8, width=1)
        draw_text(surf, t("career.budget"), f.tiny, T.TEXT_DIM, (70, 198))
        draw_text(surf, bud, f.h2, T.GOLD, (70, 216))

        # Car stats
        x, y, w = 54, 260, 320
        for label, val in [(t("career.car_chassis"), tm.chassis),
                           (t("career.car_aero"), tm.aerodynamics),
                           (t("career.car_reliability"), tm.reliability),
                           (t("career.car_engine"), tm.engineers)]:
            y = stat_bar(surf, x, y, w, label, val, color=col, fonts=f, anim=self.reveal) + 12

        # Facilities
        y += 8
        draw_text(surf, t("career.facilities"), f.tiny, T.TEXT_DIM, (x, y))
        y += 22
        facs = [(t("career.fac_factory"), tm.fac_factory),
                (t("career.fac_sim"), tm.fac_simulator),
                (t("career.fac_rd"), tm.fac_r_and_d),
                (t("career.fac_pit"), tm.fac_pit_crew),
                ("Mkt", tm.fac_marketing)]
        fx = x
        for name, lvl in facs:
            box = pygame.Rect(fx, y, 58, 44)
            soft_rect(surf, box, T.BG_PANEL_2, radius=6)
            draw_text(surf, name, f.tiny, T.TEXT_DIM, (box.centerx, box.y + 5), center=True)
            px = box.centerx - 5 * 4 + 2
            for k in range(5):
                c = T.GOLD if k < lvl else T.LINE
                pygame.draw.circle(surf, c, (px + k * 9, box.y + 30), 3)
            fx += 64

        # Contracted drivers
        y += 56
        draw_text(surf, t("career.drivers_list"), f.tiny, T.TEXT_DIM, (x, y))
        y += 22
        for d in car.player_drivers():
            draw_text(surf, f"{d.name}", f.small, T.TEXT, (x, y))
            draw_text(surf, f"OVR {d.overall:.0f}", f.tiny, T.ACCENT_2, (x + w, y), right=True)
            y += 26

        self._draw_next_round(surf, 430, 84)
        self._draw_standings(surf, 430, 250, car.team_standings(),
                             highlight=tm.id, kind="team")

    # ── próxima corrida ───────────────────────────────────────────────────────
    def _draw_next_round(self, surf, x, y):
        f = self.app.fonts
        car = self.app.career
        rnd = car.current_round()
        total = len(car.season.rounds) if car.season else 0
        done = car.season.current_round if car.season else 0
        col = T.SERIES_COLOR.get(car.current_series_id, T.ACCENT)
        glass_panel(surf, (x, y, T.WIDTH - x - 28, 150), col, alpha=214, radius=10)
        pygame.draw.polygon(surf, T.lerp(col, T.BG_PANEL, 0.78),
                            [(T.WIDTH - 320, y), (T.WIDTH - 28, y),
                             (T.WIDTH - 28, y + 150), (T.WIDTH - 430, y + 150)])
        if rnd:
            draw_text(surf, t("career.next_race"), f.tiny, T.ACCENT, (x + 20, y + 16))
            name_rect = draw_text(surf, rnd.track_name, f.h1, T.TEXT, (x + 20, y + 36))
            draw_country_flag(surf, name_rect.right + 18, name_rect.centery - 11, rnd.country)
            draw_text(surf, f"{rnd.country}  ·  " + t("career.laps", n=rnd.laps) + f"  ·  {rnd.track_type}",
                      f.small, T.TEXT_DIM, (x + 20, y + 84))
        else:
            draw_text(surf, t("career.season_complete"), f.tiny, T.GOLD, (x + 20, y + 16))
            draw_text(surf, t("career.all_races_done"), f.h2, T.TEXT, (x + 20, y + 40))
            draw_text(surf, t("career.click_end"), f.small, T.TEXT_DIM, (x + 20, y + 84))
        draw_text(surf, t("career.round", done=min(done+1, total), total=total), f.small, T.TEXT,
                  (T.WIDTH - 44, y + 16), right=True)
        bx, bw = x + 20, T.WIDTH - x - 28 - 40
        pygame.draw.rect(surf, T.BG_INPUT, (bx, y + 122, bw, 8), border_radius=4)
        if total:
            pygame.draw.rect(surf, col, (bx, y + 122, int(bw * done / total), 8),
                             border_radius=4)

    # ── tabela de classificação ───────────────────────────────────────────────
    def _draw_standings(self, surf, x, y, standings, highlight, kind):
        f = self.app.fonts
        w = T.WIDTH - x - 28
        glass_panel(surf, (x, y, w, 334), T.ACCENT, alpha=214, radius=10)
        title = t("career.standings_drivers") if kind == "driver" else t("career.standings_teams")
        draw_text(surf, title, f.tiny, T.ACCENT, (x + 20, y + 14))
        ry = y + 44
        for pos, obj, pts in standings[:8]:
            is_me = obj.id == highlight
            row = pygame.Rect(x + 12, ry - 4, w - 24, 32)
            if is_me:
                soft_rect(surf, row, T.BG_PANEL_2, radius=6)
                soft_rect(surf, row, T.ACCENT, radius=6, width=1)
            pcol = T.GOLD if pos == 1 else (T.TEXT if is_me else T.TEXT_DIM)
            draw_text(surf, f"P{pos}", f.small, pcol, (x + 24, ry))
            name = obj.name
            draw_text(surf, name, f.body if is_me else f.small,
                      T.TEXT if is_me else T.TEXT_DIM, (x + 78, ry - 1))
            draw_text(surf, f"{pts} pts", f.small, pcol, (x + w - 24, ry), right=True)
            ry += 36


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO (qualifying)
# ══════════════════════════════════════════════════════════════════════════════
SEG_COLOR = {"Q3": T.PURPLE, "Q2": T.ACCENT_2, "Q1": T.TEXT_DIM, "Q": T.TEXT_DIM}


class FP1ResultScene(Scene):
    """Resultado da sessão de FP1 (treino livre 1)."""
    def __init__(self, app, fp1):
        super().__init__(app)
        self.fp1 = fp1

    def on_enter(self):
        f = self.app.fonts
        self.go = Button((T.WIDTH // 2 - 150, T.HEIGHT - 70, 300, 52),
                         "IR PARA A CLASSIFICAÇÃO", self._go, f.h2, icon="play")

    def _go(self):
        self.app.replace(QualifyingScene(self.app))

    def update(self, dt): ...

    def handle(self, event):
        self.go.handle(event)

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        fp = self.fp1
        cx = T.WIDTH // 2
        draw_text(surf, "TREINO LIVRE 1 (FP1)", f.h1, T.ACCENT, (cx, 50), center=True)
        draw_text(surf, f"{fp['track']} · {fp['team']}", f.body, T.TEXT_DIM, (cx, 100), center=True)

        panel(surf, (cx - 380, 150, 760, 360), T.BG_PANEL, border=T.ACCENT_2, border_w=2)
        x = cx - 340
        # resultado / desfecho
        outcome_txt = {
            "crash":  ("VOCÊ BATEU O CARRO", T.RED),
            "mech":   ("QUEBRA MECÂNICA", T.RED),
            "stuck":  ("PRESO NO BOX (carro não saiu)", T.RED),
            "ok":     ("IMPRESSIONOU!" if fp["impressed"] else "SESSÃO CONCLUÍDA",
                       T.GREEN if fp["impressed"] else T.TEXT),
        }[fp["outcome"]]
        draw_text(surf, outcome_txt[0], f.h2, outcome_txt[1], (x, 172))

        rows = []
        if fp["outcome"] not in ("stuck",):
            mins = int(fp["time"] // 60); secs = fp["time"] - mins * 60
            rows.append(("Seu melhor tempo", f"{mins}:{secs:06.3f}", T.TEXT))
            rows.append(("Posição na sessão", f"P{fp['pos']} de {fp['field']}",
                         T.GOLD if fp["pos"] <= 5 else T.TEXT))
            gap = fp["gap"]
            gtxt = ("+%.3f mais lento" % gap) if gap > 0 else ("%.3f mais rápido" % gap)
            rows.append((f"Vs. titular ({fp['titular']})", gtxt,
                         T.GREEN if gap <= 0 else T.RED))
        rows.append(("Voltas completadas", str(fp["laps"]), T.TEXT))
        rows.append(("Pontos de Super Licença", f"+{fp['sl_pts']}",
                     T.GOLD if fp["sl_pts"] else T.TEXT_DIM))
        y = 224
        for lab, val, col in rows:
            draw_text(surf, lab, f.body, T.TEXT_DIM, (x, y))
            draw_text(surf, val, f.body, col, (x + 680, y), right=True)
            y += 46

        self.go.draw(surf)


class QualifyingScene(Scene):
    def on_enter(self):
        f = self.app.fonts
        car = self.app.career
        is_wet = random.random() < 0.15
        self.quali = car.run_qualifying(is_wet=is_wet)
        self.is_wet = is_wet
        self.my_id = (car.player_driver.id if self.app.profile.mode == "driver" else None)
        self.my_team = (car.player_team.id if self.app.profile.mode != "driver" else None)
        self.scroll = 0
        self.t = 0.0
        rows = self.quali["rows"] if self.quali else []
        self.visible = (_RT_H - _RT_HEAD - 6) // _RT_ROW
        self.max_scroll = max(0, len(rows) - self.visible)
        idx = next((i for i, r in enumerate(rows)
                    if r["driver_id"] == self.my_id or
                    (self.my_team and self._is_my_team(r))), 0)
        self.scroll = max(0, min(self.max_scroll, idx - self.visible // 2))
        self.go_btn = Button((T.WIDTH // 2 - 150, T.HEIGHT - 64, 300, 50),
                             t("qualifying.go_race"), self._to_race, f.h2, icon="play")

    def _is_my_team(self, row):
        car = self.app.career
        d = next((x for x in car.all_drivers if x.id == row["driver_id"]), None)
        return d is not None and d.team_id == self.my_team

    def _to_race(self):
        car = self.app.career
        if hasattr(car, "is_sprint_feature_weekend") and car.is_sprint_feature_weekend():
            self.app.replace(StrategyScene(self.app, "sprint",
                                           lambda a: SprintSimulatingScene(a)))
        else:
            rt = "feature" if car.current_series_id == "formula_1" else "race"
            self.app.replace(StrategyScene(self.app, rt, lambda a: SimulatingScene(a)))

    def update(self, dt):
        self.t += dt

    def handle(self, event):
        self.go_btn.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll = max(0, self.scroll - 1)
            elif event.button == 5:
                self.scroll = min(self.max_scroll, self.scroll + 1)

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        x, y, w, h = _RT_X, _RT_Y, _RT_W, _RT_H
        fmt = self.quali["format"] if self.quali else "single"
        title = t("qualifying.title_full") if fmt == "q1q2q3" else t("qualifying.title")
        draw_text(surf, title, f.h1, T.ACCENT, (x, 44))
        if self.is_wet:
            chip(surf, t("qualifying.wet"), (x + 520, 48), f.small, T.BG, T.ACCENT_2)

        panel(surf, (x, y, w, h), T.BG_PANEL)
        cP, cN, cT, cTime, cGap, cSeg = x+22, x+66, x+330, x+560, x+690, x+w-24
        draw_text(surf, t("common.pos"), f.tiny, T.TEXT_DIM, (cP, y+16))
        draw_text(surf, t("common.driver_col"), f.tiny, T.TEXT_DIM, (cN, y+16))
        draw_text(surf, t("common.team_col"), f.tiny, T.TEXT_DIM, (cT, y+16))
        draw_text(surf, t("common.time_col"), f.tiny, T.TEXT_DIM, (cTime, y+16))
        draw_text(surf, t("common.gap_col"), f.tiny, T.TEXT_DIM, (cGap, y+16))
        draw_text(surf, t("common.phase_col"), f.tiny, T.TEXT_DIM, (cSeg, y+16), right=True)
        pygame.draw.line(surf, T.LINE, (x+14, y+_RT_HEAD-4), (x+w-14, y+_RT_HEAD-4), 1)

        rows = self.quali["rows"] if self.quali else []
        prev = surf.get_clip()
        surf.set_clip(pygame.Rect(x, y+_RT_HEAD, w, h-_RT_HEAD))
        ry = y + _RT_HEAD + 4
        for r in rows[self.scroll:self.scroll + self.visible + 1]:
            is_me = (r["driver_id"] == self.my_id) or (self.my_team and self._is_my_team(r))
            row = pygame.Rect(x+12, ry-3, w-24, _RT_ROW-2)
            if is_me:
                pygame.draw.rect(surf, T.BG_PANEL_2, row, border_radius=6)
                pygame.draw.rect(surf, T.ACCENT, row, width=2, border_radius=6)
            pcol = T.GOLD if r["pos"] == 1 else (T.TEXT if is_me else T.TEXT_DIM)
            pole = (r["pos"] == 1)
            draw_text(surf, t("qualifying.pole") if pole else f"{r['pos']}", f.small,
                      T.GOLD if pole else pcol, (cP, ry))
            draw_text(surf, r["name"], f.small, T.TEXT if is_me else T.TEXT, (cN, ry))
            draw_text(surf, r["team_name"], f.tiny, T.TEXT_FAINT, (cT, ry+2))
            mins = int(r["time"] // 60)
            secs = r["time"] - mins*60
            draw_text(surf, f"{mins}:{secs:06.3f}", f.small, pcol, (cTime, ry))
            gap = r.get("gap", 0)
            draw_text(surf, "—" if gap <= 0 else f"+{gap:.3f}", f.small,
                      T.TEXT_FAINT, (cGap, ry))
            seg = r.get("segment", "Q")
            draw_text(surf, seg, f.tiny, SEG_COLOR.get(seg, T.TEXT_DIM), (cSeg, ry), right=True)
            ry += _RT_ROW
        surf.set_clip(prev)
        if self.max_scroll > 0:
            th = h - _RT_HEAD - 8
            kh = max(24, int(th * self.visible / len(rows)))
            ky = y + _RT_HEAD + 4 + int((th - kh) * self.scroll / self.max_scroll)
            pygame.draw.rect(surf, T.ACCENT, (x+w-8, ky, 4, kh), border_radius=2)

        # painel lateral: sua largada
        ex, ew = x + w + 20, T.WIDTH - (x + w + 20) - 40
        panel(surf, (ex, y, ew, h), T.BG_PANEL)
        draw_text(surf, t("qualifying.my_start"), f.tiny, T.ACCENT, (ex+18, y+16))
        my = next((r for r in rows if (r["driver_id"] == self.my_id) or
                   (self.my_team and self._is_my_team(r))), None)
        if my:
            draw_text(surf, f"P{my['pos']}", f.big_num,
                      T.GOLD if my['pos'] == 1 else T.TEXT, (ex+18, y+44))
            draw_text(surf, t("qualifying.on_grid"), f.small, T.TEXT_DIM, (ex+18, y+108))
            if fmt == "q1q2q3":
                draw_text(surf, t("qualifying.eliminated", seg=my.get('segment','Q3')), f.small,
                          SEG_COLOR.get(my.get('segment'), T.TEXT_DIM), (ex+18, y+140))
        if fmt == "q1q2q3":
            draw_text(surf, t("qualifying.q_format"), f.tiny, T.TEXT_FAINT,
                      (ex+18, y+h-30))
        self.go_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# SIMULANDO (tela de espera animada)
# ══════════════════════════════════════════════════════════════════════════════
class _SimBase(Scene):
    """Base para telas de simulação animada."""
    DURATION = 1.0
    _label = "SIMULANDO"

    def on_enter(self):
        self.t = 0.0
        self.done = False
        self.track = self.app.career.current_round()
        random.seed()
        self.lines = [(random.randint(0, T.WIDTH), random.randint(120, T.HEIGHT - 120),
                       random.randint(60, 180), random.uniform(0.6, 1.4))
                      for _ in range(26)]

    def handle(self, event):
        pass

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        cx, cy = T.WIDTH // 2, T.HEIGHT // 2
        for lx, ly, ln, spd in self.lines:
            px = (lx - self.t * 900 * spd) % (T.WIDTH + 200) - 100
            shade = T.lerp(T.BG_PANEL, T.ACCENT, min(1.0, spd / 1.4) * 0.5)
            pygame.draw.line(surf, shade, (px, ly), (px + ln, ly), 2)
        name = self.track.track_name if self.track else ""
        country = self.track.country if self.track else ""
        draw_text(surf, self._label, f.h1, T.ACCENT, (cx, cy - 110), center=True)
        draw_text(surf, name, f.title, T.TEXT, (cx, cy - 50), center=True)
        if country:
            draw_text(surf, country, f.body, T.TEXT_DIM, (cx, cy + 12), center=True)
        bw = 560
        bx, by = cx - bw // 2, cy + 60
        pygame.draw.rect(surf, T.BG_PANEL, (bx, by, bw, 12), border_radius=6)
        prog = min(1.0, self.t / self.DURATION)
        pygame.draw.rect(surf, T.ACCENT, (bx, by, int(bw * prog), 12), border_radius=6)
        draw_icon(surf, "play", bx + int(bw * prog), by + 6, 18, T.GOLD)
        dots = "." * (int(self.t * 4) % 4)
        draw_text(surf, t("simulating.preparing") + dots, f.small, T.TEXT_DIM, (cx, cy + 100), center=True)


# ── Estratégia de corrida (pneus + paradas + ritmo) ───────────────────────────
TYRES = [("soft", "MACIO", T.RED), ("medium", "MÉDIO", T.GOLD), ("hard", "DURO", T.TEXT)]
PACES = [("attack", "ATACAR", T.RED, "Mais rápido · gasta pneu · risco"),
         ("normal", "NORMAL", T.ACCENT_2, "Equilíbrio"),
         ("conserve", "CONSERVAR", T.GREEN, "Mais lento · poupa pneu · seguro")]


def pit_rules(series_id, race_type):
    if race_type == "sprint":
        return (0, 0)
    if series_id in ("formula_1", "formula_2") and race_type == "feature":
        return (1, 2)
    return (0, 2)


def _pop_strategy(app):
    s = getattr(app, "pending_strategy", None)
    p = getattr(app, "pending_pace", None)
    app.pending_strategy = None
    app.pending_pace = None
    return s, p


class StrategyScene(Scene):
    def __init__(self, app, race_type, next_factory):
        super().__init__(app)
        self.race_type = race_type
        self.next_factory = next_factory

    def on_enter(self):
        f = self.app.fonts
        car = self.app.career
        self.track = car.current_round()
        self.min_stops, self.max_stops = pit_rules(car.current_series_id, self.race_type)
        wear = getattr(self.track, "tyre_wear_index", 4) if self.track else 4
        self.stops = max(self.min_stops, min(self.max_stops, 1 if wear >= 5 else self.min_stops))
        self.stints = ([2, 1, 2] if wear > 6 else ([1, 2, 2] if wear > 4 else [0, 1, 1])) + [1, 1]
        self.pace = 1
        self.auto = False
        self._rects = {}
        self.go = Button((T.WIDTH // 2 - 150, T.HEIGHT - 64, 300, 50),
                         "LARGAR", self._go, f.h2, icon="play")
        self.auto_btn = Button((T.WIDTH - 250, 96, 210, 42),
                               "Automático", self._toggle, f.body, kind="ghost")

    def _toggle(self):
        self.auto = not self.auto

    def _go(self):
        car = self.app.career
        drivers = ([car.player_driver] if self.app.profile.mode != "manager"
                   else car.player_drivers())
        if self.auto:
            self.app.pending_strategy = None
        else:
            plan = [TYRES[self.stints[i]][0] for i in range(self.stops + 1)]
            if self.min_stops >= 1 and len(set(plan)) < 2 and len(plan) >= 2:
                plan[1] = TYRES[(self.stints[0] + 1) % 3][0]
            self.app.pending_strategy = {d.id: list(plan) for d in drivers if d}
        self.app.pending_pace = {d.id: PACES[self.pace][0] for d in drivers if d}
        self.app.replace(self.next_factory(self.app))

    def update(self, dt): ...

    def handle(self, event):
        self.go.handle(event)
        self.auto_btn.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self._rects.items():
                if rect.collidepoint(event.pos):
                    kind, idx = key
                    if kind == "stops":
                        self.stops = idx; self.auto = False
                    elif kind == "pace":
                        self.pace = idx
                    else:
                        self.stints[kind] = idx; self.auto = False

    def _boxes(self, surf, f, label, y, options, sel, kind, disabled=False, h=46):
        draw_text(surf, label, f.small, T.TEXT_DIM, (120, y))
        x = 120
        for i, opt in enumerate(options):
            rect = pygame.Rect(x, y + 26, 168, h)
            on = (i == sel) and not disabled
            pygame.draw.rect(surf, T.BG_PANEL_2 if on else T.BG_PANEL, rect, border_radius=10)
            pygame.draw.rect(surf, opt[2] if on else T.LINE, rect, width=3 if on else 1, border_radius=10)
            draw_text(surf, opt[1], f.h2, opt[2] if on else T.TEXT_DIM, (rect.centerx, rect.y + 5), center=True)
            if len(opt) > 3:
                draw_text(surf, opt[3], f.tiny, T.TEXT_FAINT, (rect.centerx, rect.y + h - 15), center=True)
            self._rects[(kind, i)] = rect
            x += 182

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        self._rects = {}
        lbl = {"sprint": "SPRINT", "feature": "FEATURE", "race": "CORRIDA"}.get(self.race_type, "")
        draw_text(surf, f"ESTRATÉGIA — {lbl}", f.h1, T.ACCENT, (120, 40))
        if self.track:
            draw_text(surf, f"{getattr(self.track,'track_name','')} · {getattr(self.track,'laps','?')} voltas · "
                            f"desgaste {getattr(self.track,'tyre_wear_index','?')}/10",
                      f.body, T.TEXT_DIM, (120, 92))
        # paradas
        draw_text(surf, "PARADAS", f.small, T.TEXT_DIM, (120, 128))
        x = 120
        for n in range(self.min_stops, self.max_stops + 1):
            rect = pygame.Rect(x, 154, 168, 44)
            on = (n == self.stops)
            pygame.draw.rect(surf, T.BG_PANEL_2 if on else T.BG_PANEL, rect, border_radius=10)
            pygame.draw.rect(surf, T.ACCENT if on else T.LINE, rect, width=3 if on else 1, border_radius=10)
            txt = ("SEM PARAR" if n == 0 else f"{n} PARADA" + ("S" if n != 1 else ""))
            draw_text(surf, txt, f.body, T.ACCENT if on else T.TEXT_DIM, (rect.centerx, rect.centery - 10), center=True)
            self._rects[("stops", n)] = rect
            x += 182
        # stints
        y = 216
        for s in range(self.stops + 1):
            self._boxes(surf, f, "PNEU DE LARGADA" if s == 0 else f"APÓS PARADA {s}", y, TYRES, self.stints[s], s, self.auto)
            y += 78
        # ritmo
        self._boxes(surf, f, "RITMO", y + 4, PACES, self.pace, "pace", h=52)
        hint = ("Sem parar: 1 jogo de pneu, só para se furar." if self.stops == 0
                else f"{self.stops} parada(s): pneu fresco, mas perde tempo no box.")
        draw_text(surf, hint, f.small, T.TEXT_FAINT, (120, T.HEIGHT - 110))
        if self.auto:
            draw_text(surf, "AUTOMÁTICO (a equipe decide)", f.small, T.ACCENT_2, (120, T.HEIGHT - 134))
        self.auto_btn.draw(surf)
        self.go.draw(surf)


class SimulatingScene(_SimBase):
    @property
    def _label(self): return t("simulating.race")

    def update(self, dt):
        self.t += dt
        if self.t >= self.DURATION and not self.done:
            self.done = True
            strat, pace = _pop_strategy(self.app)
            res, ev = self.app.career.simulate_next_race(strat, pace)
            self.app.replace(RaceResultScene(self.app, res, ev, race_label=t("simulating.race")))


class SprintSimulatingScene(_SimBase):
    @property
    def _label(self): return t("simulating.sprint")

    def update(self, dt):
        self.t += dt
        if self.t >= self.DURATION and not self.done:
            self.done = True
            strat, pace = _pop_strategy(self.app)
            res, ev = self.app.career.simulate_sprint_race(strat, pace)
            self.app.replace(RaceResultScene(
                self.app, res, ev, race_label=t("simulating.sprint"),
                next_scene_factory=lambda a: StrategyScene(a, "feature",
                                                           lambda b: FeatureSimulatingScene(b))))


class FeatureSimulatingScene(_SimBase):
    @property
    def _label(self): return t("simulating.feature")

    def update(self, dt):
        self.t += dt
        if self.t >= self.DURATION and not self.done:
            self.done = True
            strat, pace = _pop_strategy(self.app)
            res, ev = self.app.career.simulate_feature_race(strat, pace)
            self.app.replace(RaceResultScene(self.app, res, ev, race_label="FEATURE RACE"))


# ══════════════════════════════════════════════════════════════════════════════
# RESULTADO DA CORRIDA
# ══════════════════════════════════════════════════════════════════════════════
_EVENT_COLORS = {
    "safety_car":     T.GOLD,
    "safety_car_end": T.TEXT_DIM,
    "virtual_safety": T.GOLD,
    "engine_failure": T.RED,
    "puncture":       T.RED,
    "crash":          T.RED,
    "spin":           T.ACCENT,
    "injury":         T.RED,
    "fp1_bonus":      T.ACCENT_2,
    "penalty":        T.RED,
}
_EVENT_KEYS = set(_EVENT_COLORS.keys())


def _event_label(etype):
    return t(f"events.{etype}", etype), _EVENT_COLORS.get(etype, T.TEXT_DIM)

# layout da tabela
_RT_X, _RT_Y, _RT_W, _RT_H = 60, 96, 880, 560
_RT_ROW = 34
_RT_HEAD = 44


class RaceResultScene(Scene):
    def __init__(self, app, results, events, race_label="CORRIDA", next_scene_factory=None):
        super().__init__(app)
        self.results = results
        self.events = events
        self.race_label = race_label
        self.next_scene_factory = next_scene_factory  # callable(app) → Scene, para sprint→feature

    def on_enter(self):
        f = self.app.fonts
        # Label do botão depende se há feature race a seguir
        btn_label = t("result.to_feature") if self.next_scene_factory else t("result.continue")
        self.ok_btn = Button((T.WIDTH // 2 - 160, T.HEIGHT - 64, 320, 50),
                             btn_label, self._continue, f.h2, icon="play")
        car = self.app.career
        self.my_id = (car.player_driver.id if self.app.profile.mode == "driver"
                      else None)
        self.my_team = (car.player_team.id if self.app.profile.mode != "driver" else None)
        self.t = 0.0
        self.scroll = 0
        # tempo do vencedor (para gaps) e melhor volta da corrida
        fin = [r for r in self.results if not r.dnf]
        self.winner_time = min((r.total_time for r in fin), default=0.0)
        best_laps = [r.best_lap_time for r in self.results if r.best_lap_time > 0]
        self.race_best_lap = min(best_laps) if best_laps else 0.0
        # standings do campeonato para mostrar pontos acumulados
        car_st = {d.id: pts for _, d, pts in car.driver_standings()} if hasattr(car, "driver_standings") else {}
        self.champ_pts = car_st
        self.visible = (_RT_H - _RT_HEAD - 6) // _RT_ROW
        self.max_scroll = max(0, len(self.results) - self.visible)
        idx = next((i for i, r in enumerate(self.results)
                    if r.driver_id == self.my_id or
                    (self.my_team and r.team_id == self.my_team)), 0)
        self.scroll = max(0, min(self.max_scroll, idx - self.visible // 2))

    def update(self, dt):
        self.t += dt

    def _continue(self):
        if self.next_scene_factory:
            self.app.replace(self.next_scene_factory(self.app))
            return
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
            return (t("result.leader"), T.GOLD)
        gap = r.total_time - self.winner_time
        return (f"+{gap:.1f}s", T.TEXT_DIM)

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        x, y, w, h = _RT_X, _RT_Y, _RT_W, _RT_H
        draw_text(surf, t("result.title", label=self.race_label), f.h1, T.ACCENT, (x, 44))
        draw_text(surf, t("result.scroll_hint"), f.tiny, T.TEXT_FAINT, (x + 460, 58))

        panel(surf, (x, y, w, h), T.BG_PANEL)
        cP   = x + 22
        cN   = x + 66
        cT   = x + 310
        cG   = x + 490
        cGA  = x + 590
        cBL  = x + 690
        cPt  = x + w - 52
        cCPt = x + w - 16
        draw_text(surf, t("common.pos"),        f.tiny, T.TEXT_DIM, (cP,   y+16))
        draw_text(surf, t("common.driver_col"), f.tiny, T.TEXT_DIM, (cN,   y+16))
        draw_text(surf, t("common.team_col"),   f.tiny, T.TEXT_DIM, (cT,   y+16))
        draw_text(surf, t("common.gap_col"),    f.tiny, T.TEXT_DIM, (cG,   y+16))
        draw_text(surf, t("common.ahead_col"),  f.tiny, T.TEXT_DIM, (cGA,  y+16))
        draw_text(surf, t("common.bestlap_col"),f.tiny, T.TEXT_DIM, (cBL,  y+16))
        draw_text(surf, t("common.pts_col"),    f.tiny, T.TEXT_DIM, (cPt, y+16), right=True)
        draw_text(surf, t("common.champ_col"),  f.tiny, T.TEXT_DIM, (cCPt, y+16), right=True)
        pygame.draw.line(surf, T.LINE, (x+14, y+_RT_HEAD-4), (x+w-14, y+_RT_HEAD-4), 1)

        prev = surf.get_clip()
        surf.set_clip(pygame.Rect(x, y+_RT_HEAD, w, h-_RT_HEAD))
        ry = y + _RT_HEAD + 4
        for r in self.results[self.scroll:self.scroll + self.visible + 1]:
            is_me = (r.driver_id == self.my_id) or (self.my_team and r.team_id == self.my_team)
            row = pygame.Rect(x+12, ry-3, w-24, _RT_ROW-2)
            if is_me:
                pygame.draw.rect(surf, T.BG_PANEL_2, row, border_radius=6)
                pygame.draw.rect(surf, T.ACCENT, row, width=2, border_radius=6)
            pcol = T.GOLD if r.position == 1 else (T.TEXT if is_me else T.TEXT_DIM)
            ptxt = "DNF" if r.dnf else f"P{r.position}"
            draw_text(surf, ptxt, f.small, T.RED if r.dnf else pcol, (cP, ry))
            nm = r.driver_name[:18] + ("  ·FL" if r.fastest_lap else "")
            draw_text(surf, nm, f.small,
                      T.PURPLE if r.fastest_lap else (T.TEXT if is_me else T.TEXT_DIM),
                      (cN, ry))
            draw_text(surf, r.team_name[:18], f.tiny, T.TEXT_FAINT, (cT, ry+2))
            gtxt, gcol = self._gap_text(r)
            draw_text(surf, gtxt, f.small, gcol, (cG, ry))
            # gap ao de frente
            if not r.dnf and r.gap_to_ahead > 0:
                draw_text(surf, f"+{r.gap_to_ahead:.1f}s", f.tiny, T.TEXT_FAINT, (cGA, ry+2))
            elif not r.dnf and r.position == 1:
                draw_text(surf, "—", f.tiny, T.TEXT_FAINT, (cGA, ry+2))
            # melhor volta (FL em roxo se for a melhor da corrida)
            if r.best_lap_time > 0:
                bl_mins = int(r.best_lap_time // 60)
                bl_secs = r.best_lap_time - bl_mins * 60
                bl_txt = f"{bl_mins}:{bl_secs:05.2f}"
                bl_col = T.PURPLE if (self.race_best_lap > 0 and abs(r.best_lap_time - self.race_best_lap) < 0.001) else T.TEXT_FAINT
                draw_text(surf, bl_txt, f.tiny, bl_col, (cBL, ry+2))
            # pontos da corrida
            draw_text(surf, f"{r.points}", f.small if is_me else f.tiny,
                      T.GOLD if r.points > 0 else pcol, (cPt, ry), right=True)
            # pontos do campeonato
            camp_pts = self.champ_pts.get(r.driver_id, 0)
            draw_text(surf, f"{camp_pts}", f.tiny, T.ACCENT_2 if is_me else T.TEXT_FAINT,
                      (cCPt, ry+2), right=True)
            ry += _RT_ROW
        surf.set_clip(prev)

        # barra de rolagem
        if self.max_scroll > 0:
            track_h = h - _RT_HEAD - 8
            knob_h = max(24, int(track_h * self.visible / len(self.results)))
            knob_y = y + _RT_HEAD + 4 + int((track_h - knob_h) * self.scroll / self.max_scroll)
            pygame.draw.rect(surf, T.LINE, (x+w-8, y+_RT_HEAD+4, 4, track_h), border_radius=2)
            pygame.draw.rect(surf, T.ACCENT, (x+w-8, knob_y, 4, knob_h), border_radius=2)

        # painel lateral: eventos + melhor volta pessoal + posição no camp.
        ex, ew = x + w + 20, T.WIDTH - (x + w + 20) - 40
        panel(surf, (ex, y, ew, h), T.BG_PANEL)
        draw_text(surf, t("result.what_happened"), f.tiny, T.ACCENT, (ex+18, y+16))

        # resultado pessoal no topo do painel
        my_res = next((r for r in self.results
                       if r.driver_id == self.my_id or
                       (self.my_team and r.team_id == self.my_team)), None)
        ey = y + 46
        if my_res:
            pos_col = T.GOLD if my_res.position <= 3 else (T.RED if my_res.dnf else T.TEXT)
            pos_txt = f"DNF" if my_res.dnf else f"P{my_res.position}"
            draw_text(surf, pos_txt, f.h1, pos_col, (ex+18, ey))
            ey += 42
            draw_text(surf, t("result.race_pts", pts=my_res.points), f.small, T.GOLD, (ex+18, ey))
            ey += 24
            camp = self.champ_pts.get(my_res.driver_id, 0) if my_res.driver_id else 0
            draw_text(surf, t("result.champ_pts", pts=camp), f.small, T.ACCENT_2, (ex+18, ey))
            ey += 24
            if my_res.best_lap_time > 0:
                bl_m = int(my_res.best_lap_time // 60)
                bl_s = my_res.best_lap_time - bl_m * 60
                draw_text(surf, t("result.best_lap_short", time=f"{bl_m}:{bl_s:05.2f}"), f.small,
                          T.PURPLE if my_res.fastest_lap else T.TEXT_DIM, (ex+18, ey))
                ey += 24
            pygame.draw.line(surf, T.LINE, (ex+14, ey+4), (ex+ew-14, ey+4), 1)
            ey += 14

        ev_list = [e for e in self.events if getattr(e, "event_type", "") in _EVENT_KEYS]
        ev_list.sort(key=lambda e: getattr(e, "lap", 0))
        if not ev_list:
            draw_text(surf, t("result.clean_race"), f.small, T.TEXT_DIM, (ex+18, ey))
        for e in ev_list[:10]:
            label, col = _event_label(e.event_type)
            lap = getattr(e, "lap", 0)
            tag = f"V{lap}" if lap else "—"
            draw_text(surf, tag, f.tiny, T.TEXT_FAINT, (ex+18, ey+2))
            draw_text(surf, label, f.small, col, (ex+52, ey))
            did = getattr(e, "affects_driver", None)
            if did:
                drv = next((r.driver_name[:16] for r in self.results if r.driver_id == did), "")
                if drv:
                    draw_text(surf, drv, f.tiny, T.TEXT_DIM, (ex+52, ey+18))
                    ey += 16
            ey += 28
            if ey > y + h - 60:
                break
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
        self.champion_must_promote = self.s.get("champion_must_promote", False)
        car = self.app.career
        if self.champion_must_promote:
            label = t("season_end.btn_champion_promote")
            color = T.GOLD
        elif self.promoted:
            label = t("season_end.btn_promote")
            color = T.GOLD
        elif getattr(car, "_free_agent_next_season", False):
            label = t("season_end.btn_choose_team")
            color = T.ACCENT_2
        else:
            label = t("season_end.btn_next")
            color = T.ACCENT
        self.go_btn = Button((T.WIDTH // 2 - 200, T.HEIGHT - 90, 400, 54),
                             label, self._next, f.h2, color=color)
        self.menu_btn = Button((40, T.HEIGHT - 90, 160, 52), t("common.menu"),
                               lambda: self.app.reset_to(MenuScene(self.app)),
                               f.body, kind="ghost")

    def _next(self):
        car = self.app.career
        profile = self.app.profile
        if profile.mode == "driver":
            # Se o piloto quer ser agente livre e ainda não escolheu equipe
            if getattr(car, "_free_agent_next_season", False) and not car._pending_offer:
                self.app.push(JobSearchScene(self.app))
                return
            car._free_agent_next_season = False
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
        draw_text(surf, t("season_end.title"), f.h1, T.ACCENT, (cx, 50), center=True)

        panel(surf, (cx - 380, 110, 760, 460), T.BG_PANEL)
        x = cx - 340
        y = 140

        is_driver = self.app.profile.mode == "driver"
        pos = s.get("player_position") if is_driver else s.get("team_position")
        pcol = T.GOLD if pos == 1 else T.TEXT
        draw_text(surf, t("season_end.final_pos"), f.small, T.TEXT_DIM, (x, y))
        draw_text(surf, f"P{pos}", f.big_num, pcol, (x, y + 22))

        draw_text(surf, t("season_end.champion"), f.small, T.TEXT_DIM, (cx + 60, y))
        draw_text(surf, s.get("champion_driver", "?"), f.h2, T.TEXT, (cx + 60, y + 26))
        draw_text(surf, s.get("champion_team", ""), f.small, T.TEXT_DIM, (cx + 60, y + 60))

        y += 130
        pygame.draw.rect(surf, T.LINE, (x, y, 680, 1))
        y += 20

        rows = []
        if is_driver:
            rows.append((t("season_end.sl_earned"), f"+{s.get('sl_earned', 0)}"))
            rows.append((t("season_end.sl_total"), f"{s.get('sl_total', 0)}/40"))
            rows.append((t("season_end.prize_money"), f"€ {s.get('prize_money', 0):,}".replace(",", ".")))
            rows.append((t("season_end.personal_money"), f"€ {s.get('personal_money', 0):,}".replace(",", ".")))
            if s.get("sl_blocked"):
                rows.append((t("season_end.sl_blocked"), s.get("sl_block_reason", "")))
        else:
            rows.append((t("season_end.sponsor_income"), f"€ {s.get('sponsor_income', 0):,}".replace(",", ".")))
            rows.append((t("season_end.prize_money"), f"€ {s.get('prize_money', 0):,}".replace(",", ".")))
            rows.append((t("season_end.dividend"), f"€ {s.get('dividend', 0):,}".replace(",", ".")))
            rows.append((t("season_end.final_budget"), f"€ {s.get('final_budget', 0):,}".replace(",", ".")))
        for label, val in rows:
            draw_text(surf, label, f.body, T.TEXT_DIM, (x, y))
            draw_text(surf, val, f.body, T.TEXT, (x + 680, y), right=True)
            y += 36

        deltas = s.get("skill_deltas") or {}
        if is_driver and deltas:
            y += 6
            draw_text(surf, t("season_end.evolution"), f.tiny, T.ACCENT, (x, y)); y += 26
            skill_names = {
                "speed": t("profile.stat_speed"),
                "consistency": t("profile.stat_consistency"),
                "tyre_mgmt": t("profile.stat_tyre"),
                "overtaking": t("profile.stat_overtaking"),
                "defence": t("profile.stat_defence"),
                "rain": t("profile.stat_rain"),
                "feedback": t("profile.stat_feedback"),
            }
            dx = x
            for attr, dv in deltas.items():
                if dv == 0:
                    continue
                txt = f"{skill_names.get(attr, attr)} {'+' if dv > 0 else ''}{dv}"
                col = T.GREEN if dv > 0 else T.RED
                rect = chip(surf, txt, (dx, y), f.small, T.BG, col)
                dx += rect.width + 8
                if dx > x + 560:
                    dx = x; y += 34
            if not any(deltas.values()):
                draw_text(surf, t("season_end.no_evolution"), f.small, T.TEXT_FAINT, (x, y))

        if self.champion_must_promote:
            draw_text(surf, t("season_end.champion_must_promote",
                              series=SERIES_LABEL.get(s.get('promotes_to',''), '')),
                      f.h2, T.GOLD, (cx, 544), center=True)
            draw_text(surf, t("season_end.champion_rule"), f.tiny, T.TEXT_DIM, (cx, 572), center=True)
        elif self.promoted:
            draw_text(surf, t("season_end.promoted_to",
                              series=SERIES_LABEL.get(s.get('promotes_to',''), '')),
                      f.h2, T.GREEN, (cx, 548), center=True)
        elif not s.get("sl_blocked"):
            draw_text(surf, t("season_end.same_category"), f.small, T.TEXT_DIM,
                      (cx, 550), center=True)

        car = self.app.career
        if getattr(car, "_free_agent_next_season", False):
            panel(surf, (cx - 380, 578, 760, 36), T.BG_PANEL_2, border=T.GOLD, border_w=1)
            draw_text(surf, t("season_end.free_agent_banner"),
                      f.small, T.GOLD, (cx, 596), center=True)

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
                               t("load.btn"), self._load, f.h2)
        self.back_btn = Button((T.WIDTH // 2 + 20, T.HEIGHT - 90, 200, 52),
                               t("common.back"), self.app.pop, f.body, kind="ghost")

    def _row(self, surf, sv, row, sel, fonts):
        mode = t("load.mode_driver") if sv.get("mode") == "driver" else t("load.mode_manager")
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
            self.app.notify(t("load.fail"))

    def handle(self, event):
        if self.saves:
            self.list.handle(event)
            self.load_btn.handle(event)
        self.back_btn.handle(event)

    def update(self, dt):
        pass

    def draw(self, surf):
        gradient_bg(surf)
        header(surf, self.app, t("load.header"))
        f = self.app.fonts
        draw_text(surf, t("load.title"), f.h1, T.TEXT, (cx_center(), 120))
        if not self.saves:
            draw_text(surf, t("load.no_saves"), f.body, T.TEXT_DIM,
                      (T.WIDTH // 2, 300), center=True)
        else:
            panel(surf, (cx_center() - 10, 170, 720, 400), T.BG_PANEL)
            self.list.draw(surf, f)
            self.load_btn.draw(surf)
        self.back_btn.draw(surf)


class OptionsScene(Scene):
    def on_enter(self):
        f = self.app.fonts
        self.back_btn = Button((40, T.HEIGHT - 76, 180, 52), t("common.back"),
                               self.app.pop, f.body, kind="ghost", icon="menu")
        self._lang_rects = []
        self.res_rects = []

    def handle(self, event):
        self.back_btn.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for lang_code, r in getattr(self, "_lang_rects", []):
                if r.collidepoint(event.pos):
                    set_language(lang_code)
                    self.app.notify(LANG_NAMES.get(lang_code, lang_code))
                    return
            for idx, r in getattr(self, "res_rects", []):
                if r.collidepoint(event.pos):
                    self.app.set_resolution(idx)
                    self.app.notify(f"Resolução: {T.RESOLUTIONS[idx][0]}")
                    return

    def update(self, dt):
        pass

    def _option_chip(self, surf, rect, label, active, active_col):
        f = self.app.fonts
        bg = active_col if active else T.BG_PANEL_2
        edge = active_col if active else T.LINE
        fg = T.BG if active else T.TEXT_DIM
        pygame.draw.rect(surf, bg, rect, border_radius=8)
        pygame.draw.rect(surf, edge, rect, width=1, border_radius=8)
        draw_text(surf, label, f.small, fg, rect.center, center=True)

    def draw(self, surf):
        premium_bg(surf, self.app.anim_t)
        header(surf, self.app, "Opções")
        f = self.app.fonts
        cx = T.WIDTH // 2

        glass_panel(surf, (270, 120, 740, 430), T.PURPLE, alpha=224, radius=10)
        draw_text(surf, "OPÇÕES", f.h1, T.TEXT, (cx, 150), center=True)
        draw_text(surf, "Ajuste o jogo antes de voltar para a garagem.",
                  f.small, T.TEXT_DIM, (cx, 194), center=True)

        draw_text(surf, t("menu.lang_label").upper(), f.tiny, T.ACCENT_2, (330, 260))
        lang_list = list(LANG_NAMES.items())
        self._lang_rects = []
        x = 330
        cur_lang = current_language()
        for code, label in lang_list:
            w = max(110, f.small.size(label)[0] + 34)
            r = pygame.Rect(x, 286, w, 42)
            self._option_chip(surf, r, label, code == cur_lang, T.ACCENT_2)
            self._lang_rects.append((code, r))
            x += w + 12

        draw_text(surf, t("menu.resolution").upper(), f.tiny, T.ACCENT, (330, 370))
        labels = [r[0] for r in T.RESOLUTIONS]
        self.res_rects = []
        x, y = 330, 396
        for i, lab in enumerate(labels):
            w = max(118, f.small.size(lab)[0] + 34)
            if x + w > 950:
                x = 330
                y += 54
            r = pygame.Rect(x, y, w, 42)
            self._option_chip(surf, r, lab, i == self.app.res_index, T.ACCENT)
            self.res_rects.append((i, r))
            x += w + 12

        self.back_btn.draw(surf)


def cx_center():
    return (T.WIDTH - 700) // 2


# ══════════════════════════════════════════════════════════════════════════════
# OFERTAS (portado de main.py)
# ══════════════════════════════════════════════════════════════════════════════
def _build_offer_dict(otype, team, series_id, salary, years, forced=False):
    series_label = SERIES_LABEL.get(series_id, series_id)
    descs = {
        "step_up":        t("offer.desc_step_up",        team=team.name, series=series_label),
        "step_down":      t("offer.desc_step_down",       team=team.name, series=series_label),
        "lateral_better": t("offer.desc_lateral_better",  team=team.name, perf=f"{team.car_performance:.0f}"),
        "lateral_worse":  t("offer.desc_lateral_worse",   team=team.name),
        "fired":          t("offer.desc_fired",            team=team.name),
    }
    return {
        "type": otype, "from_team": team.name, "from_team_id": team.id,
        "from_series": series_id, "from_series_label": series_label,
        "salary": salary, "years": years, "description": descs.get(otype, ""),
        "team_chassis": team.chassis, "team_rep": team.reputation, "forced": forced,
    }


def _gen_driver_offer(career):
    # Contract lock: already signed → only promotions to a higher series are allowed
    already_signed = getattr(career, "_contract_next_year", None) is not None
    signed_series  = getattr(career, "_contract_next_series", None)

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

    if already_signed:
        if otype != "step_up":
            return None
        next_s = series_above(career.current_series_id)
        if not next_s:
            return None
        if signed_series and signed_series in SERIES_PROGRESSION:
            signed_idx = SERIES_PROGRESSION.index(signed_series)
            next_idx   = SERIES_PROGRESSION.index(next_s)
            if next_idx <= signed_idx:
                return None
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
    # Já assinou contrato via _contract_next_year? Filtra no próprio offers.py.
    # Fallback legado: checa _pending_offer
    pending = getattr(car, "_pending_offer", None)
    if pending and offer.get("type") != "not_renewed":
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
        self.back_btn = Button((40, T.HEIGHT - 70, 180, 52), t("common.back"),
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
        header(surf, self.app, t(self.title, self.title))
        if self.subtitle:
            draw_text(surf, t(self.subtitle, self.subtitle), self.app.fonts.small, T.TEXT_DIM, (40, 84))
        self.body(surf)
        self.back_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO COMPLETA
# ══════════════════════════════════════════════════════════════════════════════
class StandingsScene(SubScene):
    title = "standings.scene_title"
    subtitle = "standings.subtitle"
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

        self._draw_col(surf, f, car.driver_standings(), 40, 600, t("standings.drivers"),
                       self.scroll_d, driver_mine, lambda d: d.name, driver_short)
        self._draw_col(surf, f, car.team_standings(), 660, T.WIDTH - 660 - 40, t("standings.teams"),
                       self.scroll_t, lambda tm: (tm.id == my_tid) or tm.is_player_team,
                       lambda tm: tm.name, None)


# ══════════════════════════════════════════════════════════════════════════════
# SUPER LICENÇA
# ══════════════════════════════════════════════════════════════════════════════
class SuperLicenceScene(SubScene):
    title = "sl_scene.title"
    subtitle = "sl_scene.subtitle"

    def body(self, surf):
        f = self.app.fonts
        pd = self.app.career.player_driver
        s = sl.sl_summary(pd)
        panel(surf, (40, 130, 700, 480), T.BG_PANEL)
        x = 70
        draw_text(surf, pd.name, f.h1, T.TEXT, (x, 150))
        draw_text(surf, f"{pd.age} · {pd.nationality}", f.small, T.TEXT_DIM, (x, 192))
        elig = s["eligible"]
        chip(surf, t("sl_scene.eligible") if elig else t("sl_scene.not_eligible"), (x, 228), f.small,
             T.BG, T.GREEN if elig else T.RED)
        # barra
        draw_text(surf, t("sl_scene.points", pts=s['total_points']), f.small, T.GOLD, (x, 280))
        pygame.draw.rect(surf, T.BG_INPUT, (x, 308, 640, 14), border_radius=7)
        pygame.draw.rect(surf, T.GOLD, (x, 308, int(640 * min(1, s['total_points']/40)), 14),
                         border_radius=7)
        draw_text(surf, t("sl_scene.fp1", n=s['fp1_sessions'], pts=s['fp1_points']),
                  f.small, T.ACCENT_2, (x, 340))
        if not elig:
            draw_text(surf, s["reason"], f.small, T.RED, (x, 372))
        # histórico
        draw_text(surf, t("sl_scene.history"), f.tiny, T.ACCENT, (x, 416))
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
    title = "academy.title"

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
        draw_text(surf, "  ·  ".join([t("academy.prestige", n=a.prestige), t("academy.disc", n=disc),
                                     t("academy.pot", n=pot), t("academy.fp1_pct", n=fp1)]),
                  fonts.tiny, T.TEXT_DIM, (row.x + 14, row.y + 38))

    def _join(self):
        pd = self.app.career.player_driver
        if pd.academy_id:
            self.app.notify(t("academy.leave_first")); return
        a = self.list.current()
        ok, msg = acad.join_academy(pd, a.id, {"budget": self.app.profile.personal_money})
        self.app.notify(msg)

    def _leave(self):
        pd = self.app.career.player_driver
        if not pd.academy_id:
            self.app.notify(t("academy.not_in")); return
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
    title = "development.title"

    FAC = [("development.fac_factory", "fac_factory", "factory"),
           ("development.fac_simulator", "fac_simulator", "simulator"),
           ("development.fac_rd", "fac_r_and_d", "r_and_d"),
           ("development.fac_pit", "fac_pit_crew", "pit_crew"),
           ("development.fac_marketing", "fac_marketing", "marketing")]
    CAR = [("development.car_chassis", "chassis", 150_000, 3),
           ("development.car_aero", "aerodynamics", 180_000, 3),
           ("development.car_reliability", "reliability", 120_000, 4),
           ("development.car_pit", "pit_crew", 80_000, 3),
           ("development.car_engineers", "engineers", 100_000, 2),
           ("development.car_factory", "factory", 200_000, 3)]

    def setup(self):
        self.fac_btns = []
        self.car_btns = []

    def _upgrade_fac(self, attr, key, lbl_key):
        tm = self.app.career.player_team
        lvl = getattr(tm, attr, 1)
        cost = tm.facilities.upgrade_cost(key)
        name = t(lbl_key, lbl_key)
        if lvl >= 5:
            self.app.notify(t("development.maxed", name=name))
        elif tm.budget < cost:
            self.app.notify(t("development.no_budget"))
        else:
            setattr(tm, attr, lvl + 1); tm.budget -= cost
            self.app.notify(t("development.upgraded_fac", name=name, old=lvl, new=lvl+1))

    def _upgrade_car(self, attr, cost, gain, lbl_key):
        tm = self.app.career.player_team
        cur = getattr(tm, attr)
        name = t(lbl_key, lbl_key)
        if cur >= 99:
            self.app.notify(t("development.maxed", name=name))
        elif tm.budget < cost:
            self.app.notify(t("development.no_budget"))
        else:
            setattr(tm, attr, min(99, cur + gain)); tm.budget -= cost
            self.app.notify(t("development.upgraded_car", name=name, old=cur, new=getattr(tm, attr)))

    def body_handle(self, event):
        for b in self.fac_btns + self.car_btns:
            b.handle(event)

    def body(self, surf):
        f = self.app.fonts
        tm = self.app.career.player_team
        draw_text(surf, t("development.budget", amount=f"{tm.budget:,}".replace(",", ".")),
                  f.h2, T.GOLD, (40, 78))
        self.fac_btns = []
        self.car_btns = []
        panel(surf, (40, 120, 580, 250), T.BG_PANEL)
        draw_text(surf, t("development.facilities"), f.tiny, T.ACCENT, (60, 132))
        y = 162
        for lbl_key, attr, key in self.FAC:
            lvl = getattr(tm, attr, 1)
            cost = tm.facilities.upgrade_cost(key)
            draw_text(surf, t(lbl_key, lbl_key), f.body, T.TEXT, (60, y))
            for k in range(5):
                c = T.GOLD if k < lvl else T.LINE
                pygame.draw.circle(surf, c, (250 + k * 14, y + 12), 5)
            maxed = lvl >= 5
            label = t("development.max") if maxed else f"€ {cost:,}".replace(",", ".")
            b = Button((400, y - 4, 200, 34), label,
                       (lambda a=attr, k=key, l=lbl_key: self._upgrade_fac(a, k, l)),
                       f.small, kind="ghost" if (maxed or tm.budget < cost) else "primary")
            b.enabled = not maxed
            self.fac_btns.append(b); b.draw(surf)
            y += 42
        panel(surf, (640, 120, T.WIDTH - 640 - 40, 430), T.BG_PANEL)
        draw_text(surf, t("development.car"), f.tiny, T.ACCENT, (660, 132))
        y = 162
        for lbl_key, attr, cost, gain in self.CAR:
            cur = getattr(tm, attr)
            draw_text(surf, t(lbl_key, lbl_key), f.body, T.TEXT, (660, y))
            draw_text(surf, f"{cur}/100", f.small, T.ACCENT_2, (860, y))
            can = tm.budget >= cost and cur < 99
            b = Button((T.WIDTH - 40 - 230, y - 4, 230, 34),
                       f"+{gain}   € {cost:,}".replace(",", "."),
                       (lambda a=attr, c=cost, g=gain, l=lbl_key: self._upgrade_car(a, c, g, l)),
                       f.small, kind="primary" if can else "ghost")
            b.enabled = can
            self.car_btns.append(b); b.draw(surf)
            y += 44
        fac = tm.facilities
        draw_text(surf,
                  t("development.dev_stats",
                    dev=f"{fac.dev_speed_multiplier():.2f}",
                    pit=f"{fac.pit_time_bonus():.1f}",
                    spon=f"{fac.sponsor_multiplier():.2f}"),
                  f.small, T.TEXT_DIM, (60, 392))


# ══════════════════════════════════════════════════════════════════════════════
# TRANSFERÊNCIAS
# ══════════════════════════════════════════════════════════════════════════════
class TransferScene(SubScene):
    title = "transfers.title"

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
        self.app.notify(t("transfers.released", name=d.name))

    def _sign(self):
        car = self.app.career
        if len(car.player_team.drivers) >= 2:
            self.app.notify(t("transfers.release_first")); return
        if not self.free:
            self.app.notify(t("transfers.no_free")); return
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
        draw_text(surf, t("transfers.budget", amount=f"{pt.budget:,}".replace(",", ".")),
                  f.h2, T.GOLD, (40, 78))
        panel(surf, (40, 120, 600, 470), T.BG_PANEL)
        draw_text(surf, t("transfers.my_drivers"), f.tiny, T.ACCENT, (60, 132))
        self.my_btns = []
        y = 164
        for d in car.player_drivers():
            mv = driver_market_value(d, car.standings_drivers.get(d.id, 0))
            draw_text(surf, d.name, f.h2, T.TEXT, (60, y))
            contr = t("transfers.contract", n=d.contract_years) if d.contract_years > 0 else t("transfers.expired")
            ovr_val = t("transfers.value", ovr=f"{d.overall:.0f}", val=f"{mv:,}".replace(",", "."))
            draw_text(surf, f"{ovr_val}  ·  {contr}", f.tiny, T.TEXT_DIM, (60, y + 32))
            rb = Button((360, y, 120, 38), t("transfers.renew"), (lambda x=d: self._renew(x)),
                        f.small, kind="ghost")
            lb = Button((490, y, 120, 38), t("transfers.release"), (lambda x=d: self._release(x)),
                        f.small, kind="danger")
            self.my_btns += [rb, lb]; rb.draw(surf); lb.draw(surf)
            y += 80
        panel(surf, (660, 120, T.WIDTH - 660 - 40, 500), T.BG_PANEL)
        draw_text(surf, t("transfers.free_agents"), f.tiny, T.ACCENT, (680, 132))
        self.free_list.draw(surf, f)
        self.sign_btn.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL DO JOGADOR
# ══════════════════════════════════════════════════════════════════════════════
class PerfilScene(SubScene):
    title = "profile.title"
    ROW = 32

    def setup(self):
        self.scroll = 0
        self.visible = (470 - 40) // self.ROW

    def body_handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
            n = len(self.app.profile.history)
            d = -1 if event.button == 4 else 1
            self.scroll = max(0, min(max(0, n - self.visible), self.scroll + d))

    def body(self, surf):
        f = self.app.fonts
        car = self.app.career
        p = self.app.profile
        is_driver = p.mode != "manager"

        # ── Painel esquerdo: identidade + habilidades ────────────────────────
        panel(surf, (40, 110, 560, 540), T.BG_PANEL)
        x = 64
        draw_text(surf, p.name, f.h1, T.TEXT, (x, 126))
        mode_lbl = {"driver": "Piloto", "manager": "Chefe de Equipe",
                    "manager_turned_driver": "Piloto (ex-gerente)"}.get(p.mode, p.mode)
        draw_text(surf, f"{p.age} anos · {p.nationality} · {mode_lbl}",
                  f.small, T.TEXT_DIM, (x, 168))
        # reputação + dinheiro
        draw_text(surf, "REPUTAÇÃO", f.tiny, T.TEXT_DIM, (x, 200))
        draw_text(surf, f"{p.reputation}/100", f.h2, T.ACCENT_2, (x, 218))
        draw_text(surf, "DINHEIRO PESSOAL", f.tiny, T.TEXT_DIM, (x + 220, 200))
        draw_text(surf, f"€ {p.personal_money:,}".replace(",", "."), f.h2, T.GOLD, (x + 220, 218))

        y = 262
        if is_driver and car.player_driver:
            d = car.player_driver
            draw_text(surf, "HABILIDADES", f.tiny, T.ACCENT, (x, y)); y += 24
            w = 500
            for label, val in [("Velocidade", d.speed), ("Consistência", d.consistency),
                               ("Ultrapassagem", d.overtaking), ("Pneus", d.tyre_mgmt),
                               ("Defesa", d.defence), ("Chuva", d.rain), ("Feedback", d.feedback)]:
                y = stat_bar(surf, x, y, w, label, val, color=T.ACCENT, fonts=f) + 10
            y += 6
            # totais de carreira
            tot = [("Vitórias", d.total_wins), ("Pódios", d.total_podiums),
                   ("Corridas", d.races_completed), ("SL", f"{d.super_licence_points}/40")]
            tx = x
            for lab, v in tot:
                box = pygame.Rect(tx, y, 116, 54)
                pygame.draw.rect(surf, T.BG_PANEL_2, box, border_radius=6)
                draw_text(surf, str(v), f.h2, T.TEXT, (box.centerx, box.y + 8), center=True)
                draw_text(surf, lab, f.tiny, T.TEXT_DIM, (box.centerx, box.y + 36), center=True)
                tx += 124
        else:
            draw_text(surf, "RESUMO", f.tiny, T.ACCENT, (x, y)); y += 28
            draw_text(surf, f"Temporadas geridas: {len(p.history)}", f.body, T.TEXT, (x, y)); y += 32
            if car.player_team:
                draw_text(surf, f"Equipe atual: {car.player_team.name}", f.body, T.TEXT, (x, y))

        # ── Painel direito: histórico + equipes/categorias ───────────────────
        rx = 620
        rw = T.WIDTH - rx - 40
        # equipes e categorias passadas
        teams = list(dict.fromkeys(h.team for h in p.history))
        cats = list(dict.fromkeys(h.series for h in p.history))
        panel(surf, (rx, 110, rw, 110), T.BG_PANEL)
        draw_text(surf, "CATEGORIAS", f.tiny, T.ACCENT, (rx + 18, 122))
        cxp = rx + 18
        for c in cats[:6]:
            r = chip(surf, c, (cxp, 144), f.tiny, T.BG, T.ACCENT_2)
            cxp += r.width + 8
        draw_text(surf, "EQUIPES", f.tiny, T.ACCENT, (rx + 18, 176))
        txp = rx + 18
        for tname in teams[:5]:
            r = chip(surf, tname, (txp, 196), f.tiny, T.TEXT, T.BG_PANEL_2)
            txp += r.width + 8
            if txp > rx + rw - 120:
                break

        # histórico (rolável)
        panel(surf, (rx, 230, rw, 420), T.BG_PANEL)
        draw_text(surf, "HISTÓRICO DE CARREIRA", f.tiny, T.ACCENT, (rx + 18, 242))
        draw_text(surf, "ANO", f.tiny, T.TEXT_DIM, (rx + 18, 268))
        draw_text(surf, "CATEGORIA", f.tiny, T.TEXT_DIM, (rx + 80, 268))
        draw_text(surf, "EQUIPE", f.tiny, T.TEXT_DIM, (rx + 300, 268))
        draw_text(surf, "POS", f.tiny, T.TEXT_DIM, (rx + rw - 24, 268), right=True)
        prev = surf.get_clip()
        surf.set_clip(pygame.Rect(rx, 290, rw, 350))
        ry = 296
        hist = list(reversed(self.app.profile.history))
        for h in hist[self.scroll:self.scroll + self.visible + 1]:
            pcol = T.GOLD if h.position == 1 else T.TEXT
            draw_text(surf, str(h.year), f.small, T.TEXT_DIM, (rx + 18, ry))
            draw_text(surf, h.series, f.small, T.TEXT, (rx + 80, ry))
            draw_text(surf, h.team, f.small, T.TEXT_DIM, (rx + 300, ry))
            tag = f"P{h.position}" + ("  ↑" if h.promoted else "")
            draw_text(surf, tag, f.small, pcol, (rx + rw - 24, ry), right=True)
            ry += self.ROW
        if not hist:
            draw_text(surf, t("profile.no_history"), f.small, T.TEXT_DIM, (rx + 18, ry))
        surf.set_clip(prev)


# ══════════════════════════════════════════════════════════════════════════════
# EQUIPE E PILOTOS (info)
# ══════════════════════════════════════════════════════════════════════════════
class TeamInfoScene(SubScene):
    title = "team_info.title"

    def body(self, surf):
        f = self.app.fonts
        tm = self.app.career.player_team
        panel(surf, (40, 110, 560, 510), T.BG_PANEL)
        x = 64
        draw_text(surf, tm.name, f.h1, T.TEXT, (x, 126))
        rows = [(t("team_info.budget"), f"€ {tm.budget:,}".replace(",", ".")),
                (t("team_info.cost_race"), f"€ {tm.base_cost_per_race:,}".replace(",", ".")),
                (t("team_info.reputation"), f"{tm.reputation}/100"),
                (t("team_info.performance"), f"{tm.car_performance:.1f}/100")]
        y = 180
        for lab, val in rows:
            draw_text(surf, lab, f.body, T.TEXT_DIM, (x, y))
            draw_text(surf, val, f.body, T.TEXT, (x + 510, y), right=True)
            y += 38
        draw_text(surf, t("team_info.sponsors"), f.tiny, T.ACCENT, (x, y + 10))
        y += 40
        for sp in tm.sponsors:
            name = sp["name"] if isinstance(sp, dict) else sp.name
            val  = sp["value"] if isinstance(sp, dict) else sp.value
            draw_text(surf, name, f.small, T.TEXT, (x, y))
            draw_text(surf, f"€ {val:,}".replace(",", "."), f.small, T.GOLD, (x + 510, y), right=True)
            y += 30
        panel(surf, (620, 110, T.WIDTH - 620 - 40, 510), T.BG_PANEL)
        draw_text(surf, t("team_info.drivers"), f.tiny, T.ACCENT, (644, 126))
        y = 162
        for d in self.app.career.player_drivers():
            draw_text(surf, d.name, f.h2, T.TEXT, (644, y))
            tags = f"OVR {d.overall:.0f}  ·  Pot {d.potential}  ·  SL {d.super_licence_points}/40"
            draw_text(surf, tags, f.small, T.TEXT_DIM, (644, y + 30))
            extra = f"{t('career.health')} {d.health}%  ·  € {d.salary:,}".replace(",", ".") + f"  ·  {d.contract_years}a"
            if d.is_injured:
                extra += f"  ·  {t('career.injured')} {d.injury_races_remaining}"
            if d.academy_id:
                extra += f"  ·  {d.academy_id.split('_')[0].title()}"
            draw_text(surf, extra, f.tiny, T.TEXT_FAINT, (644, y + 56))
            y += 96


# ══════════════════════════════════════════════════════════════════════════════
# APOSENTAR → GERENTE
# ══════════════════════════════════════════════════════════════════════════════
class RetireScene(SubScene):
    title = "retire.title"

    def setup(self):
        self.series = list(MANAGER_ENTRY_COST.keys())
        self.sel = 0
        self.rects = []
        self.confirm_btn = Button((T.WIDTH - 320, T.HEIGHT - 70, 280, 52),
                                  t("retire.confirm"), self._confirm, self.app.fonts.body,
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
        draw_text(surf, t("retire.money", amount=f"{p.personal_money:,}".replace(",", ".")),
                  f.h2, T.GOLD, (40, 110))
        draw_text(surf, t("retire.choose"), f.body, T.TEXT_DIM, (40, 160))
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
    title = "become_driver.title"
    subtitle = "become_driver.subtitle"

    def setup(self):
        p = self.app.profile
        self.possible = [s for s, lim in DRIVER_AGE_GATE.items()
                         if lim != -1 and p.age <= lim]
        self.sel = 0
        self.rects = []
        self.confirm_btn = Button((T.WIDTH - 300, T.HEIGHT - 70, 260, 52),
                                  t("become_driver.try"), self._confirm, self.app.fonts.body,
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
            txt = t("become_driver.blocked") if lim == -1 else t("become_driver.until_age", age=lim)
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
        car = self.app.career
        p = self.app.profile
        self.is_driver = p.mode != "manager"
        self.forced = self.offer.get("forced", False)
        self.is_not_renewed = self.offer.get("type") == "not_renewed"
        # situação atual
        if self.is_driver and car.player_driver:
            d = car.player_driver
            self.cur_team = car.current_team.name if car.current_team else "—"
            self.cur_series = SERIES_LABEL.get(car.current_series_id, "")
            self.cur_salary = d.salary
            self.cur_years = d.contract_years
        else:
            self.cur_team = car.player_team.name if getattr(car, "player_team", None) else "—"
            self.cur_series = SERIES_LABEL.get(car.current_series_id, "")
            self.cur_salary = 0
            self.cur_years = 1
        # Multa por demissão imediata (equipe → piloto)
        self.firing_penalty = self.offer.get("penalty_to_player", 0)
        # Multa por quebra de contrato (piloto → equipe, ao aceitar via busca de vagas)
        self.breaking_penalty = self.offer.get("breaking_penalty", 0)
        # Compatibilidade com sistema legado
        base_pen = (self.cur_salary * max(1, self.cur_years)) // 2
        self.is_fired_immediate = (self.offer.get("dismissal_type") == "fired")
        self.player_pays = (self.is_driver and not self.forced and not self.is_not_renewed and
                            self.breaking_penalty > 0)
        self.team_pays = self.is_driver and (self.forced or self.is_fired_immediate)
        self.penalty = self.firing_penalty if self.team_pays else self.breaking_penalty

        if self.is_not_renewed:
            yes_lbl = t("common.understood")
        else:
            yes_lbl = t("common.accept")
        self.yes = Button((T.WIDTH // 2 - 230, 600, 200, 54), yes_lbl, self._accept, f.h2,
                          color=T.GREEN if not self.is_not_renewed else T.GOLD, text_color=T.BG)
        self.no = Button((T.WIDTH // 2 + 30, 600, 200, 54), t("common.decline"), self._reject, f.h2,
                         kind="ghost")

    def _accept(self):
        p = self.app.profile
        o = self.offer
        car = self.app.career

        if self.is_not_renewed:
            self.app.notify(t("offer.not_renewed_notify", team=self.cur_team))
            self.app.pop()
            return

        # Demissão imediata: equipe paga multa ao piloto
        if self.team_pays and self.firing_penalty > 0:
            p.receive_salary(self.firing_penalty)
            self.app.notify(t("offer.team_dismisses", amount=f"{self.firing_penalty:,.0f}"))

        # Quebra de contrato: piloto paga multa à equipe
        if self.player_pays and self.breaking_penalty > 0:
            if p.personal_money < self.breaking_penalty:
                self.app.notify(t("offer.insufficient", amount=f"{self.breaking_penalty:,.0f}"))
            p.personal_money -= self.breaking_penalty

        # TROCA IMEDIATA (ano corrente → vale já na próxima corrida):
        #  - demissão (a equipe te dispensa),
        #  - estar sem vaga,
        #  - quebra de contrato com multa paga (você sai para outra equipe agora).
        seatless = self.is_driver and not getattr(car, "has_seat", True)
        immediate = self.is_driver and (self.team_pays or seatless or self.player_pays) and \
            hasattr(car, "sign_midseason")
        if immediate:
            if o["from_series"] == car.current_series_id:
                car.sign_midseason(o["from_team_id"])
            elif hasattr(car, "switch_series_midseason"):
                car.switch_series_midseason(o["from_series"], o["from_team_id"])
            else:
                car.sign_midseason(o["from_team_id"])
            self.app.notify(t("offer.accepted", team=o["from_team"]) + " — vale já!")
            self.app.pop()
            return

        car._pending_offer = o
        if self.is_driver and hasattr(car, "sign_contract"):
            car.sign_contract(o["from_team_id"], o["from_series"])
        self.app.notify(t("offer.accepted", team=o["from_team"]))
        self.app.pop()

    def _reject(self):
        self.app.pop()

    def handle(self, event):
        self.yes.handle(event)
        self.no.handle(event)

    def update(self, dt): ...

    def _column(self, surf, f, x, w, title, tcol, rows):
        panel(surf, (x, 250, w, 300), T.BG_PANEL_2)
        draw_text(surf, title, f.small, tcol, (x + 20, 264))
        pygame.draw.line(surf, T.LINE, (x + 16, 296), (x + w - 16, 296), 1)
        y = 312
        for lab, val, vcol in rows:
            draw_text(surf, lab, f.small, T.TEXT_DIM, (x + 20, y))
            draw_text(surf, val, f.body, vcol, (x + w - 20, y), right=True)
            y += 40

    def draw(self, surf):
        gradient_bg(surf)
        f = self.app.fonts
        o = self.offer
        cx = T.WIDTH // 2
        label = OFFER_TYPE_LABEL.get(o["type"], "PROPOSTA")
        draw_text(surf, label, f.h1, T.ACCENT, (cx, 110), center=True)
        draw_text(surf, o["description"], f.body, T.TEXT, (cx, 165), center=True)

        col_w = 440
        # Coluna A — situação atual
        self._column(surf, f, cx - col_w - 20, col_w, "A · SITUAÇÃO ATUAL", T.TEXT_DIM, [
            ("Equipe", self.cur_team, T.TEXT),
            ("Categoria", self.cur_series, T.TEXT),
            ("Salário", f"€ {self.cur_salary:,}".replace(",", ".") if self.cur_salary else "—", T.TEXT),
            ("Contrato", f"{self.cur_years} ano(s)", T.TEXT),
            ("Multa de saída", f"€ {self.penalty:,}".replace(",", ".") if self.penalty else "—",
             T.RED if self.player_pays else T.TEXT_DIM),
        ])
        # Coluna B — nova proposta (ou situação de não renovação)
        if self.is_not_renewed:
            self._column(surf, f, cx + 20, col_w, "B · SITUAÇÃO", T.RED, [
                ("Status", "Contrato encerra ao fim da temporada", T.RED),
                ("Último dia", "Última corrida desta temporada", T.TEXT),
                ("Recomendação", "Procure nova equipe antes do fim da temporada", T.GOLD),
                ("Multa", "Nenhuma — é não renovação, não demissão", T.TEXT_DIM),
            ])
        else:
            self._column(surf, f, cx + 20, col_w, "B · NOVA PROPOSTA", T.GREEN, [
                ("Equipe", o["from_team"], T.TEXT),
                ("Categoria", o["from_series_label"], T.ACCENT_2),
                ("Salário", f"€ {o['salary']:,}".replace(",", ".") + "/ano", T.GOLD),
                ("Duração", f"{o['years']} ano(s)", T.TEXT),
                ("Função", "Titular", T.TEXT),
            ])

        # faixa da multa
        if self.team_pays and self.penalty:
            msg = f"A equipe te DISPENSA e paga a multa: + € {self.penalty:,}".replace(",", ".")
            mcol = T.GREEN
        elif self.player_pays and self.penalty:
            msg = f"Você rescinde o contrato e paga a multa: − € {self.penalty:,}".replace(",", ".")
            mcol = T.RED
        else:
            msg = "Sem multa (fim de contrato)."
            mcol = T.TEXT_DIM
        draw_text(surf, msg, f.body, mcol, (cx, 566), center=True)

        self.yes.draw(surf)
        self.no.draw(surf)


# ══════════════════════════════════════════════════════════════════════════════
# NOTÍCIAS
# ══════════════════════════════════════════════════════════════════════════════
_NEWS_CAT_COLOR = {
    "race":      T.ACCENT,
    "contract":  T.GOLD,
    "injury":    T.RED,
    "promotion": T.GREEN,
    "market":    T.ACCENT_2,
}
_NEWS_CAT_LABEL = {
    "race":      "CORRIDA",
    "contract":  "CONTRATO",
    "injury":    "LESÃO",
    "promotion": "CARREIRA",
    "market":    "MERCADO",
}


class NewsScene(SubScene):
    title = "news.title"
    ROW_H = 72
    PANEL_Y = 110
    PANEL_H = 540

    def setup(self):
        self.scroll = 0
        car = self.app.career
        feed = getattr(car, "news_feed", [])
        self.items = list(reversed(feed))   # mais recente primeiro
        self.visible = (self.PANEL_H - 10) // self.ROW_H
        self.max_scroll = max(0, len(self.items) - self.visible)

    def body_handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll = max(0, self.scroll - 1)
            elif event.button == 5:
                self.scroll = min(self.max_scroll, self.scroll + 1)

    def body(self, surf):
        f = self.app.fonts
        x, y, w, h = 28, self.PANEL_Y, T.WIDTH - 56, self.PANEL_H
        panel(surf, (x, y, w, h), T.BG_PANEL)
        if not self.items:
            draw_text(surf, t("news.no_news"), f.body, T.TEXT_DIM,
                      (T.WIDTH // 2, y + 80), center=True)
            return
        prev = surf.get_clip()
        surf.set_clip(pygame.Rect(x, y + 4, w, h - 8))
        ry = y + 8
        for item in self.items[self.scroll:self.scroll + self.visible + 1]:
            cat = item.get("category", "race")
            ccol = _NEWS_CAT_COLOR.get(cat, T.TEXT_DIM)
            clbl = _NEWS_CAT_LABEL.get(cat, cat.upper())
            row = pygame.Rect(x + 12, ry, w - 24, self.ROW_H - 4)
            pygame.draw.rect(surf, T.BG_PANEL_2, row, border_radius=6)
            # faixa colorida lateral
            pygame.draw.rect(surf, ccol, (x + 12, ry, 4, self.ROW_H - 4), border_radius=2)
            draw_text(surf, clbl, f.tiny, ccol, (x + 24, ry + 8))
            yr = item.get("year", "")
            rnd = item.get("round", 0)
            meta = f"{yr} · R{rnd}" if rnd else f"{yr}"
            draw_text(surf, meta, f.tiny, T.TEXT_FAINT, (x + w - 30, ry + 8), right=True)
            draw_text(surf, item.get("headline", ""), f.body, T.TEXT, (x + 24, ry + 28))
            ry += self.ROW_H
        surf.set_clip(prev)
        if self.max_scroll > 0:
            th = h - 12
            kh = max(24, int(th * self.visible / max(1, len(self.items))))
            ky = y + 6 + int((th - kh) * self.scroll / self.max_scroll)
            pygame.draw.rect(surf, T.LINE, (x + w - 8, y + 6, 4, th), border_radius=2)
            pygame.draw.rect(surf, T.ACCENT, (x + w - 8, ky, 4, kh), border_radius=2)


# ══════════════════════════════════════════════════════════════════════════════
# MORADIA
# ══════════════════════════════════════════════════════════════════════════════
_STATUS_COLORS = {
    "green":   (80, 220, 100),
    "orange":  (255, 180, 40),
    "red":     (220, 70,  70),
    "current": (100, 180, 255),
}

class HousingScene(SubScene):
    title = "housing.title"

    def setup(self):
        self.selected = None   # key being hovered
        self.message  = ""

    def body_handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for key, rect in self._card_rects.items():
                if rect.collidepoint(mx, my):
                    self._change_housing(key)
                    return

    def _change_housing(self, key):
        profile = self.app.profile
        if profile.housing == key:
            self.message = "Você já mora aqui."
            return
        old = hsng.HOUSING_OPTIONS.get(profile.housing, {}).get("name", profile.housing)
        old_opt = hsng.HOUSING_OPTIONS.get(profile.housing, {})
        new = hsng.HOUSING_OPTIONS.get(key, {}).get("name", key)
        profile.housing = key
        opt = hsng.HOUSING_OPTIONS[key]
        delta_rep = opt["rep_bonus"] - old_opt.get("rep_bonus", 0)
        profile.reputation = max(0, min(100, profile.reputation + delta_rep))
        self.message = f"Mudou de {old} para {new}."

    def body(self, surf):
        f   = self.app.fonts
        p   = self.app.profile
        car = self.app.career

        self._card_rects = {}
        salary = 0
        if hasattr(car, "player_driver") and car.player_driver:
            salary = car.player_driver.salary
        races = len(car.season.rounds) if car.season else 16

        # Título + salário bruto
        draw_text(surf, t("housing.subtitle"), f.small, T.TEXT_DIM, (56, 115))

        card_w, card_h = 340, 210
        cols = 3
        start_x, start_y = 40, 145
        gap_x, gap_y = 20, 16

        for i, (key, opt) in enumerate(hsng.HOUSING_OPTIONS.items()):
            col = i % cols
            row = i // cols
            x = start_x + col * (card_w + gap_x)
            y = start_y + row * (card_h + gap_y)
            rect = pygame.Rect(x, y, card_w, card_h)
            self._card_rects[key] = rect

            is_current = (p.housing == key)
            bd = T.ACCENT if is_current else T.LINE
            bg = T.BG_PANEL_2 if is_current else T.BG_PANEL
            pygame.draw.rect(surf, bg, rect, border_radius=10)
            pygame.draw.rect(surf, bd, rect, 2, border_radius=10)

            # Bandeira + nome
            _HOUSING_CTRY = {"origin": None, "spain": "Spain", "uk": "UK",
                              "italy": "Italy", "switzerland": "Switzerland", "monaco": "Monaco"}
            ctry = _HOUSING_CTRY.get(key)
            if ctry:
                draw_country_flag(surf, x + 14, y + 12, ctry, 40, 26)
            else:
                draw_icon(surf, "home", x + 34, y + 25, 16, T.TEXT_DIM)
            draw_text(surf, opt["name"], f.body, T.TEXT, (x + 64, y + 14))
            if is_current:
                chip(surf, "ATUAL", (x + card_w - 80, y + 14), f.tiny, T.BG, T.ACCENT)

            # Financeiro
            bd_info = hsng.annual_breakdown(salary, key)
            draw_text(surf, t("housing.rent", amount=f"{opt['monthly_cost']:,.0f}"),
                      f.tiny, T.TEXT_DIM, (x + 14, y + 52))
            draw_text(surf, t("housing.tax", pct=f"{opt['tax_rate']*100:.0f}"),
                      f.tiny, T.TEXT_DIM, (x + 14, y + 70))
            net_col = T.ACCENT_2 if bd_info["net"] >= 0 else (220, 70, 70)
            draw_text(surf, t("housing.net", amount=f"{bd_info['net']:,.0f}"),
                      f.small, net_col, (x + 14, y + 88))

            # Bonuses
            bonuses = []
            if opt["rep_bonus"] > 0:
                bonuses.append(f"+{opt['rep_bonus']} rep")
            if opt["xp_bonus"] > 0:
                bonuses.append(f"+{opt['xp_bonus']} XP/corrida")
            if opt["travel_penalty"] > 0:
                bonuses.append(f"-{opt['travel_penalty']} XP viagem")
            draw_text(surf, "  ".join(bonuses) if bonuses else "Sem bônus",
                      f.tiny, T.ACCENT_2, (x + 14, y + 112))

            # Descrição curta (truncada)
            desc = opt["description"]
            if len(desc) > 52:
                desc = desc[:50] + "…"
            draw_text(surf, desc, f.tiny, T.TEXT_DIM, (x + 14, y + 132))

            # Pros (apenas 1 linha)
            if opt.get("pros"):
                draw_text(surf, "✓ " + opt["pros"][0], f.tiny, (100, 210, 100),
                          (x + 14, y + 160))
            if opt.get("cons"):
                draw_text(surf, "✗ " + opt["cons"][0], f.tiny, (220, 100, 100),
                          (x + 14, y + 178))

        # Mensagem de feedback
        if self.message:
            draw_text(surf, self.message, f.body, T.ACCENT_2,
                      (start_x, start_y + 2 * (card_h + gap_y) + 20))


# ══════════════════════════════════════════════════════════════════════════════
# BUSCA DE VAGAS
# ══════════════════════════════════════════════════════════════════════════════
class JobSearchScene(SubScene):
    title = "job_search.title"

    ROW_H = 54

    def setup(self):
        self.scroll   = 0
        self.message  = ""
        self._vacancies: list = []
        self._btn_rects: dict = {}
        self._refresh()

    def _refresh(self):
        try:
            self._vacancies = build_vacancy_list(self.app.career)
        except Exception as e:
            self._vacancies = []
            self.message = f"Erro ao carregar vagas: {e}"

    def body_handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button in (4, 5):
                n   = len(self._vacancies)
                vis = (T.HEIGHT - 220) // self.ROW_H
                d   = -1 if event.button == 4 else 1
                self.scroll = max(0, min(max(0, n - vis), self.scroll + d))
            elif event.button == 1:
                mx, my = event.pos
                for idx, rect in self._btn_rects.items():
                    if rect.collidepoint(mx, my):
                        self._apply(idx)
                        return

    def _apply(self, idx: int):
        entry = self._vacancies[idx]
        if entry["status"] not in ("green", "orange"):
            self.message = "Esta vaga não está disponível para candidatura."
            return
        # Avisa sobre multa
        penalty = entry.get("penalty", 0)
        offer = apply_to_team(self.app.career,
                              entry["team"].id, entry["series_id"])
        if offer is None:
            self.message = f"{entry['team'].name} recusou sua candidatura. Tente outra equipe."
            return
        # Se tem multa e o piloto vai aceitar, debitamos na OfferScene
        self.app.push(OfferScene(self.app, offer))

    def body(self, surf):
        f   = self.app.fonts
        p   = self.app.profile
        car = self.app.career

        self._btn_rects = {}

        pd = getattr(car, "player_driver", None)
        penalty_base = car.breaking_contract_penalty() if hasattr(car, "breaking_contract_penalty") else 0

        # Cabeçalho
        draw_text(surf, t("job_search.hint"), f.tiny, T.TEXT_DIM, (56, 108))
        if penalty_base > 0:
            draw_text(surf,
                f"⚠ Multa por quebra de contrato: €{penalty_base:,.0f} (debitado ao aceitar)",
                f.small, (255, 180, 40), (56, 126))

        # Colunas
        cx = [56, 56+200, 56+200+180, 56+200+180+160, T.WIDTH - 200]
        hy = 148
        for lbl, x in zip(["SÉRIE", "EQUIPE", "DESEMPENHO", "VAGA", "STATUS"], cx):
            draw_text(surf, lbl, f.tiny, T.TEXT_DIM, (x, hy))

        vis  = (T.HEIGHT - 230) // self.ROW_H
        rows = self._vacancies[self.scroll: self.scroll + vis]

        prev = surf.get_clip()
        surf.set_clip(pygame.Rect(40, 162, T.WIDTH - 80, T.HEIGHT - 230))

        self._btn_rects = {}
        for i, entry in enumerate(rows):
            global_idx = i + self.scroll
            y = 162 + i * self.ROW_H
            bg = T.BG_PANEL if i % 2 == 0 else T.BG_PANEL_2
            pygame.draw.rect(surf, bg, (40, y, T.WIDTH - 80, self.ROW_H - 2))

            st  = entry["status"]
            col = _STATUS_COLORS.get(st, T.TEXT_DIM)

            # Série (badge colorido)
            chip(surf, entry["series_label"], (cx[0], y + 10), f.tiny,
                 T.BG, col)
            # Equipe
            draw_text(surf, entry["team"].name, f.small, T.TEXT, (cx[1], y + 12))
            draw_text(surf, f"Rep:{entry['team'].reputation}",
                      f.tiny, T.TEXT_DIM, (cx[1], y + 30))
            # Score vs threshold
            sc = entry["score"]
            th = entry["team_threshold"]
            bar_w = 120
            pct = min(1.0, sc / max(1, th))
            bar_col = col
            pygame.draw.rect(surf, T.BG,       (cx[2], y + 18, bar_w, 10), border_radius=4)
            pygame.draw.rect(surf, bar_col,    (cx[2], y + 18, int(bar_w*pct), 10), border_radius=4)
            draw_text(surf, f"{sc:.0f}/{th:.0f}", f.tiny, T.TEXT_DIM, (cx[2], y + 30))
            # Vagas
            draw_text(surf, entry["vacancy_label"], f.small, T.TEXT, (cx[3], y + 14))
            # Botão / status
            if st in ("green", "orange") and not entry["is_my_team"]:
                btn_r = pygame.Rect(cx[4], y + 8, 140, 34)
                btn_col = (60, 180, 80) if st == "green" else (200, 140, 30)
                pygame.draw.rect(surf, btn_col, btn_r, border_radius=6)
                draw_text(surf, "CANDIDATAR", f.small, T.BG,
                          (btn_r.centerx, btn_r.centery - 7), center=True)
                self._btn_rects[global_idx] = btn_r
            elif entry["is_my_team"]:
                draw_text(surf, "SUA EQUIPE", f.small, _STATUS_COLORS["current"],
                          (cx[4], y + 14))
            else:
                draw_text(surf, entry["reason"][:28], f.tiny, T.TEXT_DIM, (cx[4], y + 14))

        surf.set_clip(prev)

        # Mensagem de feedback
        if self.message:
            draw_text(surf, self.message, f.small, T.ACCENT_2,
                      (56, T.HEIGHT - 155))


# ══════════════════════════════════════════════════════════════════════════════
# NEGOCIAR COM EQUIPE ATUAL
# ══════════════════════════════════════════════════════════════════════════════
class NegociarEquipeScene(SubScene):
    title = "negotiate.title"

    def setup(self):
        f = self.app.fonts
        car = self.app.career
        self._rebuild_buttons(f, car)

    def _rebuild_buttons(self, f, car):
        pd = car.player_driver if hasattr(car, "player_driver") else None
        self.penalty = car.breaking_contract_penalty() if hasattr(car, "breaking_contract_penalty") else 0
        self.can_afford = self.app.profile.personal_money >= self.penalty or self.penalty == 0
        self.free_agent_set = getattr(car, "_free_agent_next_season", False)

        cx = T.WIDTH // 2
        self.now_btn = Button(
            (cx - 360, 490, 320, 56), t("negotiate.btn_now"),
            self._transfer_now, f.body,
            color=T.RED, text_color=T.TEXT)
        self.now_btn.enabled = self.can_afford and not car.season_complete()

        self.end_btn = Button(
            (cx + 40, 490, 320, 56), t("negotiate.btn_end"),
            self._transfer_end, f.body, kind="ghost")
        self.end_btn.enabled = not self.free_agent_set

    def _transfer_now(self):
        car = self.app.career
        p = self.app.profile
        if self.penalty > 0:
            p.personal_money -= self.penalty
            self.app.notify(t("negotiate.penalty_paid", amount=f"{self.penalty:,.0f}"))
        # Player is free to search — pending offer will be applied at season end
        self.app.replace(JobSearchScene(self.app))

    def _transfer_end(self):
        car = self.app.career
        car._free_agent_next_season = True
        self.free_agent_set = True
        self.app.notify(t("negotiate.notify_end"))
        f = self.app.fonts
        self._rebuild_buttons(f, car)
        self.app.pop()

    def body_handle(self, event):
        self.now_btn.handle(event)
        self.end_btn.handle(event)

    def body(self, surf):
        f = self.app.fonts
        car = self.app.career
        p = self.app.profile
        pd = car.player_driver if hasattr(car, "player_driver") else None
        cx = T.WIDTH // 2

        # Painel: contrato atual
        panel(surf, (cx - 400, 90, 800, 170), T.BG_PANEL)
        draw_text(surf, t("negotiate.current_contract"), f.tiny, T.ACCENT, (cx - 380, 102))
        team_name = car.current_team.name if car.current_team else "—"
        series    = SERIES_LABEL.get(car.current_series_id, "")
        col_data = [
            (t("negotiate.col_team"),     team_name,                                         T.TEXT),
            (t("negotiate.col_category"), series,                                            T.TEXT),
            (t("negotiate.col_salary"),   f"€ {pd.salary:,}".replace(",", ".") if pd else "—", T.GOLD),
            (t("negotiate.col_remaining"), f"{pd.contract_years} " + t("common.years", n="") if pd else "—", T.TEXT_DIM),
        ]
        bx = cx - 380
        for i, (lbl, val, vcol) in enumerate(col_data):
            ox = bx + (i % 2) * 390
            oy = 126 + (i // 2) * 54
            draw_text(surf, lbl, f.tiny, T.TEXT_DIM, (ox, oy))
            draw_text(surf, val, f.body, vcol, (ox, oy + 18))

        pen_col = T.GREEN if self.can_afford else T.RED
        panel(surf, (cx - 400, 272, 800, 90), T.BG_PANEL_2)
        draw_text(surf, t("negotiate.penalty_title"), f.tiny, T.TEXT_DIM, (cx - 380, 284))
        if self.penalty > 0:
            draw_text(surf, f"€ {self.penalty:,}".replace(",", "."), f.h2, pen_col, (cx - 380, 302))
            saldo = p.personal_money - self.penalty
            if self.can_afford:
                status = t("negotiate.balance_after", amount=f"{saldo:,}".replace(",", "."))
            else:
                status = t("negotiate.no_balance")
            draw_text(surf, status, f.small, pen_col, (cx + 80, 310))
        else:
            draw_text(surf, t("negotiate.no_penalty"), f.body, T.TEXT_DIM, (cx - 380, 302))

        cost_str = t("negotiate.opt_a_cost", amount=f"{self.penalty:,}".replace(",", ".")) if self.can_afford else \
                   t("negotiate.opt_a_no_balance", amount=f"{self.penalty:,}".replace(",", "."))
        for ox, title, desc1, desc2 in [
            (cx - 400, t("negotiate.opt_a_title"),
             t("negotiate.opt_a_desc1"), cost_str),
            (cx + 40,  t("negotiate.opt_b_title"),
             t("negotiate.opt_b_desc1"), t("negotiate.opt_b_desc2")),
        ]:
            panel(surf, (ox, 374, 360, 106), T.BG_PANEL)
            draw_text(surf, title, f.tiny, T.ACCENT, (ox + 16, 386))
            draw_text(surf, desc1, f.small, T.TEXT_DIM, (ox + 16, 406))
            draw_text(surf, desc2, f.tiny, T.TEXT_FAINT, (ox + 16, 428))

        if self.free_agent_set:
            draw_text(surf, t("negotiate.free_active"), f.body, T.GOLD, (cx, 460), center=True)

        self.now_btn.draw(surf)
        self.end_btn.draw(surf)


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
                          t("clt.back"), lambda: self.app.reset_to(MenuScene(self.app)),
                          f.h2, kind="ghost")

    def handle(self, event):
        self.btn.handle(event)

    def update(self, dt): ...

    def draw(self, surf):
        surf.fill((20, 8, 10))
        f = self.app.fonts
        cx = T.WIDTH // 2
        draw_text(surf, t("clt.title"), f.title, T.RED, (cx, 160), center=True)
        draw_text(surf, t("clt.out"), f.h2, T.TEXT, (cx, 240), center=True)
        msg_key = CLT_MSG_KEYS.get(self.series_id, "clt.formula_4")
        panel(surf, (cx - 400, 300, 800, 120), T.BG_PANEL, border=T.RED, border_w=2)
        draw_text(surf, t(msg_key), f.body, T.GOLD, (cx, 360), center=True)
        y = 460
        draw_text(surf, t("clt.history"), f.tiny, T.TEXT_DIM, (cx, y), center=True)
        y += 26
        for h in self.app.profile.history[-6:]:
            draw_text(surf, f"{h.year}   {h.series}   P{h.position}", f.small, T.TEXT_DIM,
                      (cx, y), center=True)
            y += 24
        self.btn.draw(surf)
