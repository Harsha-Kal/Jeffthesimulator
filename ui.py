"""
Sidebar drag-and-drop UI: palette of body types, placement ghost, velocity aim, and selection.
Constants below control layout; DragMenu.handle_event returns actions consumed by main.py.
"""
import math
import os
import pygame

from physics_constants import (
    G_SI,
    EPS2_M2,
    circular_orbit_velocity_from_aim_m_s,
    format_length_m,
    format_speed_m_s,
    game_screen_to_m,
    strongest_attractor,
)

# ---------------------------------------------------------------------------
# Layout: sidebar width, header, icon grid, scroll arrows, bottom button band.
# ---------------------------------------------------------------------------
SIDEBAR_W = 168
HEADER_H = 76
ARROW_H = 22
GRID_PAD = 8
ICON_CELL = 58
ICON_INNER = 52
COLS = 2
BOTTOM_H = 64
MARGIN = 6

# Velocity preview while placing: aim direction in px; speed is SI (m/s) capped for inner solar system.
VEL_MOUSE_DEAD = 10
VEL_MOUSE_MAX_DIST = 150
VEL_SPEED_MAX_M_S = 45_000.0
ARROW_LEN_MAX = 100.0


def pending_velocity_from_mouse(px, py, mx, my, bodies):
    """
    Aim direction from mouse; speed is circular-orbit speed around the dominant attractor
    when one exists, else legacy speed from pull distance. Returns (vx,vy), unit aim, arrow len.
    """
    dx = float(mx - px)
    dy = float(my - py)
    d = math.hypot(dx, dy)
    if d < VEL_MOUSE_DEAD:
        ux, uy = 1.0, 0.0
        span_t = 0.0
    else:
        ux, uy = dx / d, dy / d
        span = max(1e-6, VEL_MOUSE_MAX_DIST - VEL_MOUSE_DEAD)
        span_t = min(1.0, (d - VEL_MOUSE_DEAD) / span)

    x_m, y_m = game_screen_to_m(px, py)
    att = strongest_attractor(bodies, x_m, y_m)
    if att is not None:
        vx, vy = circular_orbit_velocity_from_aim_m_s(x_m, y_m, att, ux, uy)
        spd = math.hypot(vx, vy)
        arrow_len = span_t * ARROW_LEN_MAX
        if spd > 1e-6:
            ux, uy = vx / spd, vy / spd
        return vx, vy, ux, uy, arrow_len

    if d < VEL_MOUSE_DEAD:
        return 0.0, 0.0, ux, uy, 0.0
    speed = span_t * VEL_SPEED_MAX_M_S
    vx, vy = ux * speed, uy * speed
    arrow_len = span_t * ARROW_LEN_MAX
    return vx, vy, ux, uy, arrow_len


def _fmt_mass_kg(mass_kg: float) -> str:
    if mass_kg >= 1e27:
        return f"{mass_kg:.2e} kg"
    if mass_kg >= 1e24:
        return f"{mass_kg/1e24:.2f}e24 kg"
    if mass_kg >= 1e22:
        return f"{mass_kg/1e22:.2f}e22 kg"
    return f"{mass_kg:.2e} kg"


def _mouse_over_pending_confirm_ui(px, py, mx, my, pad=26):
    """True if the cursor is over the check/cancel circles so we don't retarget the arrow."""
    check_c = (px + 44, py)
    cancel_c = (px - 44, py)
    return (
        math.hypot(mx - check_c[0], my - check_c[1]) <= pad
        or math.hypot(mx - cancel_c[0], my - cancel_c[1]) <= pad
    )


def draw_velocity_arrow(screen, px, py, ux, uy, shaft_len, color=(130, 255, 185)):
    """Draw a line plus arrowhead from spawn along unit vector (ux, uy) with length shaft_len."""
    if shaft_len < 5.0:
        return
    x2 = px + ux * shaft_len
    y2 = py + uy * shaft_len
    p0 = (int(px), int(py))
    p1 = (int(x2), int(y2))
    pygame.draw.line(screen, color, p0, p1, 3)
    ah = 12.0
    bw = 7.0
    bx = x2 - ux * ah
    by = y2 - uy * ah
    pxo = -uy * bw
    pyo = ux * bw
    pygame.draw.polygon(
        screen,
        color,
        [(int(x2), int(y2)), (int(bx + pxo), int(by + pyo)), (int(bx - pxo), int(by - pyo))],
    )


