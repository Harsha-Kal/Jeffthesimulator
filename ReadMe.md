# Gravity Simulator

## Run

On macOS: `python3 main.py`  
Elsewhere: `python main.py` (if `python` is Python 3)

---

## How the physics works

The simulation uses **classical Newtonian N-body gravity** in **SI units** internally: positions and distances in **metres**, masses in **kilograms**, time in **seconds**, speeds in **m/s**, and accelerations in **m/s²**. What you see on screen is a **scaled projection** of that world, not a separate “game physics” model.

### Units, constant, and map scale

- **Gravitational constant** `G` is the CODATA value (≈ 6.67430×10⁻¹¹ m³/(kg·s²)), so forces and orbit speeds match real gravity for the masses you place.
- **Pixel scale**: one screen pixel along an axis corresponds to a fixed length in metres (`SCALE_M_PER_PX`, default 10⁹ m/px). That compresses solar-system distances into a window (Earth–Sun ≈ 1 AU ≈ 1.5×10¹¹ m shows up as on the order of 150 px).
- **Astronomical unit** is available for display and labels (nominal AU in metres).

### Gravity model

- Each pair of bodies contributes **mutual Newtonian attraction**: acceleration on body *i* from body *j* is proportional to `G * m_j / r²` along the line from *i* toward *j*, with **vector form** implemented using `1/r³` times the separation vector so direction and magnitude are consistent in 2D.
- **Softening**: the squared distance used in the denominator is clamped to at least a small minimum `EPS2_M2` (derived from a few pixels in metres). That avoids infinite acceleration when centres are extremely close and stabilizes very tight approaches; it is **not** full general relativity or tidal stress.

All non-static bodies feel **every other body** each step (full pairwise N-body gravity, not “only orbit the Sun”).

### Time integration (velocity Verlet)

Each frame:

1. Compute accelerations from the current positions and **save** them as `(ax0, ay0)`.
2. **Advance positions**: `x += v*dt + 0.5*a0*dt²` (and same for `y`).
3. Recompute accelerations at the **new** positions.
4. **Update velocities**: `v += 0.5*(a0 + a1)*dt` (and same for `vy`).

This is the **velocity Verlet** scheme. It is symplectic-ish, good for long-lived orbits compared to naive Euler, though very large `dt` or extreme close encounters can still misbehave.

### Simulation time vs wall clock

- The intended nominal rate is configured so that at `time_scale = 1`, about **three 30-day “months” of simulated time** pass per **one real second** of wall clock (see `SIM_SECONDS_PER_WALL_SECOND` in code). That is a **time warp** so you can watch orbits; spatial SI quantities are **not** scaled down to match an arcade speed—the integration just takes bigger `dt`.
- **`time_scale`** (keyboard `[` / `]`) multiplies how many simulated seconds elapse per real second.
- **`dt` per frame** is `SIM_SECONDS_PER_WALL_SECOND * time_scale * wall_seconds_this_frame`, with a **cap** on how large one frame’s `wall_seconds` can be (so a long hitch when dragging the window does not inject a huge single step).

### Collisions

Bodies are **circles** in the plane. **Radii** are stored in **pixels** for drawing, but **contact distance** is converted to **metres** (`radius_px * SCALE_M_PER_PX`) for overlap tests, so collision geometry matches the same world scale as gravity.

**Modes** (keys 1–4):

- **Bounce** (slightly inelastic): normal impulse with coefficient of restitution below 1 (see `RESTITUTION_INELASTIC` in `body.py`); separating motion along the normal is only corrected if bodies are approaching. **Static** bodies use a fully inelastic normal response against mobiles so huge masses do not “ping” away unrealistically.
- **Elastic**: same impulse logic with effectively perfect restitution along the normal.
- **Merge**: inelastic combination of the pair into one body—**mass-weighted centre of mass** for position, **mass-weighted average velocity** for the merged velocity (unless one part is static), blended colour and a combined radius rule; one display name is kept when both had names.
- **Fragment**: first merges the pair in the centre-of-mass sense, then **splits** into two half-mass bodies with a tangential separation kick (partly randomized). Static bodies do not fragment this way.

Overlapping pairs get **positional correction** along the contact normal (split by mass for two mobiles; the mobile moves off a static). Then velocity impulses are applied for bounce/elastic.

### Static bodies

**Static** bodies do not move (`verlet_*` no-ops). They still **attract** others gravitationally. Their **effective velocity** in collision routines is zero.

### Helpers tied to physics

- **Strongest attractor** at a point: the body that gives the largest gravitational acceleration magnitude there (used for HUD and spawn tools).
- **Circular orbit speed** around a given attractor: `v = sqrt(G*M/r)` with tangential direction consistent with screen coordinates (y downward); spawn/orbit assist can align tangential direction with an aim vector (e.g. mouse).
- **Barycentre** of the system uses mass-weighted average position; the HUD can show distance of each body from that point.

### Visuals vs truth

Trails and circle sizes are for **readability**; they do not change `G` or the equations. The **physics panel** and tags show SI speed, acceleration components, distances, and circular-orbit speed for the dominant attractor where applicable.
