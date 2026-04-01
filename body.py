"""
N-body Newtonian gravity in SI (m, kg, s), velocity Verlet integration, circle collisions.
Circle radii are in pixels; overlap depth in meters uses radius_px * SCALE_M_PER_PX (see physics_constants).
"""
from __future__ import annotations

import math
import os
import random
import pygame

from physics_constants import G_SI, EPS2_M2, radius_m_from_px

# Default inelastic normal impulse; elastic mode uses 1.0
RESTITUTION_INELASTIC = 0.92

# Collision handling: bounce (slightly inelastic), elastic, merge, fragment (split pair)
COLLISION_BOUNCE = "bounce"
COLLISION_ELASTIC = "elastic"
COLLISION_MERGE = "merge"
COLLISION_FRAGMENT = "fragment"


_SPRITE_CACHE: dict[str, pygame.Surface | None] = {}


def _load_body_sprite(name: str) -> pygame.Surface | None:
    """Load and cache body art from assets by name (stars and planets)."""
    key = name.lower()
    if key in _SPRITE_CACHE:
        return _SPRITE_CACHE[key]

    base_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(base_dir, "assets")
    img: pygame.Surface | None = None
    candidates: list[str] = []
    if os.path.isdir(assets_dir):
        base = name.replace(" ", "_")
        candidates.extend(
            [
                os.path.join(assets_dir, f"{base}.png"),
                os.path.join(assets_dir, f"{base}.PNG"),
                os.path.join(assets_dir, f"{base.lower()}.png"),
            ]
        )
        try:
            for fname in os.listdir(assets_dir):
                lower = fname.lower()
                if lower.startswith(base.lower()) and lower.endswith(".png"):
                    candidates.append(os.path.join(assets_dir, fname))
        except OSError:
            pass

    for path in candidates:
        if os.path.isfile(path):
            try:
                raw = pygame.image.load(path).convert_alpha()
            except pygame.error:
                continue
            w, h = raw.get_size()
            # Treat near-white backgrounds as transparent and crop to the non-transparent bounds.
            for y in range(h):
                for x in range(w):
                    r, g, b, a = raw.get_at((x, y))
                    if r >= 245 and g >= 245 and b >= 245:
                        raw.set_at((x, y), (r, g, b, 0))
            min_x, min_y = w, h
            max_x, max_y = -1, -1
            for y in range(h):
                for x in range(w):
                    _, _, _, a = raw.get_at((x, y))
                    if a != 0:
                        if x < min_x:
                            min_x = x
                        if y < min_y:
                            min_y = y
                        if x > max_x:
                            max_x = x
                        if y > max_y:
                            max_y = y
            if max_x >= min_x and max_y >= min_y:
                rect = pygame.Rect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
                cropped = pygame.Surface(rect.size, pygame.SRCALPHA)
                cropped.blit(raw, (0, 0), rect)
                raw = cropped
            img = raw
            break

    _SPRITE_CACHE[key] = img
    return img


