"""Alive vs dead evidence, as a per-frame log-odds that the ball is DEAD. Owner: dead-ball stream.

Positive = dead, negative = alive, 0 = no opinion. The segmenter combines this with the
possessor's evidence; nothing here makes a final decision.

Ideas not yet in v0 (each is a self-contained PR):
  - Smart Tagging SET PIECES: the frames just before a restart are dead.
  - restart geometry: ball stationary on a line / corner arc / centre spot, players static.
  - kickoff detection: both teams in their own halves, ball on the centre spot.
"""

import numpy as np


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

    # A moving ball is alive.
    bs = feat["ball_speed"]
    moving = np.where(np.isnan(bs), 0.0, np.clip((bs - c["moving_ball"]) / 3.0, 0.0, 2.0))
    out -= c["w_moving_ball"] * moving
    return out
