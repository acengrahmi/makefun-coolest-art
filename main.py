#!/usr/bin/env python3
"""Coolest-art entry, v2: a bold, clean synthwave / outrun scene.

Composition: a huge gradient sun with crisp horizontal cuts sinking
behind two neon-rimmed mountain ridges, over a reflective perspective
grid, under a star field, in a rich indigo-to-magenta palette. Strong
symmetry, strong contrast, and shapes big enough to stay striking at
thumbnail size.

Pure Python standard library, no network, fully deterministic.
Renders one PNG to argv[1] (default /output/entry.png).

Technique: one procedural pass over the framebuffer (sky, sun, ridges,
floor grid and sun reflection are all analytic), then a small star
pass, then a vignette. Ridge lines come from integer value noise, so
the output is byte-identical on every run.
"""

import math
import os
import struct
import sys
import zlib

W = 800
H = 800
HORIZON = 512  # y of the horizon line; floor lives below it

FR = [0.0] * (W * H)
FG = [0.0] * (W * H)
FB = [0.0] * (W * H)

# Sun geometry: one dominant disc, centred on the horizon axis.
SUN_X = 400.0
SUN_Y = 478.0
SUN_R = 205.0


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(c1, c2, t):
    return (lerp(c1[0], c2[0], t),
            lerp(c1[1], c2[1], t),
            lerp(c1[2], c2[2], t))


def smooth(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def gradient(stops, t):
    """Piecewise-linear colour ramp; stops are (position, colour)."""
    if t <= stops[0][0]:
        return stops[0][1]
    for k in range(1, len(stops)):
        p1, c1 = stops[k]
        if t <= p1:
            p0, c0 = stops[k - 1]
            return lerp3(c0, c1, (t - p0) / (p1 - p0))
    return stops[-1][1]


SKY_STOPS = [
    (0.00, (0.012, 0.000, 0.086)),   # deep space indigo
    (0.30, (0.075, 0.012, 0.263)),
    (0.52, (0.231, 0.043, 0.427)),
    (0.64, (0.482, 0.086, 0.478)),   # magenta bloom at the horizon
]

SUN_STOPS = [
    (0.00, (1.000, 0.847, 0.220)),   # hot yellow crown
    (0.45, (1.000, 0.545, 0.259)),
    (0.75, (1.000, 0.235, 0.475)),
    (1.00, (0.937, 0.106, 0.541)),   # magenta base
]


def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        base = y * W
        for x in range(W):
            i = base + x
            raw.append(int(clamp(FR[i]) * 255.0 + 0.5))
            raw.append(int(clamp(FG[i]) * 255.0 + 0.5))
            raw.append(int(clamp(FB[i]) * 255.0 + 0.5))
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", comp)
           + chunk(b"IEND", b""))
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)


# ---------------------------------------------------------------------------
# Deterministic integer value noise, used for the mountain ridges and
# for scattering the stars. No library randomness anywhere: the same
# integers come out on every machine and every run.
# ---------------------------------------------------------------------------

def hash01(n):
    """Integer hash -> [0, 1)."""
    n = (n * 2654435761) & 0xFFFFFFFF
    n ^= n >> 15
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 13
    return (n & 0xFFFFFF) / 16777216.0


