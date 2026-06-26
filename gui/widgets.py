"""
Widgets reutilizáveis desenhados em pygame: painéis, botões, barras, inputs, tabelas.
Todos os desenhos usam o tema de gui/theme.py.
"""
import pygame
from . import theme as T


def soft_rect(surf, rect, color, radius=8, width=0):
    """Rounded rectangle with smoother edges than pygame's direct draw."""
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return rect
    scale = 3
    layer = pygame.Surface((rect.w * scale, rect.h * scale), pygame.SRCALPHA)
    col = color if len(color) == 4 else (*color, 255)
    pygame.draw.rect(
        layer,
        col,
        layer.get_rect(),
        width=width * scale,
        border_radius=max(0, radius * scale),
    )
    layer = pygame.transform.smoothscale(layer, rect.size)
    surf.blit(layer, rect.topleft)
    return rect


def draw_text(surf, text, font, color, pos, center=False, right=False):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    elif right:
        rect.topright = pos
    else:
        rect.topleft = pos
    surf.blit(img, rect)
    return rect


def panel(surf, rect, color=T.BG_PANEL, radius=12, border=None, border_w=1):
    rect = pygame.Rect(rect)
    soft_rect(surf, rect, color, radius=radius)
    # subtle 1-pixel top-edge highlight for depth
    hi = T.lerp(color, (255, 255, 255), 0.07)
    pygame.draw.line(surf, hi, (rect.x + radius, rect.y + 1), (rect.right - radius, rect.y + 1), 1)
    if border:
        soft_rect(surf, rect, border, radius=radius, width=border_w)
    return rect


def accent_strip(surf, rect, color=T.ACCENT, radius=12):
    """Painel com faixa de acento à esquerda."""
    rect = pygame.Rect(rect)
    panel(surf, rect, radius=radius)
    soft_rect(surf, (rect.x, rect.y, 6, rect.height), color, radius=min(radius, 6))


def stat_bar(surf, x, y, w, label, value, maxv=99, color=T.ACCENT, fonts=None, anim=1.0):
    """Barra horizontal de atributo com rótulo e valor. anim escala o preenchimento."""
    draw_text(surf, label.upper(), fonts.tiny, T.TEXT_DIM, (x, y))
    draw_text(surf, int(value * anim + 0.5), fonts.small, T.TEXT, (x + w, y - 2), right=True)
    by = y + 18
    pygame.draw.rect(surf, T.BG_INPUT, (x, by, w, 9), border_radius=5)
    frac = max(0.0, min(1.0, value / maxv)) * max(0.0, min(1.0, anim))
    if frac > 0.002:
        c = T.GOLD if value >= 80 else color
        fw = max(5, int(w * frac))
        pygame.draw.rect(surf, c, (x, by, fw, 9), border_radius=5)
        # inner highlight line at top of filled bar
        hi = T.lerp(c, (255, 255, 255), 0.35)
        pygame.draw.line(surf, hi, (x + 3, by + 1), (x + fw - 3, by + 1), 1)
    return by + 9


