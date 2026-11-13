"""Score a config on the dev set (public sample game 3, clean + degraded). THE decision tool.

    python scripts/score_dev.py                         # configs/default.json
    python scripts/score_dev.py --config configs/x.json
    python scripts/score_dev.py --set segment.cost_team_switch=60

The number that matters is `robust` (from 2026-11-12; before that, `deg_mean`): spellF1 on the degraded copies (which look like the
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
                     for kind in ("degraded", "stopball")
                     for p in sorted(glob.glob(os.path.join(DEV, game + "_" + kind + "_s*.npz")))]
        out.append((game, gt, pipeline.blocks_from_gt(gt), variants))
    return out


def summarise(per):
    """per: {(game, variant): spellF1}.

    deg   -- degraded copies (ball missing in stoppages, as in Metrica's data)
    stop  -- stopball copies (ball kept visible through stoppages)
    robust = per game, the mean of deg and stop; THE number decisions are made on, because we
             don't know which convention the real tracking follows. A change is real when robust
             improves in EVERY game.
    """
    games = sorted({g for g, _ in per})

    def by_game(prefix):
        out = {}
        for g in games:
            vals = [v for (gg, var), v in per.items() if gg == g and var.startswith(prefix)]
            if vals:
                out[g] = float(np.mean(vals))
        return out

    deg, stop = by_game("degraded"), by_game("stopball")
    robust = {g: (deg[g] + stop[g]) / 2 if g in stop else deg[g] for g in deg}
    clean_by_game = {g: per[(g, "clean")] for g in games if (g, "clean") in per}
    mean = lambda d: float(np.mean(list(d.values()))) if d else float("nan")  # noqa: E731
    return {"robust": mean(robust), "deg_mean": mean(deg), "stop_mean": mean(stop),
            "clean": mean(clean_by_game), "robust_by_game": robust, "deg_by_game": deg,
            "stop_by_game": stop, "clean_by_game": clean_by_game}


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
        print("\nrobust spellF1 {:.4f}   per game: {}".format(
            summary["robust"],
            "  ".join("{} {:.4f}".format(g, v) for g, v in summary["robust_by_game"].items())))
        print("deg_mean spellF1 {:.4f}   stop_mean {:.4f}   clean {:.4f}   per game (deg): {}".format(
            summary["deg_mean"], summary["stop_mean"], summary["clean"],
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