def vnoise(x, scale, seed):
    """Smooth 1-D value noise sampled at pixel coordinate x."""
    xi = int(x // scale)
    f = (x - xi * scale) / scale
    a = hash01(xi + seed * 7919)
    b = hash01(xi + 1 + seed * 7919)
    t = f * f * (3.0 - 2.0 * f)
    return a + (b - a) * t


def build_ridges():
    """Two ridge lines, one y per column. The back ridge sits higher
    and lighter; the front ridge lower, darker, and chunkier."""
    back = []
    front = []
    for x in range(W):
        # ridged noise (1 - |2n - 1|) gives peaky crests instead of
        # rolling hills; a little ordinary noise breaks the regularity
        peak_b = 1.0 - abs(2.0 * vnoise(x, 62, 3) - 1.0)
        b = (470.0 - 80.0 * peak_b
             - 22.0 * vnoise(x, 23, 5) - 6.0 * vnoise(x, 9, 7))
        peak_f = 1.0 - abs(2.0 * vnoise(x, 48, 11) - 1.0)
        f = (506.0 - 58.0 * peak_f
             - 18.0 * vnoise(x, 19, 13) - 5.0 * vnoise(x, 8, 17))
        back.append(b)
        front.append(f)
    return back, front


RIDGE_BACK, RIDGE_FRONT = build_ridges()


def slit_alpha(y):
    """How much of the sun is cut away at row y: 0 = solid sun,
    1 = fully cut. Only the lower half is cut; the cuts widen and
    thicken as they descend, the classic outrun look. The mask only
    depends on y, and its edges are anti-aliased over ~2 px."""
    if y <= SUN_Y + 6:
        return 0.0
    u = (y - SUN_Y) / SUN_R            # 0 at centre -> 1 at base
    f = (u * 9.0) % 1.0                # position inside one band
    duty = 0.05 + 0.36 * u             # fraction of the band that is cut
    step_px = 9.0 / SUN_R              # df per pixel of y
    if f < duty:
        dist = min(f, duty - f) / step_px
        return clamp(0.5 + dist)
    dist = min(f - duty, 1.0 - f) / step_px
    return clamp(0.5 - dist)


def build_stars():
    """(x, y, radius, brightness) tuples in the sky, kept clear of the
    sun's disc and denser toward the top of the frame."""
    stars = []
    n = 0
    while len(stars) < 150:
        n += 1
        x = hash01(n * 3 + 101) * W
        y = hash01(n * 3 + 202) ** 1.4 * (HORIZON - 40)
        d = math.hypot(x - SUN_X, y - SUN_Y)
        if d < SUN_R + 14:
            continue
        r = 0.8 + 1.5 * hash01(n * 3 + 303)
        b = 0.35 + 0.65 * hash01(n * 3 + 404)
        stars.append((x, y, r, b))
    return stars


STARS = build_stars()


# ---------------------------------------------------------------------------
# The scene itself.
# ---------------------------------------------------------------------------

def sky_color(y):
    return gradient(SKY_STOPS, y / HORIZON)


def floor_color(x, y):
    """The outrun floor: near-black violet, a magenta bloom at the
    horizon, a glowing perspective grid, and the sun's shimmering
    reflection running down the middle."""
    v = y - HORIZON + 1.0                    # 1 at the horizon
    r = 0.048 + 0.014 * (v / (H - HORIZON))  # faint violet deepening
    g = 0.004
    b = 0.105 - 0.035 * (v / (H - HORIZON))
    bloom = math.exp(-v / 55.0)
    r += 0.42 * bloom
    g += 0.07 * bloom
    b += 0.30 * bloom

    # perspective depth, compressed toward the horizon
    pz = 900.0 / (v + 24.0)
    dpz = 900.0 / ((v + 24.0) * (v + 24.0))   # |d(pz)/dy| per pixel
    fh = (pz * 1.5) % 1.0
    dh = min(fh, 1.0 - fh)
    line_h = clamp(1.0 - dh / max(dpz * 1.5 * 1.6, 0.012))
    u = (x - SUN_X) * pz / 60.0
    fv = u % 1.0
    dv = min(fv, 1.0 - fv)
    du = pz / 60.0                           # du per pixel of x
    line_v = clamp(1.0 - dv / max(du * 1.7, 0.05))
    # grid lines converge and dim toward the horizon (pz is large
    # there) and burn brightest down at the viewer's feet
    fade = clamp((36.0 - pz) / 30.0)
    grid = max(line_h, line_v) * fade
    r += 0.08 * grid
    g += 0.88 * grid
    b += 1.00 * grid

    # sun reflection: a warm column that breaks up on the grid lines
    dx = abs(x - SUN_X)
    refl = math.exp(-dx / 85.0) * math.exp(-v / 230.0)
    shimmer = 0.55 + 0.45 * line_h
    r += 0.95 * refl * shimmer
    g += 0.27 * refl * shimmer
    b += 0.40 * refl * shimmer
    return (r, g, b)


def paint_scene():
    slit = [slit_alpha(y + 0.5) for y in range(H)]
    for y in range(H):
        py = y + 0.5
        base = y * W
        sky = sky_color(min(py, HORIZON)) if py <= HORIZON else None
        for x in range(W):
            px = x + 0.5
            if py <= HORIZON:
                col = sky
            else:
                col = floor_color(px, py)

            d = math.hypot(px - SUN_X, py - SUN_Y)

            # halo around the sun, added before the ridges so the
            # mountains bite into it
            if d > SUN_R:
                halo = math.exp(-(d - SUN_R) / 105.0)
                col = (col[0] + 0.52 * halo,
                       col[1] + 0.14 * halo,
                       col[2] + 0.30 * halo)

            # mountain ridges with a hot neon rim along the crest;
            # they stand on the horizon, so they are clipped to the
            # sky band and never paint over the floor
            if py <= HORIZON:
                rb = RIDGE_BACK[x]
                if py > rb:
                    t = clamp((py - rb) / 130.0)
                    col = lerp3((0.262, 0.082, 0.447),
                                (0.086, 0.016, 0.208), t)
                    rim = clamp(1.0 - (py - rb) / 2.6)
                    col = lerp3(col, (0.98, 0.36, 0.66), rim * 0.85)
                rf = RIDGE_FRONT[x]
                if py > rf:
                    t = clamp((py - rf) / 110.0)
                    col = lerp3((0.165, 0.051, 0.337),
                                (0.055, 0.012, 0.145), t)
                    rim = clamp(1.0 - (py - rf) / 3.2)
                    col = lerp3(col, (0.50, 0.82, 1.00), rim * 0.8)

            # the sun disc itself, on top of everything so far, with
            # its lower half sliced by the slit mask
            if d < SUN_R + 1.0:
                cov = clamp(SUN_R + 0.5 - d)
                if cov > 0.0:
                    t = clamp((py - (SUN_Y - SUN_R)) / (2.0 * SUN_R))
                    sun = gradient(SUN_STOPS, t)
                    a = cov * (1.0 - slit[y])
                    if a > 0.0:
                        ia = 1.0 - a
                        col = (col[0] * ia + sun[0] * a,
                               col[1] * ia + sun[1] * a,
                               col[2] * ia + sun[2] * a)

            i = base + x
            FR[i] = col[0]
            FG[i] = col[1]
            FB[i] = col[2]


def paint_stars():
    for (sx, sy, sr, bright) in STARS:
        x0 = max(0, int(sx - sr - 2))
        x1 = min(W - 1, int(sx + sr + 2))
        y0 = max(0, int(sy - sr - 2))
        y1 = min(H - 1, int(sy + sr + 2))
        for y in range(y0, y1 + 1):
            base = y * W
            for x in range(x0, x1 + 1):
                d = math.hypot(x + 0.5 - sx, y + 0.5 - sy)
                a = clamp(1.0 - d / (sr + 0.8))
                a = a * a * bright * 0.9
                if a <= 0.0:
                    continue
                i = base + x
                FR[i] = FR[i] * (1 - a) + a
                FG[i] = FG[i] * (1 - a) + a * 0.97
                FB[i] = FB[i] * (1 - a) + a * 1.00


def vignette():
    for y in range(H):
        dy = (y - H / 2) / (H / 2)
        base = y * W
        for x in range(W):
            dx = (x - W / 2) / (W / 2)
            v = 1.0 - 0.24 * clamp(dx * dx + dy * dy - 0.45)
            i = base + x
            FR[i] *= v
            FG[i] *= v
            FB[i] *= v


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    paint_scene()
    paint_stars()
    vignette()
    write_png(path)


if __name__ == "__main__":
    main()
