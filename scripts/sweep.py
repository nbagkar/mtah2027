"""Grid-search segmenter penalties on the dev set, reusing the per-frame evidence.

    python scripts/sweep.py
Prints the top settings by deg_mean spellF1. Copy a winner into a config only if it also holds
up on `clean` and the gain exceeds the seed spread -- then log it in experiments/LOG.md.
"""
import itertools
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import pipeline, segment  # noqa: E402
from scripts.score_dev import dev_games, load_npz  # noqa: E402

GRID = {
    "segment.cost_team_switch": [2, 5, 10],
    "segment.cost_to_dead": [4, 10],
    "segment.cost_from_dead": [4, 10],
    "possessor.w_margin": [1.2, 2.5],
}


def main():
    cfg = pipeline.load_config()
    gt, games = dev_games()
    blocks = pipeline.blocks_from_gt(gt)
    parts = {}
    for name, path in games:
        _, p = pipeline.predict(load_npz(path), cfg, blocks, return_parts=True)
        parts[name] = p
    keys = list(GRID)
    results = []
    for values in itertools.product(*(GRID[k] for k in keys)):
        c = pipeline.with_overrides(cfg, dict(zip(keys, values)))
        scale = c["possessor"]["w_margin"] / cfg["possessor"]["w_margin"]
        sc = {}
        for name, p in parts.items():
            lab = segment.decode(p["home_logodds"] * scale, p["dead_logodds"], c, blocks)
            sc[name] = pipeline.score(gt, lab)["spell_f1_mean"]
        deg = [v for k, v in sc.items() if k != "clean"]
        results.append((float(np.mean(deg)), float(np.ptp(deg)), sc["clean"], values))
    results.sort(reverse=True)
    print("  ".join(keys))
    for deg, spread, clean, values in results[:12]:
        print("deg {:.4f} (+-{:.3f}) clean {:.4f}  {}".format(deg, spread, clean, values))


if __name__ == "__main__":
    main()
