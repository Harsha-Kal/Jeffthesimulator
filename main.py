"""
Gravity Simulator — SI physics (m, kg, s), velocity Verlet, scaled display via SCALE_M_PER_PX.
"""
import math
import random
import sys

import pygame

sys._stars = [(random.uniform(0, 2000), random.uniform(0, 1500), random.uniform(0.1, 1.5)) for _ in range(300)]

from body import (
    Body,
    COLLISION_BOUNCE,
    COLLISION_ELASTIC,
    COLLISION_FRAGMENT,
    COLLISION_MERGE,
    accumulate_gravity,
    resolve_collisions,
)
from nyan_cat import NyanCatFlyby
from physics_constants import (
    AU_M,
    G_SI,
    SCALE_M_PER_PX,
    SECONDS_PER_DAY,
    SIM_SECONDS_PER_WALL_SECOND,
    TIME_WARP_DAYS_PER_MONTH,
    TIME_WARP_MONTHS_PER_WALL_SECOND,
    VIEW_CAM_PX_X,
    VIEW_CAM_PX_Y,
    adjust_view_camera_for_resize,
    circular_orbit_velocity_from_aim_m_s,
    format_accel_m_s2,
    format_length_m,
    format_speed_m_s,
    game_screen_to_m,
    m_to_px,
    strongest_attractor,
)
from ui import DragMenu

pygame.init()

MIN_W, MIN_H = 480, 360
INIT_W, INIT_H = 800, 600
WIDTH, HEIGHT = INIT_W, INIT_H
windowed_w, windowed_h = INIT_W, INIT_H
fullscreen = False

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption(
    "Gravity Simulator — 3 mo / real s (nominal) • [ ] scale • 1–4 collisions • O orbit"
)

clock = pygame.time.Clock()

menu = DragMenu(WIDTH, HEIGHT)
nyan = NyanCatFlyby(WIDTH, HEIGHT)
bodies: list[Body] = []

# Elapsed simulated time (s) while bodies exist; dt each frame scales with real frame duration.
sim_elapsed_s = 0.0
time_scale = 1.0

collision_mode = COLLISION_BOUNCE
COLLISION_LABELS = {
    COLLISION_BOUNCE: "bounce",
    COLLISION_ELASTIC: "elastic",
    COLLISION_MERGE: "merge",
    COLLISION_FRAGMENT: "fragment",
}

session_start_ms = None
_timer_font = pygame.font.SysFont("arial", 22, bold=True)
_hud_small = pygame.font.SysFont("arial", 14)
_phys_tag_font = pygame.font.SysFont("arial", 11)
_phys_panel_font = pygame.font.SysFont("arial", 13)


def _format_session_time(elapsed_ms):
    elapsed_ms = max(0, int(elapsed_ms))
    total_s = elapsed_ms // 1000
    m = total_s // 60
    s = total_s % 60
    return f"{m:02d}:{s:02d}"


def _format_sim_elapsed(sim_s: float) -> str:
    """Format integrated simulation time (same 30-day nominal month as the warp rate)."""
    if sim_s <= 0:
        return "0 d"
    mo = sim_s / (TIME_WARP_DAYS_PER_MONTH * SECONDS_PER_DAY)
    if mo >= 36:
        return f"{mo / 12.0:.3g} yr_sim (360 d/yr)"
    if mo >= 1:
        return f"{mo:.3g} mo_sim (30 d)"
    days = sim_s / SECONDS_PER_DAY
    if days >= 1:
        return f"{days:.3g} d sim"
    return f"{sim_s:.3g} s sim"


def _barycenter_m(bodies_list):
    if not bodies_list:
        return 0.0, 0.0
    M = sum(b.mass for b in bodies_list)
    if M <= 0:
        return 0.0, 0.0
    cx = sum(b.mass * b.x_m for b in bodies_list) / M
    cy = sum(b.mass * b.y_m for b in bodies_list) / M
    return cx, cy


