"""Build the team's dev set from Metrica's PUBLIC sample game 3 -- a different match.

Why this exists: the rules forbid training or tuning on the competition match (including its
public 5 minutes), so every parameter has to be chosen on other games. Metrica publishes a full
match in the same EPTS format, with hand-annotated event data, under
github.com/metrica-sports/sample-data. Human labels on *other* games are explicitly allowed.

Two products, both written under devdata/ (gitignored):

  1. Ground truth per frame (H/A/D/X) derived mechanically from the events -- see gt_from_events.
  2. Degraded copies of the clean tracking that mimic the competition ATD: the ball removed on
     ~41% of played frames (in bursts, preferentially in crowds and in flight), players dropped
     and jittered. Several seeds, so a parameter has to win on all of them, not on one.

    python devset/build.py            # downloads if needed, ~1-2 min
"""

import json
import os
import sys
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from possession import io  # noqa: E402

RAW = os.path.join(ROOT, "devdata", "raw")
OUT = os.path.join(ROOT, "devdata")
BASE = "https://raw.githubusercontent.com/metrica-sports/sample-data/master/data/Sample_Game_3/"
FILES = ("Sample_Game_3_metadata.xml", "Sample_Game_3_tracking.txt", "Sample_Game_3_events.json")

# Restart-type events: the ball is dead from the stoppage until one of these starts.
# A goal kick is annotated as a PASS with subtype GOAL KICK, so any PASS also ends a stoppage.
STOPPAGE_TYPES = {"BALL OUT", "FAULT RECEIVED"}
CONTROL_TYPES = {"PASS", "CARRY", "RECOVERY", "SET PIECE", "SHOT"}

DEGRADE_SEEDS = (0, 1, 2)
TARGET_BALL_MISSING = 0.41


def download():
    os.makedirs(RAW, exist_ok=True)
    for name in FILES:
        path = os.path.join(RAW, name)
        if not os.path.exists(path):
            print("downloading", name)
            urllib.request.urlretrieve(BASE + name, path)


def _subtypes(ev):
    s = ev.get("subtypes")
    if isinstance(s, dict):
        return {s.get("name")}
    if isinstance(s, list):
        return {x.get("name") for x in s}
    return set()


def gt_from_events(events, frame_id, home_team_id):
    """Mechanical H/A/D/X labels from event data.

    - X outside each period (first to last event of the period).
    - D from a stoppage event (ball out, foul, goal) to the start of the next restart event.
    - Otherwise the team of the most recent *controlling* event (pass, carry, recovery, set piece,
      shot). Challenges, ball losses and deflections do not change possession -- the same rule the
      challenge states in CHALLENGE.md.
    """
    T = len(frame_id)
    first = int(frame_id[0])

    def row(f):
        return min(max(int(f) - first, 0), T - 1)

    labels = np.full(T, "X", dtype="<U1")
    events = sorted(events, key=lambda e: (e["start"]["frame"], e["index"]))
    by_period = {}
    for ev in events:
        by_period.setdefault(ev["period"], []).append(ev)

    for period, evs in by_period.items():
        a = row(evs[0]["start"]["frame"])
        b = row(max(e["end"]["frame"] or e["start"]["frame"] for e in evs))
        team = None
        dead_from = None
        cursor = a
        for ev in evs:
            s = row(ev["start"]["frame"])
            etype = ev["type"]["name"]
            is_goal = etype == "SHOT" and "GOAL" in _subtypes(ev)
            # Fill [cursor, s) with the state that held before this event.
            if s > cursor:
                labels[cursor:s] = "D" if dead_from is not None or team is None else team
                cursor = s
            if etype in CONTROL_TYPES and ev.get("team"):
                if dead_from is not None and etype in ("SET PIECE", "PASS"):
                    dead_from = None
                if dead_from is None:
                    team = "H" if ev["team"]["id"] == home_team_id else "A"
            if etype in STOPPAGE_TYPES or is_goal:
                end = row(ev["end"]["frame"] or ev["start"]["frame"])
                if end > cursor:
                    labels[cursor:end] = "D" if team is None else team
                    cursor = end
                dead_from = end
        labels[cursor:b + 1] = "D" if dead_from is not None or team is None else team
    return labels