def draw_icon(surf, name, cx, cy, size, color):
    """Desenha ícones vetoriais simples (sem depender de fontes com emoji)."""
    s = size
    if name == "play":
        pygame.draw.polygon(surf, color, [(cx - s*0.4, cy - s*0.55),
                                          (cx - s*0.4, cy + s*0.55),
                                          (cx + s*0.6, cy)])
    elif name == "save":
        r = pygame.Rect(cx - s*0.55, cy - s*0.55, s*1.1, s*1.1)
        pygame.draw.rect(surf, color, r, width=2, border_radius=3)
        pygame.draw.rect(surf, color, (cx - s*0.25, cy - s*0.55, s*0.5, s*0.4))
        pygame.draw.rect(surf, color, (cx - s*0.35, cy + s*0.05, s*0.7, s*0.5), width=2)
    elif name == "menu":
        for i in range(3):
            y = cy - s*0.4 + i * s*0.4
            pygame.draw.line(surf, color, (cx - s*0.5, y), (cx + s*0.5, y), 2)
    elif name == "dev":  # chave de boca
        pygame.draw.line(surf, color, (cx - s*0.5, cy + s*0.5),
                         (cx + s*0.25, cy - s*0.25), 3)
        pygame.draw.circle(surf, color, (int(cx + s*0.4), int(cy - s*0.4)), int(s*0.28), 2)
    elif name == "transfer":  # setas opostas
        pygame.draw.line(surf, color, (cx - s*0.5, cy - s*0.2), (cx + s*0.5, cy - s*0.2), 2)
        pygame.draw.polygon(surf, color, [(cx + s*0.5, cy - s*0.45), (cx + s*0.5, cy + 0.05*s), (cx + s*0.75, cy - s*0.2)])
        pygame.draw.line(surf, color, (cx + s*0.5, cy + s*0.3), (cx - s*0.5, cy + s*0.3), 2)
        pygame.draw.polygon(surf, color, [(cx - s*0.5, cy + s*0.05), (cx - s*0.5, cy + s*0.55), (cx - s*0.75, cy + s*0.3)])
    elif name == "team":  # duas cabeças
        pygame.draw.circle(surf, color, (int(cx - s*0.3), int(cy - s*0.2)), int(s*0.22), 2)
        pygame.draw.arc(surf, color, (cx - s*0.6, cy + s*0.05, s*0.6, s*0.6), 3.14, 6.28, 2)
        pygame.draw.circle(surf, color, (int(cx + s*0.3), int(cy - s*0.2)), int(s*0.22), 2)
        pygame.draw.arc(surf, color, (cx, cy + s*0.05, s*0.6, s*0.6), 3.14, 6.28, 2)
    elif name == "star":
        import math
        pts = []
        for i in range(10):
            ang = -math.pi/2 + i * math.pi/5
            rr = s*0.55 if i % 2 == 0 else s*0.24
            pts.append((cx + rr*math.cos(ang), cy + rr*math.sin(ang)))
        pygame.draw.polygon(surf, color, pts, 2)
    elif name == "cap":  # capelo academia
        pygame.draw.polygon(surf, color, [(cx, cy - s*0.45), (cx + s*0.6, cy - s*0.1),
                                          (cx, cy + s*0.2), (cx - s*0.6, cy - s*0.1)], 2)
        pygame.draw.line(surf, color, (cx + s*0.45, cy - s*0.18), (cx + s*0.45, cy + s*0.35), 2)
    elif name == "door":  # aposentar
        pygame.draw.rect(surf, color, (cx - s*0.4, cy - s*0.55, s*0.8, s*1.1), 2)
        pygame.draw.circle(surf, color, (int(cx + s*0.2), int(cy)), 2)
    elif name == "helmet":
        pygame.draw.circle(surf, color, (int(cx), int(cy - s*0.05)), int(s*0.5), 2)
        pygame.draw.line(surf, color, (cx - s*0.45, cy + s*0.1), (cx + s*0.45, cy + s*0.1), 2)
    elif name == "chart":
        pygame.draw.line(surf, color, (cx - s*0.5, cy + s*0.5), (cx + s*0.5, cy + s*0.5), 2)
        for i, hh in enumerate([0.3, 0.6, 0.45]):
            bx = cx - s*0.35 + i * s*0.35
            pygame.draw.rect(surf, color, (bx, cy + s*0.5 - s*hh, s*0.2, s*hh))
    elif name == "home":  # casa
        # telhado (triângulo)
        pygame.draw.polygon(surf, color, [
            (cx, cy - s*0.55), (cx - s*0.55, cy - s*0.05), (cx + s*0.55, cy - s*0.05)], 2)
        # paredes
        pygame.draw.rect(surf, color, (cx - s*0.35, cy - s*0.05, s*0.7, s*0.6), 2)
        # porta
        pygame.draw.rect(surf, color, (cx - s*0.12, cy + s*0.1, s*0.24, s*0.45))


def draw_flag(surf, x, y, cell=7, cols=4, rows=3, color=(235, 235, 240), pole=True):
    """Bandeira quadriculada (xadrez) com mastro. (x, y) é o topo-esquerda do pano."""
    if pole:
        pygame.draw.line(surf, T.TEXT_DIM, (x, y - 2), (x, y + rows * cell + 4), 2)
        x += 3
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 0:
                pygame.draw.rect(surf, color,
                                 (x + c * cell, y + r * cell, cell, cell))
    pygame.draw.rect(surf, T.LINE, (x, y, cols * cell, rows * cell), width=1)
    return cols * cell