def _draw_body_physics_tags(screen, bodies_list, com_x_m, com_y_m, sidebar_x, screen_h):
    """Compact |v| and distance from system barycentre above each body."""
    for b in bodies_list:
        ix = int(b.x)
        iy = int(b.y)
        if ix < -40 or iy < -30 or ix > sidebar_x + 40 or iy > screen_h + 20:
            continue
        spd = 0.0 if b.is_static else math.hypot(b.vx, b.vy)
        r_com = math.hypot(b.x_m - com_x_m, b.y_m - com_y_m)
        label = b.display_name or ""
        line_speed = "|v| = " + (format_speed_m_s(spd) if not b.is_static else "0 m/s")
        line_r = f"r_COM = {format_length_m(r_com)}"
        lines = ([label] if label else []) + [line_speed, line_r]
        line_h = 13
        total_h = len(lines) * line_h
        y_top = int(iy - b.radius_px - 6 - total_h)
        for i, text in enumerate(lines):
            surf = _phys_tag_font.render(text, True, (215, 230, 250))
            x = ix - surf.get_width() // 2
            x = max(4, min(x, sidebar_x - surf.get_width() - 4))
            screen.blit(surf, (x, y_top + i * line_h))


def _draw_selected_physics_panel(screen, body, bodies_list, com_x_m, com_y_m, sidebar_x, screen_h):
    """SI readout for the selected body (strongest external attractor, acceleration)."""
    if body is None or body not in bodies_list:
        return
    att = strongest_attractor(bodies_list, body.x_m, body.y_m, exclude=body)
    name = body.display_name or "Body"
    amag = math.hypot(body.ax, body.ay)
    lines = [
        f"{name}  m = {body.mass:.5g} kg",
    ]
    if not body.is_static:
        lines.append(f"|v| = {format_speed_m_s(math.hypot(body.vx, body.vy))}  (vx, vy) = ({body.vx:.5g}, {body.vy:.5g}) m/s")
        lines.append(f"x,y = {body.x_m:.5g}, {body.y_m:.5g} m  ({body.x_m / AU_M:.5g}, {body.y_m / AU_M:.5g}) AU")
    else:
        lines.append("static  v = 0")
        lines.append(f"x,y = {body.x_m:.5g}, {body.y_m:.5g} m")
    r_com = math.hypot(body.x_m - com_x_m, body.y_m - com_y_m)
    lines.append(f"r_COM = {format_length_m(r_com)} ({r_com:.5g} m)")
    if att is not None:
        dx = body.x_m - att.x_m
        dy = body.y_m - att.y_m
        r_att = math.hypot(dx, dy)
        aname = att.display_name or "attractor"
        lines.append(f"r → {aname} = {format_length_m(r_att)} ({r_att:.5g} m)")
        if r_att > 0 and att.mass > 0:
            v_circ = math.sqrt(G_SI * att.mass / r_att)
            lines.append(f"v_circ({aname}) = {format_speed_m_s(v_circ)}")
    lines.append(f"|a| = {format_accel_m_s2(amag)}  (ax, ay) = ({body.ax:.4g}, {body.ay:.4g})")
    padding = 8
    line_skip = 15
    panel_w = max(_phys_panel_font.render(s, True, (0, 0, 0)).get_width() for s in lines) + padding * 2
    panel_h = padding * 2 + len(lines) * line_skip
    x0 = 12
    if x0 + panel_w > sidebar_x - 4:
        x0 = max(4, sidebar_x - panel_w - 8)
    y0 = screen_h - panel_h - 12
    surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    surf.fill((12, 18, 38, 210))
    pygame.draw.rect(surf, (80, 140, 200, 220), surf.get_rect(), 1, border_radius=6)
    screen.blit(surf, (x0, y0))
    for i, text in enumerate(lines):
        t = _phys_panel_font.render(text, True, (230, 238, 255))
        screen.blit(t, (x0 + padding, y0 + padding + i * line_skip))


def apply_display_size(w, h, fs):
    global screen, WIDTH, HEIGHT, fullscreen
    old_gw = menu.game_w
    old_sh = menu.screen_h
    fullscreen = fs
    if fs:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        WIDTH, HEIGHT = screen.get_size()
    else:
        WIDTH = max(MIN_W, w)
        HEIGHT = max(MIN_H, h)
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    menu.resize(WIDTH, HEIGHT)
    nyan.resize(WIDTH, HEIGHT)
    adjust_view_camera_for_resize(old_gw, menu.game_w, old_sh, menu.screen_h)