class Body:
    __slots__ = (
        "x_m",
        "y_m",
        "vx",
        "vy",
        "ax",
        "ay",
        "mass",
        "radius_px",
        "color",
        "is_static",
        "display_name",
        "trail",
    )

    def __init__(
        self,
        x_m: float,
        y_m: float,
        mass_kg: float,
        radius_px: float,
        color,
        is_static: bool = False,
        vx: float = 0.0,
        vy: float = 0.0,
        display_name: str | None = None,
    ):
        self.x_m = float(x_m)
        self.y_m = float(y_m)
        self.vx = float(vx)
        self.vy = float(vy)
        self.ax = 0.0
        self.ay = 0.0
        self.mass = float(mass_kg)
        self.radius_px = float(radius_px)
        self.color = color
        self.is_static = is_static
        self.display_name = display_name
        self.trail: list[tuple[float, float]] = []

    @property
    def x(self) -> float:
        """Playfield screen x (px); accounts for view camera."""
        from physics_constants import VIEW_CAM_PX_X, m_to_px

        return m_to_px(self.x_m) - VIEW_CAM_PX_X

    @property
    def y(self) -> float:
        from physics_constants import VIEW_CAM_PX_Y, m_to_px

        return m_to_px(self.y_m) - VIEW_CAM_PX_Y

    @property
    def radius(self) -> float:
        return self.radius_px

    def apply_gravity(self, other: Body) -> None:
        """Accumulate SI acceleration toward other (Newtonian 1/r² with softening)."""
        dx = other.x_m - self.x_m
        dy = other.y_m - self.y_m
        dist_sq = dx * dx + dy * dy
        dist_sq = max(dist_sq, EPS2_M2)
        dist = math.sqrt(dist_sq)
        inv_r3 = 1.0 / (dist * dist_sq)
        s = G_SI * other.mass * inv_r3
        self.ax += s * dx
        self.ay += s * dy

    def verlet_advance_position(self, dt: float, ax0: float, ay0: float) -> None:
        if self.is_static:
            return
        self.x_m += self.vx * dt + 0.5 * ax0 * dt * dt
        self.y_m += self.vy * dt + 0.5 * ay0 * dt * dt

    def verlet_finish_velocity(self, dt: float, ax0: float, ay0: float, ax1: float, ay1: float) -> None:
        if self.is_static:
            return
        self.vx += 0.5 * (ax0 + ax1) * dt
        self.vy += 0.5 * (ay0 + ay1) * dt

        self.trail.append((self.x_m, self.y_m))
        if len(self.trail) > 200:
            self.trail.pop(0)

    def draw(self, screen: pygame.Surface, trail_surf=None) -> None:
        from physics_constants import VIEW_CAM_PX_X, VIEW_CAM_PX_Y, m_to_px

        px = int(m_to_px(self.x_m) - VIEW_CAM_PX_X)
        py = int(m_to_px(self.y_m) - VIEW_CAM_PX_Y)
        
        if len(self.trail) > 1:
            pts = [
                (int(m_to_px(tx) - VIEW_CAM_PX_X), int(m_to_px(ty) - VIEW_CAM_PX_Y))
                for tx, ty in self.trail
            ]
            if len(pts) > 1 and trail_surf:
                for i in range(len(pts) - 1):
                    alpha = int(255 * (i / len(pts)))
                    w = max(1, int((self.radius_px // 2) * (i / len(pts))))
                    c = (*self.color, alpha)
                    try:
                        pygame.draw.line(trail_surf, c, pts[i], pts[i+1], w)
                    except ValueError:
                        pass
        
        glow_r = int(self.radius_px * 2.5)
        glow_surf = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
        for i in range(5, 0, -1):
            r = int(glow_r * (i / 5.0))
            a = int(60 / i)
            pygame.draw.circle(glow_surf, (*self.color, a), (glow_r, glow_r), r)
        screen.blit(glow_surf, (px - glow_r, py - glow_r))

        pygame.draw.circle(screen, self.color, (px, py), self.radius_px)
        pygame.draw.circle(screen, (255, 255, 255), (px, py), max(1, self.radius_px // 2))

        if self.display_name:
            sprite = _load_body_sprite(self.display_name)
            if sprite is not None:
                iw, ih = sprite.get_size()
                if iw > 0 and ih > 0:
                    diameter = self.radius_px * 2.0
                    factor = diameter / max(iw, ih)
                    dw = max(1, int(iw * factor))
                    dh = max(1, int(ih * factor))
                    scaled = pygame.transform.smoothscale(sprite, (dw, dh))
                    screen.blit(scaled, (px - dw // 2, py - dh // 2))
                    return

        pygame.draw.circle(screen, self.color, (px, py), int(self.radius_px))


def clear_accelerations(bodies: list[Body]) -> None:
    for b in bodies:
        b.ax = 0.0
        b.ay = 0.0


def accumulate_gravity(bodies: list[Body]) -> None:
    clear_accelerations(bodies)
    n = len(bodies)
    for i in range(n):
        for j in range(n):
            if i != j:
                bodies[i].apply_gravity(bodies[j])


def _inv_mass(body: Body) -> float:
    return 0.0 if body.is_static else 1.0 / body.mass


def _min_dist_m(a: Body, b: Body) -> float:
    return radius_m_from_px(a.radius_px) + radius_m_from_px(b.radius_px)


def _blend_color(c1, c2, w1: float, w2: float):
    return (
        int(min(255, (c1[0] * w1 + c2[0] * w2) / (w1 + w2))),
        int(min(255, (c1[1] * w1 + c2[1] * w2) / (w1 + w2))),
        int(min(255, (c1[2] * w1 + c2[2] * w2) / (w1 + w2))),
    )


def _merge_two(a: Body, b: Body) -> Body:
    M = a.mass + b.mass
    x_m = (a.mass * a.x_m + b.mass * b.x_m) / M
    y_m = (a.mass * a.y_m + b.mass * b.y_m) / M
    if a.is_static or b.is_static:
        vx = vy = 0.0
        is_static = True
    else:
        vx = (a.mass * a.vx + b.mass * b.vx) / M
        vy = (a.mass * a.vy + b.mass * b.vy) / M
        is_static = False
    r_px = math.sqrt(a.radius_px * a.radius_px + b.radius_px * b.radius_px)
    r_px = max(r_px, min(a.radius_px, b.radius_px))
    col = _blend_color(a.color, b.color, a.mass, b.mass)
    trail = a.trail if len(a.trail) >= len(b.trail) else b.trail
    name_a, name_b = a.display_name, b.display_name
    if name_a and name_b:
        merged_name = name_a if a.mass >= b.mass else name_b
    else:
        merged_name = name_a or name_b
    out = Body(x_m, y_m, M, r_px, col, is_static=is_static, vx=vx, vy=vy, display_name=merged_name)
    out.trail = trail[-200:]
    return out


def _fragment_two(a: Body, b: Body) -> list[Body]:
    """Inelastic COM merge then split into two halves with tangential separation."""
    if a.is_static or b.is_static:
        return []

    M = a.mass + b.mass
    x_c = (a.mass * a.x_m + b.mass * b.x_m) / M
    y_c = (a.mass * a.y_m + b.mass * b.y_m) / M
    vx_c = (a.mass * a.vx + b.mass * b.vx) / M
    vy_c = (a.mass * a.vy + b.mass * b.vy) / M

    dx = b.x_m - a.x_m
    dy = b.y_m - a.y_m
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        nx, ny = 1.0, 0.0
    else:
        nx, ny = dx / dist, dy / dist
    tx, ty = -ny, nx

    r_px = max(4.0, math.sqrt(a.radius_px * a.radius_px + b.radius_px * b.radius_px) * 0.85)
    sep_m = radius_m_from_px(r_px) * 0.6
    kick = 800.0 + random.uniform(0, 400.0)

    half = M * 0.5
    c = _blend_color(a.color, b.color, a.mass, b.mass)

    b1 = Body(
        x_c - nx * sep_m,
        y_c - ny * sep_m,
        half,
        r_px,
        c,
        vx=vx_c - tx * kick,
        vy=vy_c - ty * kick,
    )
    b2 = Body(
        x_c + nx * sep_m,
        y_c + ny * sep_m,
        half,
        r_px,
        c,
        vx=vx_c + tx * kick,
        vy=vy_c + ty * kick,
    )
    return [b1, b2]


def resolve_pair(
    a: Body,
    b: Body,
    collision_mode: str,
) -> Body | list[Body] | None:
    """
    Positional separation + impulse, or merge/fragment (returns replacement bodies).
    None = handled in place only.
    """
    if a.is_static and b.is_static:
        return None

    dx = b.x_m - a.x_m
    dy = b.y_m - a.y_m
    dist_sq = dx * dx + dy * dy
    min_d = _min_dist_m(a, b)
    min_d_sq = min_d * min_d

    if dist_sq < 1e-18:
        nx, ny = 1.0, 0.0
        dist = 0.0
    else:
        dist = math.sqrt(dist_sq)
        nx = dx / dist
        ny = dy / dist

    if dist >= min_d:
        return None

    can_merge = not a.is_static and not b.is_static and collision_mode in (
        COLLISION_MERGE,
        COLLISION_FRAGMENT,
    )

    if can_merge and collision_mode == COLLISION_MERGE:
        return _merge_two(a, b)

    if can_merge and collision_mode == COLLISION_FRAGMENT:
        return _fragment_two(a, b)

    penetration = min_d - dist
    if penetration > 0:
        if a.is_static and not b.is_static:
            b.x_m += nx * penetration
            b.y_m += ny * penetration
        elif b.is_static and not a.is_static:
            a.x_m -= nx * penetration
            a.y_m -= ny * penetration
        elif not a.is_static and not b.is_static:
            total_m = a.mass + b.mass
            a.x_m -= nx * penetration * (b.mass / total_m)
            a.y_m -= ny * penetration * (b.mass / total_m)
            b.x_m += nx * penetration * (a.mass / total_m)
            b.y_m += ny * penetration * (a.mass / total_m)

    dx = b.x_m - a.x_m
    dy = b.y_m - a.y_m
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1e-12:
        nx, ny = 1.0, 0.0
    else:
        nx = dx / dist
        ny = dy / dist

    vax = 0.0 if a.is_static else a.vx
    vay = 0.0 if a.is_static else a.vy
    vbx = 0.0 if b.is_static else b.vx
    vby = 0.0 if b.is_static else b.vy

    rel_along = (vax - vbx) * nx + (vay - vby) * ny
    if rel_along <= 0:
        return None

    if collision_mode == COLLISION_ELASTIC:
        e = 1.0
    else:
        e = RESTITUTION_INELASTIC
    # Inelastic normal bounce vs immovable body: avoids planets pinging off the huge drawn sun.
    if (a.is_static and not b.is_static) or (b.is_static and not a.is_static):
        e = 0.0

    inv_sum = _inv_mass(a) + _inv_mass(b)
    if inv_sum <= 0:
        return None

    j = (1.0 + e) * rel_along / inv_sum

    if not a.is_static:
        a.vx -= (j / a.mass) * nx
        a.vy -= (j / a.mass) * ny
    if not b.is_static:
        b.vx += (j / b.mass) * nx
        b.vy += (j / b.mass) * ny
    return None


def resolve_collisions(bodies: list[Body], collision_mode: str, passes: int = 2) -> None:
    """Pairwise resolution; merge/fragment remove originals and insert new bodies."""
    for _ in range(passes):
        restart = True
        while restart:
            restart = False
            for i in range(len(bodies)):
                for j in range(i + 1, len(bodies)):
                    rep = resolve_pair(bodies[i], bodies[j], collision_mode)
                    if isinstance(rep, Body):
                        bodies.pop(j)
                        bodies.pop(i)
                        bodies.append(rep)
                        restart = True
                        break
                    if isinstance(rep, list):
                        bodies.pop(j)
                        bodies.pop(i)
                        bodies.extend(rep)
                        restart = True
                        break
                if restart:
                    break
