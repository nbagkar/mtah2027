"""Score a config on the dev set (public sample game 3, clean + degraded). THE decision tool.

    python scripts/score_dev.py                         # configs/default.json
    python scripts/score_dev.py --config configs/x.json
    python scripts/score_dev.py --set segment.cost_team_switch=60

The number that matters is `deg_mean` -- spellF1 averaged over the degraded seeds, which look like
the competition ATD. `clean` is reported so you can tell a modelling problem from a noise problem.
A change is worth keeping when deg_mean improves by more than the seed spread.
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
    gt_path = os.path.join(DEV, "game3_gt.npz")
    if not os.path.exists(gt_path):
        sys.exit("no dev set -- run: python devset/build.py")
    gt = np.load(gt_path)["labels"]
    games = [("clean", os.path.join(DEV, "game3_clean.npz"))]
    games += [(os.path.basename(p)[len("game3_"):-4], p)
              for p in sorted(glob.glob(os.path.join(DEV, "game3_degraded_s*.npz")))]
    return gt, games


def evaluate(cfg, verbose=True):
    gt, games = dev_games()
    blocks = pipeline.blocks_from_gt(gt)
    rows = {}
    for name, path in games:
        pred = pipeline.predict(load_npz(path), cfg, blocks)
        rows[name] = pipeline.score(gt, pred)
    deg = [r["spell_f1_mean"] for k, r in rows.items() if k != "clean"]
    summary = {"deg_mean": float(np.mean(deg)), "deg_spread": float(np.ptp(deg)),
               "clean": rows["clean"]["spell_f1_mean"],
               "deg_macro": float(np.mean([r["macro_f1"] for k, r in rows.items()
                                           if k != "clean"]))}
    if verbose:
        print("{:<14} {:>8} {:>8} {:>6} {:>6} {:>8} {:>8}".format(
            "dev game", "spellF1", "macroF1", "poss", "gt", "aliveF1", "teamAcc"))
        for name, r in rows.items():
            print("{:<14} {:>8.4f} {:>8.4f} {:>6} {:>6} {:>8.4f} {:>8.4f}".format(
                name, r["spell_f1_mean"], r["macro_f1"], r["n_pred_spells"], r["n_gt_spells"],
                r["alive_dead_f1"], r["team_acc_gt_alive"]))
        print("\ndeg_mean spellF1 {deg_mean:.4f}  (seed spread {deg_spread:.4f})   "
              "clean {clean:.4f}   deg macroF1 {deg_macro:.4f}".format(**summary))
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