def _apply_orbit_to_pending():
    """Set pending spawn velocity to circular orbit around strongest local attractor."""
    p = menu.pending
    if not p or p["item"].get("is_static"):
        return
    px, py = p["x"], p["y"]
    x_m, y_m = game_screen_to_m(px, py)
    att = strongest_attractor(bodies, x_m, y_m)
    if att is None:
        return
    aux = float(p.get("pux", 1.0))
    auy = float(p.get("puy", 0.0))
    vx, vy = circular_orbit_velocity_from_aim_m_s(x_m, y_m, att, aux, auy)
    spd = math.hypot(vx, vy)
    p["pvx"] = vx
    p["pvy"] = vy
    p["fvx"] = vx
    p["fvy"] = vy
    if spd > 1e-3:
        p["pux"] = vx / spd
        p["puy"] = vy / spd
        p["fux"] = p["pux"]
        p["fuy"] = p["puy"]
    else:
        p["pux"], p["puy"] = 1.0, 0.0
        p["fux"], p["fuy"] = 1.0, 0.0
    # Arrow length from speed vs ~30 km/s Earth-like
    ref = 30_000.0
    t = min(1.0, spd / ref)
    p["palen"] = t * 100.0
    p["falen"] = p["palen"]
    p["frozen"] = True


running = True
clock.tick(60)
try:
    while running:
        frame_ms = max(1, clock.get_time())
        # Long frames (window drag/resume) would advance sim too far in one step and destabilize orbits.
        wall_s = min(frame_ms * 0.001, 0.15)
        dt = SIM_SECONDS_PER_WALL_SECOND * time_scale * wall_s

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_F11:
                    if fullscreen:
                        apply_display_size(windowed_w, windowed_h, False)
                    else:
                        windowed_w, windowed_h = WIDTH, HEIGHT
                        apply_display_size(0, 0, True)
                if event.key == pygame.K_o:
                    _apply_orbit_to_pending()
                if event.key == pygame.K_LEFTBRACKET:
                    time_scale *= 0.5
                    time_scale = max(1e-6, time_scale)
                if event.key == pygame.K_RIGHTBRACKET:
                    time_scale = min(1e6, time_scale * 2.0)
                if event.key == pygame.K_1:
                    collision_mode = COLLISION_BOUNCE
                if event.key == pygame.K_2:
                    collision_mode = COLLISION_ELASTIC
                if event.key == pygame.K_3:
                    collision_mode = COLLISION_MERGE
                if event.key == pygame.K_4:
                    collision_mode = COLLISION_FRAGMENT

            if event.type == pygame.VIDEORESIZE and not fullscreen:
                old_gw = menu.game_w
                old_sh = menu.screen_h
                nw = max(MIN_W, event.w)
                nh = max(MIN_H, event.h)
                windowed_w, windowed_h = nw, nh
                screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
                WIDTH, HEIGHT = nw, nh
                menu.resize(WIDTH, HEIGHT)
                nyan.resize(WIDTH, HEIGHT)
                adjust_view_camera_for_resize(old_gw, menu.game_w, old_sh, menu.screen_h)

            action, payload = menu.handle_event(event, bodies)

            if action == "spawn" and payload:
                item, pos, vel = payload
                x, y = pos
                vx, vy = vel
                x_m, y_m = game_screen_to_m(x, y)
                if item.get("is_static"):
                    bodies.append(
                        Body(
                            x_m,
                            y_m,
                            mass_kg=item["mass"],
                            radius_px=item["radius"],
                            color=item["color"],
                            is_static=True,
                            display_name=item.get("name"),
                        )
                    )
                else:
                    bodies.append(
                        Body(
                            x_m,
                            y_m,
                            mass_kg=item["mass"],
                            radius_px=item["radius"],
                            color=item["color"],
                            vx=vx,
                            vy=vy,
                            display_name=item.get("name"),
                        )
                    )

            if action == "clear_all":
                bodies.clear()

            if action == "delete_body" and payload is not None:
                try:
                    bodies.remove(payload)
                except ValueError:
                    pass

        accumulate_gravity(bodies)
        ax0 = [(b.ax, b.ay) for b in bodies]

        for i, b in enumerate(bodies):
            b.verlet_advance_position(dt, ax0[i][0], ax0[i][1])

        accumulate_gravity(bodies)
        for i, b in enumerate(bodies):
            b.verlet_finish_velocity(dt, ax0[i][0], ax0[i][1], b.ax, b.ay)

        # After integration so per-body ax0 still matches (merges replace bodies).
        resolve_collisions(bodies, collision_mode)

        nyan.update(frame_ms)

        now_ms = pygame.time.get_ticks()
        if len(bodies) > 0:
            if session_start_ms is None:
                session_start_ms = now_ms
            session_elapsed_ms = now_ms - session_start_ms
            sim_elapsed_s += dt
        else:
            session_start_ms = None
            session_elapsed_ms = 0
            sim_elapsed_s = 0.0

        screen.fill((4, 6, 12))
        
        import math
        for i, (sx, sy, sz) in enumerate(sys._stars):
            sx = (sx - sz * 0.3) % WIDTH
            sys._stars[i] = (sx, sy, sz)
            t = pygame.time.get_ticks() * 0.002
            twinkle = math.sin(t + sx * 0.1) * 0.5 + 0.5
            c = int(30 + 50 * sz + twinkle * 80 * sz)
            c_color = (min(255, c), min(255, c), min(255, c + 60))
            pygame.draw.circle(screen, c_color, (int(sx), int(sy)), max(1, int(sz)))
            
        trail_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        for body in bodies:
            body.draw(screen, trail_surf=trail_surf)
            
        screen.blit(trail_surf, (0, 0))

        com_x, com_y = _barycenter_m(bodies)
        _draw_body_physics_tags(screen, bodies, com_x, com_y, menu.sidebar_x, HEIGHT)
        _draw_selected_physics_panel(screen, menu.selected_body, bodies, com_x, com_y, menu.sidebar_x, HEIGHT)
        if bodies:
            cx = int(m_to_px(com_x) - VIEW_CAM_PX_X)
            cy = int(m_to_px(com_y) - VIEW_CAM_PX_Y)
            if 0 <= cx < menu.sidebar_x and 0 <= cy < HEIGHT:
                pygame.draw.line(screen, (100, 180, 255), (cx - 8, cy), (cx + 8, cy), 2)
                pygame.draw.line(screen, (100, 180, 255), (cx, cy - 8), (cx, cy + 8), 2)

        real_clock = _format_session_time(session_elapsed_ms)
        sim_clock = _format_sim_elapsed(sim_elapsed_s) if bodies else "—"
        timer_text = f"{real_clock}  ·  {sim_clock}"
        timer_surf = _timer_font.render(timer_text, True, (220, 232, 255))
        screen.blit(timer_surf, (12, 10))

        earth_sun_px = AU_M / SCALE_M_PER_PX
        rate_mo_s = TIME_WARP_MONTHS_PER_WALL_SECOND * time_scale
        hud_lines = [
            (
                f"Δt = {dt:.4g} s_sim this frame • rate {rate_mo_s:g} mo / real s "
                f"({SIM_SECONDS_PER_WALL_SECOND * time_scale:.4g} s_sim / real s)"
            ),
            (
                f"Space: 1 px = {SCALE_M_PER_PX:.3g} m (~1 AU = {earth_sun_px:.3g} px)  ·  "
                f"|v|, r in SI (true orbit speeds; time warp only steps integration)"
            ),
            f"G = {G_SI:.5e} m³/(kg·s²)   collisions: {COLLISION_LABELS[collision_mode]} [1–4]  [ ] × time",
        ]
        hy = 38
        for line in hud_lines:
            s = _hud_small.render(line, True, (160, 190, 220))
            screen.blit(s, (12, hy))
            hy += 16

        menu.draw(screen, bodies)
        nyan.draw(screen)

        pygame.display.flip()
        clock.tick(60)

except KeyboardInterrupt:
    pass
finally:
    pygame.quit()
sys.exit(0)