def _sidebar_background(w, h):
    """Load and crop/scale starry art for the sidebar, or a dark fallback if missing."""
    path = os.path.join(os.path.dirname(__file__), "assets", "starrybackground.png")
    fallback = pygame.Surface((w, h))
    fallback.fill((8, 10, 28))
    if not os.path.isfile(path):
        return fallback
    try:
        img = pygame.image.load(path).convert()
    except pygame.error:
        return fallback
    iw, ih = img.get_size()
    if iw <= 0 or ih <= 0:
        return fallback
    scale = max(w / iw, h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    scaled = pygame.transform.smoothscale(img, (nw, nh))
    x = max(0, (nw - w) // 2)
    y = max(0, (nh - h) // 2)
    out = pygame.Surface((w, h))
    out.blit(scaled, (0, 0), (x, y, w, h))
    return out


def _glass_header_panel(rect_w, rect_h):
    """Semi-transparent rounded rectangle for the title area above the body grid."""
    surf = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
    surf.fill((10, 14, 32, 220))
    pygame.draw.rect(surf, (120, 200, 255, 180), surf.get_rect(), 2, border_radius=8)
    pygame.draw.rect(surf, (180, 100, 220, 80), surf.get_rect().inflate(-3, -3), 1, border_radius=6)
    return surf


def _draw_sun_icon(surf, cx, cy, r):
    for a in range(0, 360, 45):
        rad = math.radians(a)
        x2 = cx + math.cos(rad) * (r + 6)
        y2 = cy - math.sin(rad) * (r + 6)
        pygame.draw.line(surf, (255, 220, 80), (cx, cy), (int(x2), int(y2)), 2)
    pygame.draw.circle(surf, (255, 230, 60), (int(cx), int(cy)), r)
    pygame.draw.circle(surf, (255, 200, 40), (int(cx), int(cy)), r, 2)


def _draw_planet_icon(surf, cx, cy, r, color, rings=False):
    pygame.draw.circle(surf, tuple(max(0, c - 40) for c in color), (int(cx), int(cy) + 2), r)
    pygame.draw.circle(surf, color, (int(cx), int(cy)), r)
    pygame.draw.circle(surf, tuple(min(255, c + 50) for c in color), (int(cx - r // 3), int(cy - r // 3)), max(2, r // 4))
    if rings:
        pygame.draw.ellipse(surf, (200, 200, 220), (cx - r - 2, cy - 2, r * 2 + 4, r // 2 + 4), 2)


def _draw_icon(surface, item, rect):
    """Dispatch to planet/sun sketches or a generic colored disk for unknown palette names."""
    cx, cy = rect.centerx, rect.centery
    r = 14
    name = item["name"]
    if name == "Sun":
        _draw_sun_icon(surface, cx, cy, r)
    elif name == "Mars":
        _draw_planet_icon(surface, cx, cy, r, (220, 80, 60))
    elif name == "Earth":
        _draw_planet_icon(surface, cx, cy, r, (60, 140, 220))
    elif name == "Ice":
        _draw_planet_icon(surface, cx, cy, r, (120, 200, 255), rings=True)
    else:
        pygame.draw.circle(surface, item["color"], (int(cx), int(cy)), r)


class DragMenu:
    # Right-hand palette: drag items into the playfield, confirm spawn, aim initial velocity.

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.items = [
            {
                "name": "Sun",
                "color": (255, 230, 60),
                "mass": 1.989e30,
                "radius": 15,
                "is_static": True,
            },
            {
                "name": "Mars",
                "color": (220, 80, 60),
                "mass": 6.39e23,
                "radius": 6,
                "is_static": False,
            },
            {
                "name": "Earth",
                "color": (60, 200, 120),
                "mass": 5.972e24,
                "radius": 6,
                "is_static": False,
            },
            {
                "name": "Ice",
                "color": (140, 200, 255),
                "mass": 4.8e22,
                "radius": 6,
                "is_static": False,
            },
        ]

        self.sidebar_x = screen_w - SIDEBAR_W
        self.game_w = self.sidebar_x

        self.scroll = 0
        self.hovered_index = None
        self.dragging_item = None
        self.pending = None
        self.selected_body = None
        self._font_title = pygame.font.SysFont("arial", 15, bold=True)
        self._font_small = pygame.font.SysFont("arial", 12)
        self._sidebar_bg = _sidebar_background(SIDEBAR_W, screen_h)
        self._item_rects = []

    def resize(self, screen_w, screen_h):
        """Keep sidebar aligned to the new window size and rebuild the background surface."""
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.sidebar_x = screen_w - SIDEBAR_W
        self.game_w = self.sidebar_x
        self._sidebar_bg = _sidebar_background(SIDEBAR_W, screen_h)
        self.scroll = min(self.scroll, self._max_scroll())

    def _grid_top(self):
        return HEADER_H + ARROW_H + GRID_PAD

    def _grid_bottom(self):
        return self.screen_h - BOTTOM_H - ARROW_H - GRID_PAD

    def _rows_visible(self):
        inner_h = self._grid_bottom() - self._grid_top()
        return max(1, inner_h // ICON_CELL)

    def _total_rows(self):
        return math.ceil(len(self.items) / COLS)

    def _max_scroll(self):
        return max(0, self._total_rows() - self._rows_visible())

    def _layout_item_rects(self):
        """Compute screen rects for each palette icon row, respecting vertical scroll."""
        rects = []
        row0 = self._grid_top()
        for idx in range(len(self.items)):
            row = idx // COLS - self.scroll
            col = idx % COLS
            if row < 0 or row >= self._rows_visible():
                rects.append(None)
                continue
            x = self.sidebar_x + GRID_PAD + col * ICON_CELL
            y = row0 + row * ICON_CELL
            rects.append(pygame.Rect(x, y, ICON_CELL - 4, ICON_CELL - 4))
        self._item_rects = rects

    def _arrow_rects(self):
        up = pygame.Rect(self.sidebar_x + SIDEBAR_W // 2 - 36, HEADER_H + 2, 72, ARROW_H - 4)
        down = pygame.Rect(
            self.sidebar_x + SIDEBAR_W // 2 - 36,
            self.screen_h - BOTTOM_H - ARROW_H + 2,
            72,
            ARROW_H - 4,
        )
        return up, down

    def _in_game(self, mx, my):
        return 0 <= mx < self.game_w and 0 <= my < self.screen_h

    def _in_sidebar(self, mx, my):
        return self.sidebar_x <= mx < self.screen_w and 0 <= my < self.screen_h

    def _placement_valid(self, item, x, y, bodies):
        """Spawn is invalid if outside margins or overlapping another body (with a small gap)."""
        r = item["radius"]
        if x - r < MARGIN or x + r > self.game_w - MARGIN or y - r < MARGIN or y + r > self.screen_h - MARGIN:
            return False
        for b in bodies:
            dist = math.hypot(x - b.x, y - b.y)
            if dist < r + b.radius + 4:
                return False
        return True

    def _influence_radius(self, item):
        return max(48, item["radius"] * 10)

    def _clear_button_rect(self):
        return pygame.Rect(self.sidebar_x + 10, self.screen_h - BOTTOM_H + 8, SIDEBAR_W - 20, BOTTOM_H - 16)

    def _body_at(self, mx, my, bodies):
        """Topmost body under the cursor (reverse draw order) for selection and delete affordance."""
        for b in reversed(bodies):
            if math.hypot(mx - b.x, my - b.y) <= b.radius + 6:
                return b
        return None

    def _delete_button_pos(self, body):
        ox = body.x + body.radius + 16
        oy = body.y - body.radius - 12
        return ox, oy

    def _delete_hit(self, mx, my, body):
        if body is None:
            return False
        ox, oy = self._delete_button_pos(body)
        return math.hypot(mx - ox, my - oy) <= 17

    def _spawn_velocity_for_pending(self, item):
        """Final (vx, vy) at confirm: zero for static bodies, else frozen aim or live mouse aim."""
        if item.get("is_static"):
            return 0.0, 0.0
        if self.pending.get("frozen"):
            return float(self.pending["fvx"]), float(self.pending["fvy"])
        return float(self.pending.get("pvx", 0)), float(self.pending.get("pvy", 0))

    def _toggle_pending_freeze(self, px, py, mx, my, bodies):
        """Lock or unlock the velocity vector while placing; clicking UI keeps the last preview."""
        if self.pending.get("frozen"):
            self.pending["frozen"] = False
            return
        if _mouse_over_pending_confirm_ui(px, py, mx, my):
            vx = float(self.pending.get("pvx", 0))
            vy = float(self.pending.get("pvy", 0))
            ux = float(self.pending.get("pux", 1))
            uy = float(self.pending.get("puy", 0))
            alen = float(self.pending.get("palen", 0))
        else:
            vx, vy, ux, uy, alen = pending_velocity_from_mouse(px, py, mx, my, bodies)
        self.pending["frozen"] = True
        self.pending["fvx"], self.pending["fvy"] = vx, vy
        self.pending["fux"], self.pending["fuy"] = ux, uy
        self.pending["falen"] = alen

    def handle_event(self, event, bodies):
        """Return (action, payload) for main.py: spawn, clear_all, delete_body, or (None, None)."""
        mx, my = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEWHEEL and self._in_sidebar(mx, my):
            self.scroll = max(0, min(self._max_scroll(), self.scroll - event.y))
            self._layout_item_rects()
            return None, None

        if event.type == pygame.MOUSEMOTION:
            self.hovered_index = None
            for i, r in enumerate(self._item_rects):
                if r and r.collidepoint(mx, my):
                    self.hovered_index = i
                    break

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            up_r, down_r = self._arrow_rects()
            if up_r.collidepoint(mx, my) and self.scroll > 0:
                self.scroll -= 1
                self._layout_item_rects()
                return None, None
            if down_r.collidepoint(mx, my) and self.scroll < self._max_scroll():
                self.scroll += 1
                self._layout_item_rects()
                return None, None

            if self._clear_button_rect().collidepoint(mx, my):
                self.selected_body = None
                self.pending = None
                self.dragging_item = None
                return "clear_all", None

            # Pending placement: check/cancel spawn, or toggle velocity freeze on empty game click.
            if self.pending:
                px, py = self.pending["x"], self.pending["y"]
                item = self.pending["item"]
                valid = self._placement_valid(item, px, py, bodies)
                cr = 18
                check_c = (px + 44, py)
                cancel_c = (px - 44, py)
                if math.hypot(mx - check_c[0], my - check_c[1]) <= cr:
                    if valid:
                        vx, vy = self._spawn_velocity_for_pending(item)
                        self.pending = None
                        return "spawn", (item, (px, py), (vx, vy))
                    return None, None
                if math.hypot(mx - cancel_c[0], my - cancel_c[1]) <= cr:
                    self.pending = None
                    return None, None

                if self._in_game(mx, my) and not item.get("is_static"):
                    self._toggle_pending_freeze(px, py, mx, my, bodies)
                    return None, None

            # Game area without pending: delete button on selected body, else pick/deselect under cursor.
            if self._in_game(mx, my) and not self.pending:
                if self.selected_body in bodies and self._delete_hit(mx, my, self.selected_body):
                    b = self.selected_body
                    self.selected_body = None
                    return "delete_body", b
                hit = self._body_at(mx, my, bodies)
                if hit:
                    self.selected_body = hit
                else:
                    self.selected_body = None
                return None, None

            if self.dragging_item is None and self.pending is None:
                for i, r in enumerate(self._item_rects):
                    if r and r.collidepoint(mx, my):
                        self.dragging_item = self.items[i]
                        return None, None

        # Drop on playfield: enter pending state so user can confirm position and aim velocity.
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_item:
            item = self.dragging_item
            self.dragging_item = None
            if self._in_game(mx, my):
                self.pending = {
                    "item": item,
                    "x": float(mx),
                    "y": float(my),
                    "frozen": False,
                    "fvx": 0.0,
                    "fvy": 0.0,
                    "fux": 1.0,
                    "fuy": 0.0,
                    "falen": 0.0,
                    "pvx": 0.0,
                    "pvy": 0.0,
                    "pux": 1.0,
                    "puy": 0.0,
                    "palen": 0.0,
                }
            return None, None

        return None, None

    def draw(self, screen, bodies):
        """Paint sidebar chrome, clipped icon grid, overlays for drag/pending/selection."""
        self._layout_item_rects()

        screen.blit(self._sidebar_bg, (self.sidebar_x, 0))

        hdr = pygame.Rect(self.sidebar_x + 8, 8, SIDEBAR_W - 16, HEADER_H - 16)
        screen.blit(_glass_header_panel(hdr.width, hdr.height), hdr.topleft)

        display_item = None
        if self.dragging_item:
            display_item = self.dragging_item
        elif self.pending:
            display_item = self.pending["item"]
        elif self.hovered_index is not None:
            display_item = self.items[self.hovered_index]

        if display_item:
            t1 = self._font_title.render(display_item["name"], True, (235, 245, 255))
            if self.pending and not display_item.get("is_static"):
                lock = "locked" if self.pending.get("frozen") else "aim = orbit dir • pull = arrow • O = refresh"
                sub = f"{_fmt_mass_kg(display_item['mass'])} • {lock}"
            else:
                sub = _fmt_mass_kg(display_item["mass"])
            t2 = self._font_small.render(sub, True, (170, 200, 230))
        else:
            t1 = self._font_title.render("Select body", True, (235, 245, 255))
            t2 = self._font_small.render("Drag onto space", True, (170, 200, 230))
        screen.blit(t1, (hdr.x + 8, hdr.y + 10))
        screen.blit(t2, (hdr.x + 8, hdr.y + 34))

        up_r, down_r = self._arrow_rects()
        arrow_specs = (
            (
                up_r,
                (
                    (up_r.centerx, up_r.centery - 5),
                    (up_r.centerx - 8, up_r.centery + 5),
                    (up_r.centerx + 8, up_r.centery + 5),
                ),
                self.scroll > 0,
            ),
            (
                down_r,
                (
                    (down_r.centerx, down_r.centery + 5),
                    (down_r.centerx - 8, down_r.centery - 5),
                    (down_r.centerx + 8, down_r.centery - 5),
                ),
                self.scroll < self._max_scroll(),
            ),
        )
        for rect, points, active in arrow_specs:
            col = (120, 210, 255) if active else (55, 70, 95)
            pygame.draw.rect(screen, (18, 22, 42), rect, border_radius=4)
            pygame.draw.rect(screen, (90, 140, 200), rect, 1, border_radius=4)
            pygame.draw.polygon(screen, col, points)

        # Clip scrolling grid so icons do not draw over arrows or header/footer.
        clip = pygame.Rect(self.sidebar_x, self._grid_top(), SIDEBAR_W, self._grid_bottom() - self._grid_top())
        old_clip = screen.get_clip()
        screen.set_clip(clip)

        for i, r in enumerate(self._item_rects):
            if not r:
                continue
            item = self.items[i]
            bg = (35, 45, 72) if self.hovered_index == i else (22, 28, 48)
            pygame.draw.rect(screen, bg, r, border_radius=6)
            border = (140, 200, 255) if self.hovered_index == i else (70, 100, 150)
            pygame.draw.rect(screen, border, r, 2, border_radius=6)
            inner = r.inflate(-6, -6)
            _draw_icon(screen, item, inner)

        screen.set_clip(old_clip)

        bot = self._clear_button_rect()
        pygame.draw.rect(screen, (22, 28, 48), bot, border_radius=8)
        pygame.draw.rect(screen, (90, 140, 200), bot, 2, border_radius=8)
        hint = self._font_small.render("Clear all", True, (190, 210, 235))
        sub = self._font_small.render("bodies", True, (160, 185, 210))
        screen.blit(hint, (bot.centerx - hint.get_width() // 2, bot.centery - 10))
        screen.blit(sub, (bot.centerx - sub.get_width() // 2, bot.centery + 2))

        mx, my = pygame.mouse.get_pos()

        def draw_ghost(ix, iy, item, valid):
            """Semi-transparent influence ring plus body preview at cursor or pending position."""
            inf = self._influence_radius(item)
            col = (240, 240, 250, 55) if valid else (255, 80, 80, 70)
            ring = (220, 220, 230, 90) if valid else (255, 100, 100, 100)
            s = pygame.Surface((inf * 2 + 4, inf * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, col, (inf + 2, inf + 2), inf)
            pygame.draw.circle(s, ring, (inf + 2, inf + 2), inf, 2)
            screen.blit(s, (int(ix - inf - 2), int(iy - inf - 2)))
            ghost = pygame.Surface((item["radius"] * 2 + 4, item["radius"] * 2 + 4), pygame.SRCALPHA)
            cc = item["radius"] + 2
            pygame.draw.circle(ghost, (*item["color"], 200), (cc, cc), item["radius"])
            screen.blit(ghost, (int(ix - cc), int(iy - cc)))

        if self.dragging_item and self._in_game(mx, my):
            valid = self._placement_valid(self.dragging_item, mx, my, bodies)
            draw_ghost(mx, my, self.dragging_item, valid)

        if self.pending:
            px, py = self.pending["x"], self.pending["y"]
            item = self.pending["item"]
            valid = self._placement_valid(item, px, py, bodies)
            draw_ghost(px, py, item, valid)

            if not item.get("is_static"):
                if self.pending.get("frozen"):
                    ux = float(self.pending["fux"])
                    uy = float(self.pending["fuy"])
                    alen = float(self.pending["falen"])
                    acol = (255, 220, 120)
                else:
                    if not _mouse_over_pending_confirm_ui(px, py, mx, my):
                        vx, vy, ux, uy, alen = pending_velocity_from_mouse(px, py, mx, my, bodies)
                        self.pending["pvx"] = vx
                        self.pending["pvy"] = vy
                        self.pending["pux"] = ux
                        self.pending["puy"] = uy
                        self.pending["palen"] = alen
                    else:
                        ux = float(self.pending["pux"])
                        uy = float(self.pending["puy"])
                        alen = float(self.pending["palen"])
                    acol = (130, 255, 185)
                draw_velocity_arrow(screen, px, py, ux, uy, alen, color=acol)

                if self.pending.get("frozen"):
                    pvx = float(self.pending.get("fvx", 0))
                    pvy = float(self.pending.get("fvy", 0))
                else:
                    pvx = float(self.pending.get("pvx", 0))
                    pvy = float(self.pending.get("pvy", 0))
                x_m, y_m = game_screen_to_m(px, py)
                att = strongest_attractor(bodies, x_m, y_m)
                v_mag = math.hypot(pvx, pvy)
                ty0 = int(py + item["radius"] + 10)
                readout = [f"|v| = {format_speed_m_s(v_mag)}"]
                if att is not None:
                    dxp = x_m - att.x_m
                    dyp = y_m - att.y_m
                    rp = math.sqrt(max(dxp * dxp + dyp * dyp, EPS2_M2))
                    readout.append(f"r → primary = {format_length_m(rp)}")
                    v_circ = math.sqrt(G_SI * att.mass / rp)
                    readout.append(f"v_circ = {format_speed_m_s(v_circ)}")
                for li, line in enumerate(readout):
                    surf = self._font_small.render(line, True, (190, 220, 250))
                    lx = int(px - surf.get_width() // 2)
                    lx = max(6, min(lx, self.game_w - surf.get_width() - 6))
                    screen.blit(surf, (lx, ty0 + li * 14))

            cr = 18
            check_c = (int(px + 44), int(py))
            cancel_c = (int(px - 44), int(py))

            pygame.draw.circle(screen, (40, 160, 70), check_c, cr)
            pygame.draw.circle(screen, (20, 100, 40), check_c, cr, 2)
            pts = [
                (check_c[0] - 6, check_c[1]),
                (check_c[0] - 1, check_c[1] + 5),
                (check_c[0] + 8, check_c[1] - 6),
            ]
            pygame.draw.lines(screen, (255, 255, 255), False, pts, 3)

            pygame.draw.circle(screen, (200, 50, 50), cancel_c, cr)
            pygame.draw.circle(screen, (120, 30, 30), cancel_c, cr, 2)
            pygame.draw.line(screen, (255, 255, 255), (cancel_c[0] - 7, cancel_c[1] - 7), (cancel_c[0] + 7, cancel_c[1] + 7), 3)
            pygame.draw.line(screen, (255, 255, 255), (cancel_c[0] + 7, cancel_c[1] - 7), (cancel_c[0] - 7, cancel_c[1] + 7), 3)

        if self.selected_body is not None:
            if self.selected_body not in bodies:
                self.selected_body = None
            else:
                ox, oy = self._delete_button_pos(self.selected_body)
                ox, oy = int(ox), int(oy)
                pygame.draw.circle(screen, (200, 50, 50), (ox, oy), 16)
                pygame.draw.circle(screen, (120, 30, 30), (ox, oy), 16, 2)
                pygame.draw.line(screen, (255, 255, 255), (ox - 7, oy - 7), (ox + 7, oy + 7), 3)
                pygame.draw.line(screen, (255, 255, 255), (ox + 7, oy - 7), (ox - 7, oy + 7), 3)

        pygame.draw.line(screen, (100, 160, 220), (self.sidebar_x, 0), (self.sidebar_x, self.screen_h), 2)
