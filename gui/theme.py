"""
Tema visual do Motorsport Dynasty Manager — cores, fontes e métricas.
Paleta dark com acento laranja (inspirada em paddock noturno).
"""
import pygame

# ── Paleta ────────────────────────────────────────────────────────────────────
BG          = (15, 14, 23)      # fundo principal
BG_PANEL    = (26, 26, 46)      # painéis
BG_PANEL_2  = (22, 33, 62)      # painéis secundários
BG_INPUT    = (10, 10, 21)
LINE        = (45, 45, 70)

ACCENT      = (255, 137, 6)     # laranja
ACCENT_DK   = (200, 100, 0)
ACCENT_2    = (102, 192, 244)   # azul claro
GOLD        = (249, 199, 79)
GREEN       = (63, 185, 80)
RED         = (233, 69, 96)
PURPLE      = (203, 166, 247)

TEXT        = (242, 244, 250)
TEXT_DIM    = (188, 194, 210)   # mais claro p/ legibilidade em fundo escuro
TEXT_FAINT  = (140, 146, 164)

# Cores por categoria
SERIES_COLOR = {
    "formula_4":        (120, 200, 120),
    "formula_regional": (102, 192, 244),
    "formula_3":        (203, 166, 247),
    "formula_2":        (249, 199, 79),
    "formula_1":        (233, 69, 96),
}

# Tela virtual de desenho (todas as coordenadas das cenas usam isto).
# A janela real pode ter qualquer resolução; a App escala a tela virtual.
WIDTH, HEIGHT = 1280, 720
FPS = 60

# Resoluções de janela disponíveis (label, largura, altura, fullscreen)
RESOLUTIONS = [
    ("1280×720",   1280, 720,  False),
    ("1600×900",   1600, 900,  False),
    ("Full HD",    1920, 1080, False),
    ("2K (QHD)",   2560, 1440, False),
    ("4K UHD",     3840, 2160, False),
    ("Tela Cheia",    0,    0,  True),
]


class Fonts:
    """Carrega fontes uma vez após pygame.init()."""
    def __init__(self):
        # Tenta fontes comuns no Windows; cai pra default se faltar
        self.title  = self._load(["Bahnschrift", "Arial Black", "Impact"], 56, bold=True)
        self.h1     = self._load(["Bahnschrift", "Segoe UI", "Arial"], 34, bold=True)
        self.h2     = self._load(["Segoe UI Semibold", "Segoe UI", "Arial"], 24, bold=True)
        self.body   = self._load(["Segoe UI", "Arial"], 19)
        self.small  = self._load(["Segoe UI", "Arial"], 16)
        self.tiny   = self._load(["Segoe UI", "Arial"], 13)
        self.mono   = self._load(["Consolas", "Courier New"], 17)
        self.mono_sm= self._load(["Consolas", "Courier New"], 14)
        self.big_num= self._load(["Bahnschrift", "Arial Black"], 42, bold=True)

    def _load(self, names, size, bold=False):
        for n in names:
            path = pygame.font.match_font(n.lower().replace(" ", ""), bold=bold)
            if path:
                return pygame.font.Font(path, size)
        return pygame.font.SysFont("arial", size, bold=bold)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
