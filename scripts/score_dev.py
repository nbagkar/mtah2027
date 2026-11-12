"""Score a config on the dev set (public sample game 3, clean + degraded). THE decision tool.

    python scripts/score_dev.py                         # configs/default.json
    python scripts/score_dev.py --config configs/x.json
    python scripts/score_dev.py --set segment.cost_team_switch=60

The number that matters is `deg_mean`: spellF1 on the degraded copies (which look like the
competition ATD), averaged over seeds and then over the three public sample games. `clean` is
reported so you can tell a modelling problem from a noise problem. A change is worth keeping
when deg_mean improves in EVERY game, not just on average.
"""

import argparse
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import io, pipeline  # noqa: E402

DEV = os.path.join(ROOT, "devdata")


def load_npz(path):
    z = np.load(path)
    return io.Tracking(z["frame_id"], z["px"], z["py"], z["team"], z["bx"], z["by"],
                       tuple(z["pitch"]))


def dev_games():
    """[(game, gt_labels, blocks, [(variant, npz_path)])] for every game devset/build.py wrote."""
    gts = sorted(glob.glob(os.path.join(DEV, "game*_gt.npz")))
    if not gts:
        sys.exit("no dev set -- run: python devset/build.py")
    out = []
    for gt_path in gts:
        game = os.path.basename(gt_path)[:-len("_gt.npz")]
        gt = np.load(gt_path)["labels"]
        variants = [("clean", os.path.join(DEV, game + "_clean.npz"))]
        variants += [(os.path.basename(p)[len(game) + 1:-4], p)
                     for p in sorted(glob.glob(os.path.join(DEV, game + "_degraded_s*.npz")))]
        out.append((game, gt, pipeline.blocks_from_gt(gt), variants))
    return out


def summarise(per):
    """per: {(game, variant): spellF1}. A change is real when deg improves in EVERY game."""
    games = sorted({g for g, _ in per})
    deg_by_game = {g: float(np.mean([v for (gg, var), v in per.items()
                                     if gg == g and var != "clean"])) for g in games}
    clean_by_game = {g: per[(g, "clean")] for g in games}
    return {"deg_mean": float(np.mean(list(deg_by_game.values()))),
            "clean": float(np.mean(list(clean_by_game.values()))),
            "deg_by_game": deg_by_game, "clean_by_game": clean_by_game}


def evaluate(cfg, verbose=True):
    rows = {}
    for game, gt, blocks, variants in dev_games():
        for name, path in variants:
            rows[(game, name)] = pipeline.score(gt, pipeline.predict(load_npz(path), cfg, blocks))
    summary = summarise({k: r["spell_f1_mean"] for k, r in rows.items()})
    if verbose:
        print("{:<7} {:<14} {:>8} {:>8} {:>6} {:>6} {:>8} {:>8}".format(
            "game", "variant", "spellF1", "macroF1", "poss", "gt", "aliveF1", "teamAcc"))
        for (game, name), r in rows.items():
            print("{:<7} {:<14} {:>8.4f} {:>8.4f} {:>6} {:>6} {:>8.4f} {:>8.4f}".format(
                game, name, r["spell_f1_mean"], r["macro_f1"], r["n_pred_spells"],
                r["n_gt_spells"], r["alive_dead_f1"], r["team_acc_gt_alive"]))
        print("\ndeg_mean spellF1 {:.4f}   clean {:.4f}   per game (deg): {}".format(
            summary["deg_mean"], summary["clean"],
            "  ".join("{} {:.4f}".format(g, v) for g, v in summary["deg_by_game"].items())))
    return summary, rows


def parse_sets(items):
    out = {}
    for item in items or []:
        k, v = item.split("=", 1)
        out[k] = json.loads(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--set", action="append", help="dotted.key=value override")
    args = ap.parse_args()
    cfg = pipeline.load_config(args.config, parse_sets(args.set))
    evaluate(cfg)


if __name__ == "__main__":
    main()