# ── Bandeiras nacionais simplificadas ─────────────────────────────────────────
_FC = {
    "white": (245, 245, 245), "red": (206, 17, 38), "blue": (0, 45, 116),
    "green": (0, 120, 60), "yellow": (255, 205, 0), "black": (24, 24, 28),
    "maroon": (122, 0, 25), "ltblue": (0, 102, 178), "darkgreen": (0, 100, 70),
}


def _bands(surf, x, y, w, h, colors, vertical, weights=None):
    n = len(colors)
    weights = weights or [1] * n
    tot = sum(weights)
    off = 0
    for col, wt in zip(colors, weights):
        seg = (w if vertical else h) * wt / tot
        if vertical:
            pygame.draw.rect(surf, _FC[col], (x + off, y, seg + 1, h))
        else:
            pygame.draw.rect(surf, _FC[col], (x, y + off, w, seg + 1))
        off += seg


# spec: ("v"/"h", [cores], [pesos opcionais])  ou  nome especial
_FLAGS = {
    "France": ("v", ["blue", "white", "red"]),
    "Italy": ("v", ["green", "white", "red"]),
    "Belgium": ("v", ["black", "yellow", "red"]),
    "Mexico": ("v", ["green", "white", "red"]),
    "Germany": ("h", ["black", "red", "yellow"]),
    "Netherlands": ("h", ["red", "white", "blue"]),
    "Hungary": ("h", ["red", "white", "green"]),
    "Austria": ("h", ["red", "white", "red"]),
    "Spain": ("h", ["red", "yellow", "red"], [1, 2, 1]),
    "Azerbaijan": ("h", ["ltblue", "red", "green"]),
    "Monaco":       ("h", ["red", "white"]),
    "Switzerland":  None,  # drawn as special case
    "Bahrain": ("v", ["white", "maroon"], [1, 3]),
    "Qatar": ("v", ["white", "maroon"], [1, 4]),
}


