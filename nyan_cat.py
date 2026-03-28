import math
import random
import pygame

# First flyby: random moment within the first 60s after startup.
FIRST_MINUTE_MS = 60_000
# Later flybys: base 2m 3s, plus random jitter so timing isn’t fixed.
REPEAT_INTERVAL_MS = 2 * 60_000 + 3_000
REPEAT_JITTER_MS = 30_000

SPEED_PX_S = 260
CAT_W = 52
TRAIL_LEN = 132

_INV_SQRT2 = math.sqrt(0.5)
# Motion: top-right → bottom-left (down and left)
VX = -SPEED_PX_S * _INV_SQRT2
VY = SPEED_PX_S * _INV_SQRT2
# Rainbow trails toward top-right (opposite to velocity)
BX = -VX / SPEED_PX_S
BY = -VY / SPEED_PX_S
PX = -BY
PY = BX

RAINBOW = [
    (255, 0, 0),
    (255, 128, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 128, 255),
    (148, 0, 211),
]

# Pivot in local space (center of temp surface) — cat “core” in original right-facing layout
_TMP_W, _TMP_H = 268, 128
_CX_TMP = _TMP_W // 2
_CY_TMP = _TMP_H // 2
# World offset from self.x, self.y (top-left of sprite box) to rotation pivot
_PIVOT_DX = 22.0
_PIVOT_DY = 22.0


def _next_repeat_delay_ms():
    delay = REPEAT_INTERVAL_MS + random.randint(-REPEAT_JITTER_MS, REPEAT_JITTER_MS)
    return max(45_000, delay)


def _face_angle_degrees():
    """Right-facing sprite → motion (VX, VY); pygame.rotate is CCW, +y is down."""
    return -math.degrees(math.atan2(VY, VX))


class NyanCatFlyby:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.active = False
        self.x = 0.0
        self.y = 0.0
        self._anim_t = 0.0
        boot = pygame.time.get_ticks()
        self._next_spawn_ms = boot + random.randint(0, FIRST_MINUTE_MS)

    def resize(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h

    def update(self, frame_ms):
        now = pygame.time.get_ticks()
        dt = max(0.001, min(frame_ms, 200) / 1000.0)

        if not self.active:
            if now >= self._next_spawn_ms:
                self.active = True
                margin = 40
                self.x = float(self.screen_w + TRAIL_LEN + margin)
                self.y = float(-margin - 40)
                self._anim_t = 0.0
            return

        self._anim_t += dt
        self.x += VX * dt
        self.y += VY * dt
        if self.x < -(TRAIL_LEN + CAT_W + 60) or self.y > self.screen_h + TRAIL_LEN + 60:
            self.active = False
            self._next_spawn_ms = now + _next_repeat_delay_ms()

    def draw(self, surface):
        if not self.active:
            return
        cx = self.x
        cy = self.y
        t = self._anim_t
        px = cx + _PIVOT_DX
        py = cy + _PIVOT_DY

        def w2l(wx, wy):
            return (int(_CX_TMP + wx - px), int(_CY_TMP + wy - py))

        tmp = pygame.Surface((_TMP_W, _TMP_H), pygame.SRCALPHA)

        icx = int(cx)
        icy = int(cy)

        # Tail-side anchor (left of poptart); strips step along (BX, BY) = up-right = behind flight
        rear_x = cx - 28.0
        rear_y = cy + 22.0
        for i, col in enumerate(RAINBOW):
            wave = 3 * math.sin(t * 8 + i * 0.7)
            along = 18.0 + i * 14.0
            wx = rear_x + BX * along + PX * wave
            wy = rear_y + BY * along + PY * wave
            p1 = w2l(wx - PX * 32, wy - PY * 32)
            p2 = w2l(wx + PX * 32, wy + PY * 32)
            pygame.draw.line(tmp, col, p1, p2, 5)

        body = pygame.Rect(*w2l(icx, icy + 12), 36, 22)
        pygame.draw.rect(tmp, (255, 174, 201), body, border_radius=4)
        ox, oy = w2l(icx + 4, icy + 14)
        pygame.draw.rect(tmp, (255, 220, 235), (ox, oy, 28, 6), border_radius=2)
        for sx, sy in ((10, 18), (22, 20), (16, 24), (28, 22)):
            pygame.draw.rect(tmp, (255, 50, 80), (*w2l(icx + sx, icy + sy), 3, 3))
            pygame.draw.rect(tmp, (255, 220, 100), (*w2l(icx + sx + 5, icy + sy - 2), 2, 2))

        whx, why = icx + 28, icy + 4
        h0 = w2l(whx, why)
        pygame.draw.ellipse(tmp, (153, 153, 170), (*h0, 26, 22))
        pygame.draw.polygon(
            tmp,
            (153, 153, 170),
            [w2l(whx + 4, why + 2), w2l(whx + 2, why - 6), w2l(whx + 10, why)],
        )
        pygame.draw.polygon(
            tmp,
            (153, 153, 170),
            [w2l(whx + 18, why + 2), w2l(whx + 22, why - 6), w2l(whx + 14, why)],
        )
        pygame.draw.polygon(
            tmp,
            (255, 182, 193),
            [w2l(whx + 5, why + 1), w2l(whx + 4, why - 4), w2l(whx + 9, why)],
        )
        pygame.draw.polygon(
            tmp,
            (255, 182, 193),
            [w2l(whx + 17, why + 1), w2l(whx + 20, why - 4), w2l(whx + 15, why)],
        )

        eye = (255, 255, 255)
        pygame.draw.circle(tmp, eye, w2l(whx + 9, why + 10), 4)
        pygame.draw.circle(tmp, eye, w2l(whx + 17, why + 10), 4)
        pygame.draw.circle(tmp, (40, 40, 50), w2l(whx + 10, why + 10), 2)
        pygame.draw.circle(tmp, (40, 40, 50), w2l(whx + 18, why + 10), 2)
        arc_rect = pygame.Rect(*w2l(whx + 8, why + 12), 12, 8)
        pygame.draw.arc(tmp, (60, 60, 70), arc_rect, 0.2, 2.8, 2)

        for lx, ly in ((icx + 6, icy + 32), (icx + 14, icy + 34), (icx + 22, icy + 32), (icx + 30, icy + 34)):
            pygame.draw.rect(tmp, (120, 120, 135), (*w2l(lx, ly), 5, 8), border_radius=1)

        angle = _face_angle_degrees()
        rotated = pygame.transform.rotate(tmp, angle)
        r = rotated.get_rect(center=(int(px), int(py)))
        surface.blit(rotated, r.topleft)
