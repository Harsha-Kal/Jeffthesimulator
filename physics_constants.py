"""
SI constants and scale: real Newtonian gravity with meters / kg / seconds.
1 screen pixel represents SCALE_M_PER_PX meters so solar-system distances fit the window.
"""
from __future__ import annotations

import math

# Universal gravitational constant (N⋅m²/kg², CODATA 2018)
G_SI = 6.67430e-11

# 1 px ↔ this many meters (Earth–Sun ~1.5e11 m → ~150 px)
SCALE_M_PER_PX = 1e9

# Minimum center separation (m²) for gravity softening — ~2 px scale
_GRAV_SOFTEN_M = 2.0 * SCALE_M_PER_PX
EPS2_M2 = _GRAV_SOFTEN_M * _GRAV_SOFTEN_M

# IAU 2012 astronomical unit (exact definition tied to Gaussian constant context; nominal value)
AU_M = 1.495_978_707e11

# Wall clock: simulated seconds advanced per one real second at time_scale=1 (3 × 30-day months).
SECONDS_PER_DAY = 86400.0
TIME_WARP_MONTHS_PER_WALL_SECOND = 3.0
TIME_WARP_DAYS_PER_MONTH = 30.0
SIM_SECONDS_PER_WALL_SECOND = (
    TIME_WARP_MONTHS_PER_WALL_SECOND * TIME_WARP_DAYS_PER_MONTH * SECONDS_PER_DAY
)

# World-pixel offset for the playfield: screen (0,0) shows world pixel (VIEW_CAM_PX_X, VIEW_CAM_PX_Y).
# Same units as m_to_px (metres / SCALE_M_PER_PX). Updated when the window is resized so the
# playfield center keeps looking at the same region of space.
VIEW_CAM_PX_X: float = 0.0
VIEW_CAM_PX_Y: float = 0.0


def adjust_view_camera_for_resize(
    old_game_w: float, new_game_w: float, old_screen_h: int, new_screen_h: int
) -> None:
    """Pan camera so the point under the playfield center stays fixed after a size change."""
    global VIEW_CAM_PX_X, VIEW_CAM_PX_Y
    VIEW_CAM_PX_X += (old_game_w - new_game_w) / 2.0
    VIEW_CAM_PX_Y += (old_screen_h - new_screen_h) / 2.0


def game_screen_to_m(sx: float, sy: float) -> tuple[float, float]:
    """Convert playfield screen pixels (top-left of window) to world metres using the view camera."""
    return px_to_m(sx + VIEW_CAM_PX_X), px_to_m(sy + VIEW_CAM_PX_Y)


def px_to_m(px: float) -> float:
    return px * SCALE_M_PER_PX


def m_to_px(m: float) -> float:
    return m / SCALE_M_PER_PX


def radius_m_from_px(radius_px: float) -> float:
    return radius_px * SCALE_M_PER_PX


def strongest_attractor(bodies, x_m: float, y_m: float, exclude=None):
    """
    Body that produces the largest gravitational acceleration magnitude at (x_m, y_m).
    If ``exclude`` is a Body in the list, it is skipped (e.g. querying a body's own position).
    """
    best = None
    best_a = 0.0
    for b in bodies:
        if b is exclude:
            continue
        dx = b.x_m - x_m
        dy = b.y_m - y_m
        r2 = dx * dx + dy * dy
        r2 = max(r2, EPS2_M2)
        a = G_SI * b.mass / r2
        if a > best_a:
            best_a = a
            best = b
    return best


def circular_orbit_velocity_m_s(x_m: float, y_m: float, attractor):
    """
    Speed sqrt(G*M/r) tangential to the radius from attractor to (x_m, y_m).
    Direction is +90° from attractor→point in screen coords (y down): (dy, -dx).
    """
    if attractor is None:
        return 0.0, 0.0
    dx = x_m - attractor.x_m
    dy = y_m - attractor.y_m
    r2 = dx * dx + dy * dy
    r2 = max(r2, EPS2_M2)
    r = math.sqrt(r2)
    v = math.sqrt(G_SI * attractor.mass / r)
    tx = dy / r
    ty = -dx / r
    return tx * v, ty * v


def circular_orbit_velocity_from_aim_m_s(
    x_m: float,
    y_m: float,
    attractor,
    aim_ux: float,
    aim_uy: float,
) -> tuple[float, float]:
    """
    Circular orbit speed sqrt(G*M/r); velocity is along the tangential axis (perpendicular
    to attractor→body) with sign chosen so it matches the mouse/aim direction in screen space.
    """
    if attractor is None:
        return 0.0, 0.0
    dx = x_m - attractor.x_m
    dy = y_m - attractor.y_m
    r2 = dx * dx + dy * dy
    r2 = max(r2, EPS2_M2)
    r = math.sqrt(r2)
    v = math.sqrt(G_SI * attractor.mass / r)
    tx = dy / r
    ty = -dx / r
    aim_len2 = aim_ux * aim_ux + aim_uy * aim_uy
    if aim_len2 < 1e-12:
        return tx * v, ty * v
    dot = aim_ux * tx + aim_uy * ty
    sgn = 1.0 if dot >= 0.0 else -1.0
    return sgn * tx * v, sgn * ty * v


def format_length_m(d: float) -> str:
    """Format a distance in metres (km / Mm / AU as appropriate)."""
    ad = abs(d)
    if ad >= 0.01 * AU_M:
        return f"{d / AU_M:.5g} AU"
    if ad >= 1e6:
        return f"{d / 1e6:.5g} Mm"
    if ad >= 1e3:
        return f"{d / 1e3:.5g} km"
    return f"{d:.5g} m"


def format_speed_m_s(v: float) -> str:
    """Format speed in m/s (km/s when large)."""
    av = abs(v)
    if av >= 1000.0:
        return f"{v / 1000.0:.5g} km/s"
    return f"{v:.5g} m/s"


def format_accel_m_s2(a: float) -> str:
    """Format acceleration magnitude in m/s²."""
    aa = abs(a)
    if aa >= 1e-3:
        return f"{a:.4g} m/s²"
    if aa >= 1e-9:
        return f"{a:.4e} m/s²"
    return f"{a:.2e} m/s²"