def draw_country_flag(surf, x, y, country, w=34, h=22):
    """Desenha uma bandeira nacional simplificada. (x, y) = topo-esquerda."""
    if country == "Switzerland":
        pygame.draw.rect(surf, _FC["red"], (x, y, w, h))
        cx_, cy_ = x + w // 2, y + h // 2
        arm = max(2, h // 4)
        thick = max(2, h // 5)
        pygame.draw.rect(surf, _FC["white"], (cx_ - thick, cy_ - arm, thick * 2, arm * 2))
        pygame.draw.rect(surf, _FC["white"], (cx_ - arm, cy_ - thick, arm * 2, thick * 2))
        pygame.draw.rect(surf, (60, 62, 80), (x, y, w, h), width=1)
        return w
    spec = _FLAGS.get(country)
    if spec:
        orient = spec[0]
        _bands(surf, x, y, w, h, spec[1], orient == "v",
               spec[2] if len(spec) > 2 else None)
    elif country == "Japan":
        pygame.draw.rect(surf, _FC["white"], (x, y, w, h))
        pygame.draw.circle(surf, _FC["red"], (int(x + w / 2), int(y + h / 2)), int(h * 0.32))
    elif country == "China":
        pygame.draw.rect(surf, _FC["red"], (x, y, w, h))
        pygame.draw.circle(surf, _FC["yellow"], (int(x + w * 0.22), int(y + h * 0.32)), 3)
        for dx, dy in [(0.40, 0.18), (0.46, 0.34), (0.46, 0.55), (0.40, 0.70)]:
            pygame.draw.circle(surf, _FC["yellow"], (int(x + w * dx), int(y + h * dy)), 1)
    elif country == "Brazil":
        pygame.draw.rect(surf, _FC["green"], (x, y, w, h))
        cx, cy = x + w / 2, y + h / 2
        pygame.draw.polygon(surf, _FC["yellow"],
                            [(cx, y + 2), (x + w - 3, cy), (cx, y + h - 2), (x + 3, cy)])
        pygame.draw.circle(surf, _FC["blue"], (int(cx), int(cy)), int(h * 0.20))
    elif country == "Canada":
        pygame.draw.rect(surf, _FC["white"], (x, y, w, h))
        pygame.draw.rect(surf, _FC["red"], (x, y, w * 0.25, h))
        pygame.draw.rect(surf, _FC["red"], (x + w * 0.75, y, w * 0.25, h))
        pygame.draw.rect(surf, _FC["red"], (int(x + w * 0.45), int(y + h * 0.35), int(w * 0.1), int(h * 0.3)))
    elif country == "USA":
        for i in range(7):
            col = "red" if i % 2 == 0 else "white"
            pygame.draw.rect(surf, _FC[col], (x, y + i * h / 7, w, h / 7 + 1))
        pygame.draw.rect(surf, _FC["blue"], (x, y, w * 0.42, h * 0.55))
    elif country in ("UK", "Australia", "Singapore"):
        # base azul com cruz branca/vermelha (aproximação do Union/azul)
        pygame.draw.rect(surf, _FC["blue"], (x, y, w, h))
        pygame.draw.line(surf, _FC["white"], (x, y + h / 2), (x + w, y + h / 2), 4)
        pygame.draw.line(surf, _FC["white"], (x + w / 2, y), (x + w / 2, y + h), 4)
        pygame.draw.line(surf, _FC["red"], (x, y + h / 2), (x + w, y + h / 2), 2)
        pygame.draw.line(surf, _FC["red"], (x + w / 2, y), (x + w / 2, y + h), 2)
        if country == "Singapore":
            pygame.draw.rect(surf, _FC["red"], (x, y, w, h / 2))
            pygame.draw.rect(surf, _FC["white"], (x, y + h / 2, w, h / 2))
            pygame.draw.circle(surf, _FC["white"], (int(x + w * 0.25), int(y + h * 0.25)), 4)
    elif country == "Saudi Arabia":
        pygame.draw.rect(surf, _FC["darkgreen"], (x, y, w, h))
        pygame.draw.line(surf, _FC["white"], (x + 4, y + h - 5), (x + w - 4, y + h - 5), 2)
    elif country == "UAE":
        pygame.draw.rect(surf, _FC["red"], (x, y, w * 0.28, h))
        _bands(surf, x + w * 0.28, y, w * 0.72, h, ["green", "white", "black"], False)
    elif country == "Qatar":
        _bands(surf, x, y, w, h, ["white", "maroon"], True, [1, 4])
    else:
        # genérica: bandeira quadriculada
        draw_flag(surf, x, y, cell=max(4, h // 3), cols=3, rows=3, pole=False)
        return w
    pygame.draw.rect(surf, (60, 62, 80), (x, y, w, h), width=1)
    return w


ICON_NAMES = {"play","save","menu","dev","transfer","team","star","cap","door","helmet","chart","home"}


class Button:
    def __init__(self, rect, label, callback, font=None,
                 color=T.ACCENT, text_color=(15, 14, 23), kind="primary", icon=""):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.font = font
        self.color = color
        self.text_color = text_color
        self.kind = kind        # primary | ghost | danger
        self.icon = icon
        self.hover = False
        self.enabled = True
        self.anim = 0.0         # easing do hover (0..1)

    def handle(self, event):
        if not self.enabled:
            return
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.callback()

    def draw(self, surf):
        # easing do hover
        target = 1.0 if (self.hover and self.enabled) else 0.0
        self.anim += (target - self.anim) * 0.25
        lift = int(self.anim * 2)
        rect = self.rect.move(0, -lift)
        if self.kind == "primary":
            base = self.color
            if not self.enabled:
                base = T.LINE
            else:
                base = T.lerp(self.color, (255, 255, 255), 0.18 * self.anim)
                # glow
                if self.anim > 0.02:
                    glow = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
                    soft_rect(glow, glow.get_rect(), (*self.color, int(70 * self.anim)), radius=14)
                    surf.blit(glow, (rect.x - 8, rect.y - 8))
            soft_rect(surf, rect, base, radius=8)
            tc = self.text_color if self.enabled else T.TEXT_FAINT
        else:
            base = T.BG_PANEL_2 if self.kind == "ghost" else (60, 25, 30)
            edge = T.LINE if self.kind == "ghost" else T.RED
            if self.enabled:
                base = T.lerp(base, (255, 255, 255), 0.12 * self.anim)
                edge = T.lerp(edge, T.ACCENT if self.kind == "ghost" else (255, 120, 130),
                              self.anim)
            soft_rect(surf, rect, base, radius=8)
            soft_rect(surf, rect, edge, radius=8, width=1)
            tc = T.TEXT if self.enabled else T.TEXT_FAINT
        self.rect_draw = rect
        # Ícone vetorial à esquerda do texto (se for um nome conhecido)
        if self.icon in ICON_NAMES:
            tw = self.font.size(self.label)[0]
            isz = self.font.get_height() * 0.7
            gap = 10
            total = isz + gap + tw
            ix = rect.centerx - total / 2 + isz / 2
            draw_icon(surf, self.icon, ix, rect.centery, isz, tc)
            draw_text(surf, self.label, self.font, tc,
                      (ix + isz / 2 + gap, rect.centery - self.font.get_height() // 2))
        else:
            label = (self.icon + "  " + self.label) if self.icon else self.label
            draw_text(surf, label, self.font, tc, rect.center, center=True)


class TextInput:
    def __init__(self, rect, font, placeholder="", max_len=24, numeric=False):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.text = ""
        self.placeholder = placeholder
        self.max_len = max_len
        self.numeric = numeric
        self.active = False
        self._blink = 0

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB):
                self.active = False
            elif len(self.text) < self.max_len:
                ch = event.unicode
                if ch and (not self.numeric or ch.isdigit()):
                    self.text += ch

    def value(self):
        return self.text.strip()

    def draw(self, surf):
        self._blink = (self._blink + 1) % 60
        border = T.ACCENT if self.active else T.LINE
        soft_rect(surf, self.rect, T.BG_INPUT, radius=7)
        soft_rect(surf, self.rect, border, radius=7, width=2)
        if self.text:
            draw_text(surf, self.text, self.font, T.TEXT,
                      (self.rect.x + 12, self.rect.centery - self.font.get_height() // 2))
        else:
            draw_text(surf, self.placeholder, self.font, T.TEXT_FAINT,
                      (self.rect.x + 12, self.rect.centery - self.font.get_height() // 2))
        if self.active and self._blink < 30:
            tw = self.font.size(self.text)[0]
            cx = self.rect.x + 12 + tw + 2
            pygame.draw.line(surf, T.TEXT, (cx, self.rect.y + 8),
                             (cx, self.rect.bottom - 8), 2)


class SelectList:
    """Lista vertical selecionável (ex.: escolher equipe)."""
    def __init__(self, rect, items, font, row_h=46, render_row=None):
        self.rect = pygame.Rect(rect)
        self.items = items            # lista de objetos
        self.font = font
        self.row_h = row_h
        self.selected = 0
        self.scroll = 0
        self.render_row = render_row  # fn(surf, item, row_rect, selected, fonts)
        self.hover_idx = -1

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover_idx = self._index_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                idx = self._index_at(event.pos)
                if idx is not None:
                    self.selected = idx
            elif event.button == 4:
                self.scroll = max(0, self.scroll - 1)
            elif event.button == 5:
                maxs = max(0, len(self.items) - self._visible_rows())
                self.scroll = min(maxs, self.scroll + 1)

    def _visible_rows(self):
        return self.rect.height // self.row_h

    def _index_at(self, pos):
        if not self.rect.collidepoint(pos):
            return None
        rel = pos[1] - self.rect.y
        idx = self.scroll + rel // self.row_h
        return idx if 0 <= idx < len(self.items) else None

    def current(self):
        return self.items[self.selected] if self.items else None

    def draw(self, surf, fonts):
        prev = surf.get_clip()
        surf.set_clip(self.rect)
        vis = self._visible_rows()
        for i in range(self.scroll, min(len(self.items), self.scroll + vis)):
            y = self.rect.y + (i - self.scroll) * self.row_h
            row = pygame.Rect(self.rect.x, y, self.rect.width, self.row_h - 4)
            if i == self.selected:
                soft_rect(surf, row, T.BG_PANEL_2, radius=7)
                soft_rect(surf, row, T.ACCENT, radius=7, width=2)
            elif i == self.hover_idx:
                soft_rect(surf, row, T.BG_PANEL, radius=7)
            if self.render_row:
                self.render_row(surf, self.items[i], row, i == self.selected, fonts)
            else:
                draw_text(surf, str(self.items[i]), self.font, T.TEXT,
                          (row.x + 10, row.centery - 10))
        surf.set_clip(prev)


def chip(surf, text, pos, font, fg, bg, padx=10, pady=4):
    w = font.size(text)[0] + padx * 2
    h = font.get_height() + pady * 2
    rect = pygame.Rect(pos[0], pos[1], w, h)
    soft_rect(surf, rect, bg, radius=h // 2)
    draw_text(surf, text, font, fg, rect.center, center=True)
    return rect
