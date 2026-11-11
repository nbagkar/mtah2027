"""Which team has the ball, as a per-frame log-odds for HOME. Owner: possessor stream.

Positive = home, negative = away, 0 = no opinion (ball unseen, in flight, nobody close). The
segmenter turns this into possessions; this module only weighs evidence frame by frame.

Ideas not yet in v0:
  - team shape when the ball is missing: the team in possession spreads out and pushes up.
  - Smart Tagging phases (Build Up / Progression / ... carry a Team tag) as a soft prior.
  - pass detection: ball leaves player of team T and arrives at a player of team T.
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
    return c["w_margin"] * margin * near * slow
