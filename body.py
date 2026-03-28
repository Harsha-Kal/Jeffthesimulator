import pygame
import math

G = 0.5  # gravitational constant (tweak later)

class Body:
    def __init__(self, x, y, mass, radius, color, is_static=False, vx=0.0, vy=0.0):
        self.x = x
        self.y = y
        self.vx = float(vx)
        self.vy = float(vy)
        self.ax = 0
        self.ay = 0
        self.mass = mass
        self.radius = radius
        self.color = color
        self.is_static = is_static  # sun can be static

        self.trail = []

    def apply_gravity(self, other):
        dx = other.x - self.x
        dy = other.y - self.y

        dist_sq = dx*dx + dy*dy
        if dist_sq < 25:
            dist_sq = 25  # avoid explosion

        dist = math.sqrt(dist_sq)

        force = G * self.mass * other.mass / dist_sq

        fx = force * dx / dist
        fy = force * dy / dist

        self.ax += fx / self.mass
        self.ay += fy / self.mass

    def update(self, dt):
        if self.is_static:
            return

        self.vx += self.ax * dt
        self.vy += self.ay * dt

        self.x += self.vx * dt
        self.y += self.vy * dt

        self.trail.append((int(self.x), int(self.y)))
        if len(self.trail) > 200:
            self.trail.pop(0)

    def draw(self, screen):
        if len(self.trail) > 1:
            pygame.draw.lines(screen, self.color, False, self.trail, 1)

        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)


RESTITUTION = 0.92


def _inv_mass(body):
    return 0.0 if body.is_static else 1.0 / body.mass


def resolve_pair(a, b, restitution=RESTITUTION):
    if a.is_static and b.is_static:
        return

    dx = b.x - a.x
    dy = b.y - a.y
    dist_sq = dx * dx + dy * dy
    min_dist = a.radius + b.radius

    if dist_sq < 1e-12:
        nx, ny = 1.0, 0.0
        dist = 0.0
    else:
        dist = math.sqrt(dist_sq)
        nx = dx / dist
        ny = dy / dist

    if dist >= min_dist:
        return

    penetration = min_dist - dist
    if penetration > 0:
        if a.is_static and not b.is_static:
            b.x += nx * penetration
            b.y += ny * penetration
        elif b.is_static and not a.is_static:
            a.x -= nx * penetration
            a.y -= ny * penetration
        elif not a.is_static and not b.is_static:
            total_m = a.mass + b.mass
            a.x -= nx * penetration * (b.mass / total_m)
            a.y -= ny * penetration * (b.mass / total_m)
            b.x += nx * penetration * (a.mass / total_m)
            b.y += ny * penetration * (a.mass / total_m)

    dx = b.x - a.x
    dy = b.y - a.y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1e-8:
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
        return

    inv_sum = _inv_mass(a) + _inv_mass(b)
    if inv_sum <= 0:
        return

    j = (1.0 + restitution) * rel_along / inv_sum

    if not a.is_static:
        a.vx -= (j / a.mass) * nx
        a.vy -= (j / a.mass) * ny
    if not b.is_static:
        b.vx += (j / b.mass) * nx
        b.vy += (j / b.mass) * ny


def resolve_collisions(bodies, passes=2):
    n = len(bodies)
    for _ in range(passes):
        for i in range(n):
            for j in range(i + 1, n):
                resolve_pair(bodies[i], bodies[j])