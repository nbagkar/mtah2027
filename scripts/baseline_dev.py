"""The official reference baseline (nearest player + majority vote), run on the dev set.

Our anchor: the competition floor is this algorithm with window 50 (spellF1 0.2433 on the real
match). Whatever beats it here by a clear margin is a candidate to beat it there.
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import pipeline  # noqa: E402
from scripts.score_dev import dev_games, load_npz  # noqa: E402


def baseline_labels(trk, window, blocks):
    d = np.sqrt((trk.px - trk.bx[:, None]) ** 2 + (trk.py - trk.by[:, None]) ** 2)
    d = np.where(np.isnan(d), np.inf, d)
    nearest = np.argmin(d, axis=1)
    team = trk.team[np.arange(len(nearest)), nearest]
    codes = np.where(np.isnan(trk.bx), -1, team)
    h = np.concatenate(([0], np.cumsum(codes == 0)))
    a = np.concatenate(([0], np.cumsum(codes == 1)))
    i = np.arange(len(codes))
    lo, hi = np.maximum(0, i - window), np.minimum(len(codes), i + window + 1)
    nh, na = h[hi] - h[lo], a[hi] - a[lo]
    # Exactly the official rule: D only where nobody was seen in the whole window.
    lab = np.where(nh + na == 0, "D", np.where(nh >= na, "H", "A")) if window else \
        np.where(codes == 0, "H", np.where(codes == 1, "A", "D"))
    out = np.full(len(codes), "X", "<U1")
    for s, e in blocks:
        out[s:e] = lab[s:e]
    return out


if __name__ == "__main__":
    gt, games = dev_games()
    blocks = pipeline.blocks_from_gt(gt)
    for w in (0, 25, 50, 125):
        res = [pipeline.score(gt, baseline_labels(load_npz(p), w, blocks)) for _, p in games]
        print("smooth{:<4} clean {:.4f}  deg_mean {:.4f}  poss(deg) {}".format(
            w, res[0]["spell_f1_mean"], np.mean([r["spell_f1_mean"] for r in res[1:]]),
            [r["n_pred_spells"] for r in res[1:]]))
