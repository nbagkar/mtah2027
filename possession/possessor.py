"""Which team has the ball, as a per-frame log-odds for HOME. Owner: possessor stream.

Positive = home, negative = away, 0 = no opinion (ball unseen, in flight, nobody close). The
segmenter turns this into possessions; this module only weighs evidence frame by frame.

Ideas not yet in v0:
  - Smart Tagging phases (Build Up / Progression / ... carry a Team tag) as a soft prior.

Pass detection (ball leaves team T, arrives at team T) and sustained control are in, off by
default: `w_bridge`, `w_ctrl` (features.control_and_bridge).
"""

import numpy as np


def home_logodds(feat, cfg):
    c = cfg["possessor"]
    dh, da = feat["d_home"], feat["d_away"]
    have = ~np.isnan(dh) & ~np.isnan(da)
    nearest = np.fmin(dh, da)

    # Who is closer, in metres, saturated so one frame can't dominate.
    margin = np.where(have, np.clip(da - dh, -c["margin_cap_m"], c["margin_cap_m"]), 0.0)

    # Trust it only when someone is actually near the ball, and less when the ball is fast
    # (passes in flight pass close to opponents without changing possession).
    near = np.where(have, np.clip((c["control_radius_m"] - nearest) / c["control_radius_m"],
                                  0.0, 1.0), 0.0)
    bs = feat["ball_speed"]
    slow = np.where(np.isnan(bs), 0.5, np.clip(1.0 - bs / c["fast_ball"], 0.0, 1.0))
    out = c["w_margin"] * margin * near * slow

    # Carry: the nearest player is close AND moving with the ball -> that team controls it.
    # Off by default (w_carry 0) until the dev set says otherwise.
    w = c.get("w_carry", 0.0)
    if w:
        rel = feat["carry_rel_speed"]
        close = feat["nearest_d"] < c["carry_radius_m"]
        together = rel < c["carry_rel_speed"]
        sign = np.where(feat["nearest_team"] == 0, 1.0, -1.0)
        carrying = np.nan_to_num(close & together, nan=0.0).astype(float)
        out = out + w * sign * carrying

    # Sustained control: a team gets this only once it has been the controlling team (nearest,
    # within the control radius, ball slow) for ctrl_min_frames in a row, so a pass brushing
    # past an opponent doesn't count. Off by default (w_ctrl 0).
    wc = c.get("w_ctrl", 0.0)
    if wc:
        held = feat["ctrl_run"] >= c.get("ctrl_min_frames", 10)
        out = out + wc * feat["ctrl"] * held

    # Pass / gap bridge: the ball leaves team T and the next team to control it is T again,
    # within bridge_max_gap frames -> the frames in between are T's (a completed pass, or the
    # ball unseen while T kept it). Speaks where the ball is in flight or invisible, which is
    # where the wrong-team frames are. Off by default (w_bridge 0).
    wb = c.get("w_bridge", 0.0)
    if wb:
        b = feat["bridge"]
        # Optionally only where the ball is visibly moving over ~1 s (a pass in flight): a still
        # or unseen ball between two touches of one team may be a stoppage (foul, throw-in).
        if c.get("bridge_only_moving", False):
            with np.errstate(invalid="ignore"):
                b = b * (feat["ball_speed_1s"] > c.get("bridge_min_speed", 3.0))
        out = out + wb * b

    # Team shape: ball-free, so it also speaks while the ball is invisible (41% of frames).
    # Saturated with tanh so one wide moment can't outvote the ball. Off by default.
    # Width and movement are smooth and present on every frame, so even a modest weight adds
    # up over a possession and drowns the ball. With shape_only_ball_missing they speak only
    # where the ball (after gap filling) is unknown.
    gate = (feat["ball_ok"] == 0) if c.get("shape_only_ball_missing", True) else 1.0
    ww = c.get("w_width", 0.0)
    if ww:
        out = out + gate * ww * np.tanh(np.nan_to_num(feat["width_diff"]) / c["width_scale_m"])
    wm = c.get("w_move", 0.0)
    if wm:
        out = out + gate * wm * np.tanh(np.nan_to_num(feat["move"]) / c["move_scale"])
    return out
