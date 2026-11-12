"""Grid-search parameters on the dev set (other games only -- never the competition match).

    python scripts/sweep.py                       # the GRID below
    python scripts/sweep.py --grid grid.json      # {"dotted.key": [values], ...}

`segment.*` keys only change the decoder, so the per-frame evidence is computed once per setting
of every other key and reused across them; that keeps a large segmenter grid cheap.

Prints the top settings by deg_mean spellF1, with the per-game degraded scores in brackets.
Adopt a winner only if it beats the current config in EVERY game and doesn't hurt `clean` --
then log it in experiments/LOG.md.
"""
import argparse
import itertools
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import pipeline, segment  # noqa: E402
from scripts.score_dev import dev_games, load_npz, summarise  # noqa: E402

GRID = {
    "segment.cost_team_switch": [5, 10, 20],
    "segment.cost_to_dead": [4, 10],
    "segment.cost_from_dead": [4],
}


def product(grid):
    keys = list(grid)
    for values in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, values))


def run(grid, top=12):
    base = pipeline.load_config()
    games = dev_games()
    tracks = {(g, name): load_npz(path) for g, _, _, variants in games for name, path in variants}
    meta = {g: (gt, blocks) for g, gt, blocks, _ in games}
    evid_grid = {k: v for k, v in grid.items() if not k.startswith("segment.")}
    seg_grid = {k: v for k, v in grid.items() if k.startswith("segment.")}
    results = []
    for evid in product(evid_grid):
        cfg_e = pipeline.with_overrides(base, evid)
        parts = {key: pipeline.predict(trk, cfg_e, meta[key[0]][1], return_parts=True)[1]
                 for key, trk in tracks.items()}
        for seg in product(seg_grid):
            cfg = pipeline.with_overrides(cfg_e, seg)
            per = {}
            for key, p in parts.items():
                gt, blocks = meta[key[0]]
                lab = segment.decode(p["home_logodds"], p["dead_logodds"], cfg, blocks)
                per[key] = pipeline.score(gt, lab)["spell_f1_mean"]
            results.append((summarise(per), {**evid, **seg}))
    results.sort(key=lambda r: -r[0]["deg_mean"])
    for summ, setting in results[:top]:
        print("deg {:.4f} clean {:.4f} [{}]  {}".format(
            summ["deg_mean"], summ["clean"],
            " ".join("{:.3f}".format(v) for v in summ["deg_by_game"].values()),
            json.dumps(setting)), flush=True)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", help="JSON file: {dotted.key: [values]}")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    grid = GRID
    if args.grid:
        with open(args.grid) as fh:
            grid = json.load(fh)
    run(grid, args.top)


if __name__ == "__main__":
    main()
