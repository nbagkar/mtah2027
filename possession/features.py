"""Per-frame features computed from a Tracking. Owner: features / possessor stream.

Every feature is a 1-D float array of length T (one per tracking row). NaN means "no evidence".
Add new features here as new keys; the models only read the keys they know, so adding one never
breaks anyone else.
"""

import numpy as np


def interpolate_gaps(x, max_gap):
    """Linear interpolation across NaN runs no longer than max_gap frames."""
    x = x.astype(np.float64).copy()
    n = len(x)
    isnan = np.isnan(x)
    if not isnan.any() or isnan.all():
        return x
    idx = np.arange(n)
    good = np.flatnonzero(~isnan)
    filled = np.interp(idx, good, x[good])
    # Length of the NaN run each frame sits in.
    edges = np.diff(np.concatenate(([0], isnan.astype(np.int8), [0])))
    starts, stops = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    ok = np.zeros(n, bool)
    for a, b in zip(starts, stops):
        if b - a <= max_gap and a > 0 and b < n:
            ok[a:b] = True
    x[isnan & ok] = filled[isnan & ok]
    return x


def rolling_mean(x, half_window):
    """Centred NaN-aware moving average over +/- half_window frames."""
    if half_window <= 0:
        return x
    v = np.where(np.isnan(x), 0.0, x)
    c = (~np.isnan(x)).astype(np.float64)
    k = np.ones(2 * half_window + 1)
    num = np.convolve(v, k, "same")
    den = np.convolve(c, k, "same")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def run_length_of(mask):
    """For each frame, the length of the True-run it sits in (0 where mask is False)."""
    out = np.zeros(len(mask), np.int64)
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        out[a:b] = b - a
    return out


def compute(trk, cfg, fps=25):
    f = cfg["features"]
    L, W = trk.pitch
    ball_seen = ~np.isnan(trk.bx)
    bx = interpolate_gaps(trk.bx, f["ball_interp_max_gap"])
    by = interpolate_gaps(trk.by, f["ball_interp_max_gap"])
    ball_ok = ~np.isnan(bx)

    # Distances from every slot to the ball, then nearest per team.
    dx = trk.px - bx[:, None]
    dy = trk.py - by[:, None]
    dist = np.sqrt(dx * dx + dy * dy)
    d_home = np.where(trk.team == 0, dist, np.inf)
    d_away = np.where(trk.team == 1, dist, np.inf)
    d_home = np.nanmin(np.where(np.isnan(d_home), np.inf, d_home), axis=1)
    d_away = np.nanmin(np.where(np.isnan(d_away), np.inf, d_away), axis=1)
    d_home[~np.isfinite(d_home)] = np.nan
    d_away[~np.isfinite(d_away)] = np.nan

    # Ball speed (m/s), smoothed a little: tracking jitter makes raw diffs useless.
    vx = np.gradient(bx) * fps
    vy = np.gradient(by) * fps
    ball_speed = rolling_mean(np.sqrt(vx * vx + vy * vy), f["speed_smooth"])

    # Player motion: median slot speed per frame, then a ~1 s mean. Low = play has stopped.
    # Displacement over `lag` frames, not frame-to-frame: 15 cm of position jitter is ~5 m/s of
    # fake speed at 1-frame lag and ~0.5 m/s at 10.
    lag = f["motion_lag"]
    pspeed = np.full(trk.px.shape, np.nan, np.float32)
    ddx = trk.px[lag:] - trk.px[:-lag]
    ddy = trk.py[lag:] - trk.py[:-lag]
    pspeed[lag // 2: lag // 2 + len(ddx)] = np.sqrt(ddx * ddx + ddy * ddy) * fps / lag
    pspeed[pspeed > 12] = np.nan  # identity switches show up as teleports
    with np.errstate(all="ignore"):
        player_speed = rolling_mean(np.nanmedian(pspeed, axis=1), f["motion_smooth"])

    margin = f["out_margin_m"]
    ball_out = ball_ok & ((bx < -margin) | (bx > L + margin) | (by < -margin) | (by > W + margin))

    # Carry: the nearest player moving *with* the ball (dribbling / receiving). Relative speed of
    # ball and nearest player, both measured over the same lag so jitter cancels similarly.
    T = len(bx)
    dist_nan = np.where(np.isnan(dist), np.inf, dist)
    nearest = np.argmin(dist_nan, axis=1)
    rows = np.arange(T)
    nearest_d = dist_nan[rows, nearest]
    nearest_team = trk.team[rows, nearest].astype(np.float64)
    nearest_team[~np.isfinite(nearest_d)] = np.nan
    bvx = np.full(T, np.nan)
    bvy = np.full(T, np.nan)
    bvx[lag // 2: lag // 2 + T - lag] = (bx[lag:] - bx[:-lag]) * fps / lag
    bvy[lag // 2: lag // 2 + T - lag] = (by[lag:] - by[:-lag]) * fps / lag
    pvx_n = np.full(T, np.nan)
    pvy_n = np.full(T, np.nan)
    sel = nearest[lag // 2: lag // 2 + T - lag]
    r = rows[: T - lag]
    pvx_n[lag // 2: lag // 2 + T - lag] = (trk.px[r + lag, sel] - trk.px[r, sel]) * fps / lag
    pvy_n[lag // 2: lag // 2 + T - lag] = (trk.py[r + lag, sel] - trk.py[r, sel]) * fps / lag
    rel_speed = np.sqrt((bvx - pvx_n) ** 2 + (bvy - pvy_n) ** 2)

    n_players = np.sum(~np.isnan(trk.px), axis=1).astype(np.float64)
    missing_run = run_length_of(~ball_seen).astype(np.float64)

    return {
        "ball_seen": ball_seen.astype(np.float64),
        "ball_ok": ball_ok.astype(np.float64),
        "bx": bx, "by": by,
        "d_home": d_home, "d_away": d_away,
        "ball_speed": ball_speed,
        "player_speed": player_speed,
        "ball_out": ball_out.astype(np.float64),
        "n_players": n_players,
        "ball_missing_run": missing_run,
        "nearest_d": np.where(np.isfinite(nearest_d), nearest_d, np.nan),
        "nearest_team": nearest_team,
        "carry_rel_speed": rel_speed,
    }
