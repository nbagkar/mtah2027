"""Alive vs dead evidence, as a per-frame log-odds that the ball is DEAD. Owner: dead-ball stream.

Positive = dead, negative = alive, 0 = no opinion. The segmenter combines this with the
possessor's evidence; nothing here makes a final decision.

Ideas not yet in (each is a self-contained PR):
  - Smart Tagging SET PIECES: the frames just before a restart are dead (needs team agreement:
    our dev games have no Smart Tagging, so nothing on it could be tuned).
  - kickoff detection: both teams in their own halves, ball on the centre spot.
"""

import numpy as np

# Laws of the Game dimensions (metres). Fixed by the rules, not fitted to any data.
GOAL_AREA_DEPTH = 5.5
GOAL_AREA_HALF_WIDTH = 9.16  # 7.32 / 2 + 5.5


def restart_distance(bx, by, pitch):
    """Distance (m) from the ball to the nearest place a restart is taken from.

    Restart spots: a touchline (throw-in), a corner (corner kick), the goal area (goal kick) and
    the centre spot (kick-off). Free kicks can be anywhere, so they aren't covered. NaN where the
    ball position is unknown. Coordinates: origin at a corner, x along the length (0..L).
    """
    L, W = pitch
    touch = np.minimum(np.abs(by), np.abs(W - by))
    cx = np.minimum(np.abs(bx), np.abs(L - bx))
    cy = touch
    corner = np.sqrt(cx * cx + cy * cy)
    # Goal area: 0 inside the 5.5 m box, else distance to it.
    gx = np.maximum(cx - GOAL_AREA_DEPTH, 0.0)
    gy = np.maximum(np.abs(by - W / 2) - GOAL_AREA_HALF_WIDTH, 0.0)
    goal_area = np.sqrt(gx * gx + gy * gy)
    centre = np.sqrt((bx - L / 2) ** 2 + (by - W / 2) ** 2)
    return np.minimum.reduce([touch, corner, goal_area, centre])


def dead_logodds(feat, cfg):
    c = cfg["deadball"]
    out = np.zeros(len(feat["ball_seen"]))

    # Ball clearly outside the pitch.
    out += c["w_ball_out"] * feat["ball_out"]

    # Players barely moving: the strongest stoppage signal available without the ball.
    ps = feat["player_speed"]
    slow = np.where(np.isnan(ps), 0.0, (c["slow_speed"] - ps) / c["slow_scale"])
    out += c["w_slow"] * np.clip(slow, -2.0, 2.0)

    # Long ball absence is weak evidence of a stoppage (the camera / tracker lost it).
    # With long_missing_needs_slow it counts only as far as the players are also slow: added on
    # its own, it nearly cancels the running-players term, and the dev score then swings by
    # 0.08 between neighbouring settings (experiments/LOG.md, 2026-11-12).
    long_missing = (feat["ball_missing_run"] > c["missing_run_frames"]).astype(float)
    if c.get("long_missing_needs_slow", False):
        gate = np.where(np.isnan(ps), 0.0,
                        np.clip((c["missing_slow_speed"] - ps) / c["slow_scale"], 0.0, 1.0))
        long_missing = long_missing * gate
    out += c["w_long_missing"] * long_missing

    # A moving ball is alive. moving_ball_1s measures it over ~1 s, so ball jitter can't fake it.
    bs = feat["ball_speed_1s"] if c.get("moving_ball_1s", False) else feat["ball_speed"]
    moving = np.where(np.isnan(bs), 0.0, np.clip((bs - c["moving_ball"]) / 3.0, 0.0, 2.0))
    out -= c["w_moving_ball"] * moving

    # A visible ball that stays put for ~1 s: placed for a restart. Works whether or not the
    # tracker keeps the ball during stoppages, unlike the long-missing cue (v0.6: on, 0.5).
    w = c.get("w_ball_still", 0.0)
    if w:
        b1 = feat["ball_speed_1s"]
        still = np.where(np.isnan(b1), 0.0,
                         np.clip((c["ball_still_speed"] - b1) / c["ball_still_speed"], 0.0, 1.0))
        out += w * still

    # Restart geometry: a slow ball on a touchline, in a corner, in the goal area or on the
    # centre spot is about to be put back into play. Stacks on the ball-still cue: a still ball
    # anywhere is a hint, a still ball where restarts happen is a stronger one. Off by default.
    w = c.get("w_restart", 0.0)
    if w:
        b1 = feat["ball_speed_1s"]
        s = c.get("restart_still_speed", 1.5)
        tol = c.get("restart_tol_m", 2.0)
        still = np.where(np.isnan(b1), 0.0, np.clip((s - b1) / s, 0.0, 1.0))
        d = restart_distance(feat["bx"], feat["by"], feat["pitch"])
        near = np.where(np.isnan(d), 0.0, np.clip((tol - d) / tol, 0.0, 1.0))
        out += w * still * near
    return out