def degrade(trk, seed, played):
    """Make clean tracking look like the competition's automatic ATD."""
    rng = np.random.default_rng(seed)
    T, S = trk.px.shape
    px = trk.px + rng.normal(0, 0.15, trk.px.shape).astype(np.float32)
    py = trk.py + rng.normal(0, 0.15, trk.py.shape).astype(np.float32)
    bx = trk.bx + rng.normal(0, 0.3, T).astype(np.float32)
    by = trk.by + rng.normal(0, 0.3, T).astype(np.float32)

    # Player dropouts in bursts (~7% of slot-frames, mean burst 2 s).
    drop = _bursty_mask(rng, (T, S), p_on=0.07, mean_len=50)
    px[drop] = np.nan
    py[drop] = np.nan

    # Ball dropouts: hazard rises in crowds and when the ball is fast (in the air).
    d = np.sqrt((trk.px - trk.bx[:, None]) ** 2 + (trk.py - trk.by[:, None]) ** 2)
    crowd = np.nansum(d < 3.0, axis=1)
    speed = np.r_[0, np.sqrt(np.diff(trk.bx) ** 2 + np.diff(trk.by) ** 2) * 25]
    hazard = 1.0 + 0.6 * np.clip(crowd - 1, 0, 4) + 1.5 * (np.nan_to_num(speed) > 15)
    p_start = 0.019 * hazard  # calibrated so ~41% of played frames lose the ball
    mean_len = 30
    missing = np.zeros(T, bool)
    t = 0
    while t < T:
        if rng.random() < p_start[t]:
            n = int(rng.geometric(1.0 / mean_len))
            missing[t:t + n] = True
            t += n
        t += 1
    rate = missing[played].mean() if played.any() else 0
    print("    seed {}: ball missing on {:.1%} of played frames".format(seed, rate))
    bx[missing] = np.nan
    by[missing] = np.nan
    return io.Tracking(trk.frame_id, px, py, trk.team, bx, by, trk.pitch)


def _bursty_mask(rng, shape, p_on, mean_len):
    T, S = shape
    mask = np.zeros(shape, bool)
    starts = rng.random(shape) < p_on / mean_len
    for s in range(S):
        for t in np.flatnonzero(starts[:, s]):
            mask[t:t + int(rng.geometric(1.0 / mean_len)), s] = True
    return mask


def main():
    download()
    meta, raw, ev_path = (os.path.join(RAW, f) for f in FILES)
    trk = io.load(meta, raw, cache_dir=os.path.join(OUT, "cache"))
    with open(ev_path) as fh:
        events = json.load(fh)["data"]
    import xml.etree.ElementTree as ET
    root = io._strip_ns(ET.parse(meta).getroot())
    home_id = [t.get("id") for t in root.iter("Team")][0]

    gt = gt_from_events(events, trk.frame_id, home_id)
    graded = gt != "X"
    from possession.pipeline import scorer
    pm = scorer()
    stats = pm.possession_stats(pm.label_codes(list(gt)), pm.valid_runs(pm.label_codes(list(gt))))
    print("dev GT: {} graded frames, H {:.0%} A {:.0%} D {:.0%}, {} possessions, mean {:.1f}s".format(
        graded.sum(), (gt == "H").sum() / graded.sum(), (gt == "A").sum() / graded.sum(),
        (gt == "D").sum() / graded.sum(), stats["n_spells"], stats["mean_duration_s"]))

    np.savez_compressed(os.path.join(OUT, "game3_gt.npz"), labels=gt)
    np.savez_compressed(os.path.join(OUT, "game3_clean.npz"),
                        **{k: np.asarray(v) for k, v in trk._asdict().items()})
    for seed in DEGRADE_SEEDS:
        d = degrade(trk, seed, graded)
        np.savez_compressed(os.path.join(OUT, "game3_degraded_s{}.npz".format(seed)),
                            **{k: np.asarray(v) for k, v in d._asdict().items()})
    print("wrote", OUT)


if __name__ == "__main__":
    main()
