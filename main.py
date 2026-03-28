import pygame
import sys
from body import Body, resolve_collisions
from nyan_cat import NyanCatFlyby
from ui import DragMenu

pygame.init()

MIN_W, MIN_H = 480, 360
INIT_W, INIT_H = 800, 600
WIDTH, HEIGHT = INIT_W, INIT_H
windowed_w, windowed_h = INIT_W, INIT_H
fullscreen = False

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Gravity Simulator — drag edges to resize, F11 fullscreen")

clock = pygame.time.Clock()

menu = DragMenu(WIDTH, HEIGHT)
nyan = NyanCatFlyby(WIDTH, HEIGHT)
bodies = []

DT = 0.1

session_start_ms = None
_timer_font = pygame.font.SysFont("arial", 22, bold=True)


def _format_session_time(elapsed_ms):
    elapsed_ms = max(0, int(elapsed_ms))
    total_s = elapsed_ms // 1000
    m = total_s // 60
    s = total_s % 60
    return f"{m:02d}:{s:02d}"


def apply_display_size(w, h, fs):
    global screen, WIDTH, HEIGHT, fullscreen
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


running = True
clock.tick(60)
try:
    while running:
        frame_ms = max(1, clock.get_time())

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

            if event.type == pygame.VIDEORESIZE and not fullscreen:
                nw = max(MIN_W, event.w)
                nh = max(MIN_H, event.h)
                windowed_w, windowed_h = nw, nh
                screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
                WIDTH, HEIGHT = nw, nh
                menu.resize(WIDTH, HEIGHT)
                nyan.resize(WIDTH, HEIGHT)

            action, payload = menu.handle_event(event, bodies)

            if action == "spawn" and payload:
                item, pos, vel = payload
                x, y = pos
                vx, vy = vel
                if item.get("is_static"):
                    bodies.append(
                        Body(x, y, mass=item["mass"], radius=item["radius"], color=item["color"], is_static=True)
                    )
                else:
                    bodies.append(
                        Body(
                            x,
                            y,
                            mass=item["mass"],
                            radius=item["radius"],
                            color=item["color"],
                            vx=vx,
                            vy=vy,
                        )
                    )

            if action == "clear_all":
                bodies.clear()

            if action == "delete_body" and payload is not None:
                try:
                    bodies.remove(payload)
                except ValueError:
                    pass

        # Physics step
        for body in bodies:
            body.ax = 0
            body.ay = 0

        for i in range(len(bodies)):
            for j in range(len(bodies)):
                if i != j:
                    bodies[i].apply_gravity(bodies[j])

        for body in bodies:
            body.update(DT)

        resolve_collisions(bodies)

        nyan.update(frame_ms)

        now_ms = pygame.time.get_ticks()
        if len(bodies) > 0:
            if session_start_ms is None:
                session_start_ms = now_ms
            session_elapsed_ms = now_ms - session_start_ms
        else:
            session_start_ms = None
            session_elapsed_ms = 0

        # Draw
        screen.fill((0, 0, 0))

        for body in bodies:
            body.draw(screen)

        timer_text = _format_session_time(session_elapsed_ms)
        timer_surf = _timer_font.render(timer_text, True, (220, 232, 255))
        screen.blit(timer_surf, (12, 10))

        menu.draw(screen, bodies)
        nyan.draw(screen)

        pygame.display.flip()
        clock.tick(60)

except KeyboardInterrupt:
    pass
finally:
    pygame.quit()
sys.exit(0)
