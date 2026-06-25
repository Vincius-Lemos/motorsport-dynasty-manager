"""
App — laço principal e pilha de cenas (state machine) do Motorsport Dynasty.
"""
import pygame
from . import theme as T


class Scene:
    """Base de uma tela. Subclasses sobrescrevem handle/update/draw."""
    def __init__(self, app):
        self.app = app

    def on_enter(self): ...
    def handle(self, event): ...
    def update(self, dt): ...
    def draw(self, surf): ...


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Motorsport Dynasty Manager")
        # Tela virtual onde tudo é desenhado (coordenadas fixas das cenas)
        self.canvas = pygame.Surface((T.WIDTH, T.HEIGHT))
        # screen = janela real; pode ter qualquer resolução
        self.window = None
        self.res_index = 2          # Full HD por padrão
        self._scale = 1.0
        self._offset = (0, 0)
        self.fonts = T.Fonts()
        self._apply_resolution(self.res_index)
        self.clock = pygame.time.Clock()
        self.running = True
        self.stack = []
        # Estado de jogo partilhado entre cenas
        self.profile = None
        self.career = None
        self.mode = None        # "driver" | "manager"
        self.toast = None
        self._toast_t = 0
        self.anim_t = 0.0        # relógio global p/ animações
        self._fade = 0.0         # alpha de transição (0..1)

    # ── resolução / escala ────────────────────────────────────────────────────
    @property
    def screen(self):
        """Compatibilidade: cenas desenham sempre na tela virtual."""
        return self.canvas

    def _apply_resolution(self, index):
        label, w, h, full = T.RESOLUTIONS[index]
        self.res_index = index
        if full:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((w, h))
        self._recompute_scale()

    def cycle_resolution(self, delta=1):
        self._apply_resolution((self.res_index + delta) % len(T.RESOLUTIONS))

    def set_resolution(self, index):
        if 0 <= index < len(T.RESOLUTIONS):
            self._apply_resolution(index)

    def _recompute_scale(self):
        win_w, win_h = self.window.get_size()
        scale = min(win_w / T.WIDTH, win_h / T.HEIGHT)
        disp_w, disp_h = int(T.WIDTH * scale), int(T.HEIGHT * scale)
        self._scale = scale
        self._offset = ((win_w - disp_w) // 2, (win_h - disp_h) // 2)

    def _window_to_canvas(self, pos):
        ox, oy = self._offset
        return (int((pos[0] - ox) / self._scale),
                int((pos[1] - oy) / self._scale))

    def _transform_event(self, event):
        """Converte coordenadas da janela real para a tela virtual."""
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                           pygame.MOUSEBUTTONUP):
            event.pos = self._window_to_canvas(event.pos)
        return event

    # ── pilha de cenas ────────────────────────────────────────────────────────
    def push(self, scene):
        self.stack.append(scene)
        scene.on_enter()
        self._fade = 1.0

    def pop(self):
        if self.stack:
            self.stack.pop()
        self._fade = 1.0

    def replace(self, scene):
        if self.stack:
            self.stack.pop()
        self.push(scene)

    def reset_to(self, scene):
        self.stack = []
        self.push(scene)

    @property
    def scene(self):
        return self.stack[-1] if self.stack else None

    def notify(self, text, secs=2.5):
        self.toast = text
        self._toast_t = secs

    # ── laço ──────────────────────────────────────────────────────────────────
    def run(self):
        while self.running and self.stack:
            dt = self.clock.tick(T.FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    # F11 alterna tela cheia (último item da lista)
                    self.set_resolution(len(T.RESOLUTIONS) - 1
                                        if not T.RESOLUTIONS[self.res_index][3] else 2)
                elif self.scene:
                    self.scene.handle(self._transform_event(event))
            if self.scene:
                self.anim_t += dt
                self.scene.update(dt)
                self.canvas.fill(T.BG)
                self.scene.draw(self.canvas)
                self._draw_toast(dt)
                # fade de transição entre telas
                if self._fade > 0.001:
                    self._fade = max(0.0, self._fade - dt * 4.5)
                    ov = pygame.Surface((T.WIDTH, T.HEIGHT))
                    ov.fill(T.BG)
                    ov.set_alpha(int(255 * self._fade))
                    self.canvas.blit(ov, (0, 0))
                # Escala a tela virtual para a janela real (com letterbox)
                self.window.fill((0, 0, 0))
                scaled = pygame.transform.smoothscale(
                    self.canvas,
                    (int(T.WIDTH * self._scale), int(T.HEIGHT * self._scale)))
                self.window.blit(scaled, self._offset)
                pygame.display.flip()
        pygame.quit()

    def _draw_toast(self, dt):
        if not self.toast:
            return
        self._toast_t -= dt
        if self._toast_t <= 0:
            self.toast = None
            return
        from .widgets import draw_text
        f = self.fonts.small
        w = f.size(self.toast)[0] + 40
        rect = pygame.Rect((T.WIDTH - w) // 2, T.HEIGHT - 70, w, 42)
        alpha = min(1.0, self._toast_t) if self._toast_t < 1 else 1.0
        s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        s.fill((*T.ACCENT, int(235 * alpha)))
        self.screen.blit(s, rect.topleft)
        draw_text(self.screen, self.toast, f, (15, 14, 23), rect.center, center=True)
