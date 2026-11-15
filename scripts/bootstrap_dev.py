"""Bootstrap intervals on the dev score. Owner: role 5 (validation).

    python scripts/bootstrap_dev.py                      # configs/default.json, 1000 draws
    python scripts/bootstrap_dev.py --draws 2000 --config configs/x.json

`score_dev.py` gives one number per game. This script says how much that number could move by
chance, which is what the technical document reports next to it.

Method: the official one. `possession_metrics.bootstrap_spell_f1` (in the pinned challenge repo)
resamples a game's ground-truth possessions with replacement, because spellF1 scores each
possession as one hit-or-miss, so the possessions are the sample size. We do the same, with one
addition: in a draw, every copy of a game (clean, 6 degraded seeds, 3 stopball seeds) uses the
SAME resampled possessions, so `robust` is resampled as one number, exactly as score_dev.py builds
it (per game: mean of the degraded mean and the stopball mean; then the mean over games).

Two sources of noise are reported separately:
  * possessions -- the bootstrap above: "a different 90 minutes of the same kind of football".
                   This is the one that matters for the real match.
  * seeds       -- the spread between the random degraded/stopball copies of one game (standard
                   error of the seed mean). This is our own simulation noise.

Runs on the dev set only (Metrica's public games). It never reads competition data.
Intervals are 5th-95th percentile (a 90% interval), the convention of the official scorer.
"""

import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import pipeline  # noqa: E402
from scripts.score_dev import dev_games, load_npz, parse_sets  # noqa: E402

SEED = 0  # fixed, so the intervals in the technical document regenerate exactly


def match_flags(pm, gt_codes, pred_codes):
    """(per-IoU matched flags for each GT possession, n_pred) -- as bootstrap_spell_f1 does it."""
    runs = pm.valid_runs(gt_codes)
    filled = pm.fill_abstentions(pred_codes, runs)
    gt_spells = pm.possession_spells(gt_codes, runs)
    pred_spells = pm.possession_spells(filled, runs)
    overlaps = pm.spell_overlaps(gt_spells, pred_spells)
    n_gt = len(gt_spells)
    flags = np.vstack([pm.matched_gt_flags(overlaps, n_gt, t) for t in pm.SPELL_IOUS])
    return flags, len(pred_spells)


def spell_f1_from_draw(flags, n_pred, picks):
    """spell_f1_mean for one resample `picks` of GT possessions; same formula as the official."""
    n_gt = len(picks)
    f1s = []
    for row in flags:
        tp = int(row[picks].sum())
        fn = n_gt - tp
        fp = max(0, n_pred - tp)
        f1s.append(2.0 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return float(np.mean(f1s))


def robust_of(variant_scores):
    """{variant: score} for one game -> (robust, deg_mean, stop_mean, clean)."""
    deg = [v for k, v in variant_scores.items() if k.startswith("degraded")]
    stop = [v for k, v in variant_scores.items() if k.startswith("stopball")]
    d, s = float(np.mean(deg)), (float(np.mean(stop)) if stop else None)
    robust = (d + s) / 2 if s is not None else d
    return robust, d, s, variant_scores.get("clean")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--set", action="append", help="dotted.key=value override")
    ap.add_argument("--draws", type=int, default=1000)
    args = ap.parse_args()
    cfg = pipeline.load_config(args.config, parse_sets(args.set))
    pm = pipeline.scorer()

    games = []  # (game, n_gt, {variant: (flags, n_pred)}, {variant: point score})
    for game, gt, blocks, variants in dev_games():
        gt_codes = pm.label_codes(list(gt))
        per = {}
        point = {}
        for name, path in variants:
            pred = pipeline.predict(load_npz(path), cfg, blocks)
            pred_codes = pm.label_codes(list(pred))
            per[name] = match_flags(pm, gt_codes, pred_codes)
            # the point estimate is the official number, so it matches score_dev.py exactly
            point[name] = pipeline.score(gt, pred)["spell_f1_mean"]
        n_gt = per[next(iter(per))][0].shape[1]
        games.append((game, n_gt, per, point))
        print("scored {} ({} possessions, {} copies)".format(game, n_gt, len(per)), flush=True)

    rng = np.random.RandomState(SEED)
    keys = ("robust", "degraded", "stopball", "clean")
    draws = {g: {k: np.empty(args.draws) for k in keys} for g, *_ in games}
    overall = {k: np.empty(args.draws) for k in keys}
    for i in range(args.draws):
        for game, n_gt, per, _ in games:
            picks = rng.randint(0, n_gt, n_gt)  # one resample, shared by every copy of the game
            scores = {name: spell_f1_from_draw(f, n_pred, picks) for name, (f, n_pred) in per.items()}
            for k, v in zip(keys, robust_of(scores)):
                draws[game][k][i] = np.nan if v is None else v
        for k in keys:
            overall[k][i] = np.mean([draws[g][k][i] for g, *_ in games])

    def interval(a):
        lo, hi = np.nanpercentile(a, pm.BOOTSTRAP_PERCENTILES)
        return lo, hi

    print("\n90% bootstrap intervals over ground-truth possessions ({} draws, seed {})".format(
        args.draws, SEED))
    print("{:<8} {:<9} {:>7}   {:<17} {:>10}".format("game", "score", "point", "90% interval",
                                                     "seed s.e."))
    for game, n_gt, per, point in games:
        pt = dict(zip(keys, robust_of(point)))
        for k in keys:
            if pt[k] is None:
                continue
            lo, hi = interval(draws[game][k])
            prefix = {"robust": None, "degraded": "degraded", "stopball": "stopball",
                      "clean": None}[k]
            vals = [v for n, v in point.items() if prefix and n.startswith(prefix)]
            se = "{:.4f}".format(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else ""
            print("{:<8} {:<9} {:>7.4f}   [{:.4f}, {:.4f}] {:>10}".format(
                game, k, pt[k], lo, hi, se))
    print()
    for k in keys:
        pts = [dict(zip(keys, robust_of(p)))[k] for *_, p in games]
        if any(p is None for p in pts):
            continue
        lo, hi = interval(overall[k])
        print("{:<8} {:<9} {:>7.4f}   [{:.4f}, {:.4f}]".format("mean", k, float(np.mean(pts)), lo, hi))
    print("\nofficial baseline floor on the real match: 0.2433")


if __name__ == "__main__":
    main()
