"""Build the team's dev set from Metrica's PUBLIC sample games 1, 2 and 3 -- different matches.

Why this exists: the rules forbid training or tuning on the competition match (including its
public 5 minutes), so every parameter has to be chosen on other games. Metrica publishes three
full matches with hand-annotated event data under github.com/metrica-sports/sample-data: game 3
in the same EPTS format as the competition ATD, games 1-2 as home/away CSVs. Human labels on
*other* games are explicitly allowed.

Two products, both written under devdata/ (gitignored):

  1. Ground truth per frame (H/A/D/X) derived mechanically from the events -- see gt_from_events.
  2. Degraded copies of the clean tracking that mimic the competition ATD: the ball removed on
     ~41% of played frames (in bursts, preferentially in crowds and in flight), players dropped
     and jittered. Several seeds, so a parameter has to win on all of them, not on one.
  3. "stopball" copies: the same, but with the ball kept visible through every stoppage. Metrica's
     public tracking drops the ball for 82-99% of dead-ball frames, so the degraded copies teach
     "ball gone a while = stoppage". An automatic tracker may keep seeing the ball at throw-ins
     and free kicks; these copies are the other extreme, and a setting has to hold up on both.

    python devset/build.py            # downloads if needed, ~1-2 min
"""

import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from possession import io  # noqa: E402

RAW = os.path.join(ROOT, "devdata", "raw")
OUT = os.path.join(ROOT, "devdata")
# Pinned to an upstream commit, and every file checked against its sha256, so the dev scores
# can't drift if Metrica's repo changes.
BASE = ("https://raw.githubusercontent.com/metrica-sports/sample-data/"
        "e706dd506b360d69d9d123d5b8026e7294b13996/data/")
SHA256 = {
    "Sample_Game_1_RawEventsData.csv": "097dda6345e17390dca095331458fd00e47960c480c76f4356fd4edf2575ef05",
    "Sample_Game_1_RawTrackingData_Away_Team.csv": "0a3df68a92af0290ede472e62de3b6489ddee29223da09bdf0cf76c8e0ab0618",
    "Sample_Game_1_RawTrackingData_Home_Team.csv": "0a3d0eff7785950379c587d3597b86a2d91c2492281b4652e1abb97c99b6b364",
    "Sample_Game_2_RawEventsData.csv": "edf31a18599265b77a8baf150f2ce6d89456fb0324b62ea7a391229657a619ba",
    "Sample_Game_2_RawTrackingData_Away_Team.csv": "aa639f40762eade46c389020fe4458266b5ba14027b1e96e22e75db62803718b",
    "Sample_Game_2_RawTrackingData_Home_Team.csv": "3f9990ac204b07133e4202441d6fcbb386897c7c7f81e1bc3ce4d35bc8644694",
    "Sample_Game_3_events.json": "28a53bfe9eaf32535362335553d517cdce0eabb588af6166009081753751f4e0",
    "Sample_Game_3_metadata.xml": "009c7dcfcb66192014917ca1559c158f612353e390eafb85f8214b06a1c7dec1",
    "Sample_Game_3_tracking.txt": "570e6ce82c2d93bc92723af331d93c31110bec1d6dc0be07c6d44ca3f981d658",
}
FILES = {
    1: ("Sample_Game_1_RawEventsData.csv", "Sample_Game_1_RawTrackingData_Home_Team.csv",
        "Sample_Game_1_RawTrackingData_Away_Team.csv"),
    2: ("Sample_Game_2_RawEventsData.csv", "Sample_Game_2_RawTrackingData_Home_Team.csv",
        "Sample_Game_2_RawTrackingData_Away_Team.csv"),
    3: ("Sample_Game_3_metadata.xml", "Sample_Game_3_tracking.txt", "Sample_Game_3_events.json"),
}
METRICA_PITCH = (105.0, 68.0)  # the sample games' metadata pitch; games 1-2 ship no metadata

# Restart-type events: the ball is dead from the stoppage until one of these starts.
# A goal kick is annotated as a PASS with subtype GOAL KICK, so any PASS also ends a stoppage.
STOPPAGE_TYPES = {"BALL OUT", "FAULT RECEIVED"}
CONTROL_TYPES = {"PASS", "CARRY", "RECOVERY", "SET PIECE", "SHOT"}

STOPBALL_SEEDS = (0, 1, 2)
DEGRADE_SEEDS = tuple(range(6))  # 3 -> 6 on 2026-11-12: one game spread 0.05 across 3 seeds
TARGET_BALL_MISSING = 0.41


def download():
    os.makedirs(RAW, exist_ok=True)
    for game, names in FILES.items():
        for name in names:
            path = os.path.join(RAW, name)
            if not os.path.exists(path):
                print("downloading", name)
                _fetch("{}Sample_Game_{}/{}".format(BASE, game, name), path)
            with open(path, "rb") as fh:
                got = hashlib.sha256(fh.read()).hexdigest()
            if got != SHA256[name]:
                sys.exit("{} has sha256 {}, expected {}; delete it and rerun".format(path, got, SHA256[name]))


def _fetch(url, path):
    tmp = path + ".part"  # a failed download never leaves a truncated file behind
    try:
        urllib.request.urlretrieve(url, tmp)
    except urllib.error.URLError:
        # python.org's macOS Python ships without root certificates; the system curl has them
        subprocess.run(["curl", "-fsSL", "-o", tmp, url], check=True)
    os.replace(tmp, path)


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
            # A shot that scores or goes out stops play. Games 1-2 write this into the subtype
            # ("ON TARGET-GOAL", "OFF TARGET-OUT"); game 3 uses separate events, so this is
            # unchanged there.
            tokens = {t for sub in _subtypes(ev) if sub for t in sub.split("-")}
            is_goal = etype == "SHOT" and bool(tokens & {"GOAL", "OUT"})
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


def ball_through_stoppages(trk, gt):
    """Keep the ball visible through each dead-ball stretch: where the clean tracking loses it,
    walk it in a straight line from where it was last seen to where it reappears (the restart
    spot). A crude stand-in for a tracker that follows the ball while play is stopped."""
    bx, by = trk.bx.copy(), trk.by.copy()
    dead = gt == "D"
    edges = np.diff(np.concatenate(([0], dead.astype(np.int8), [0])))
    for s, e in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        nan_in = s + np.flatnonzero(np.isnan(trk.bx[s:e]))
        if not len(nan_in):
            continue
        first = nan_in[0]
        before = np.flatnonzero(~np.isnan(trk.bx[:first]))
        after = first + np.flatnonzero(~np.isnan(trk.bx[first:]))
        if not len(before) or not len(after):
            continue
        i0, i1 = before[-1], after[0]
        idx = np.arange(first, min(e, i1))
        frac = (idx - i0) / max(1, i1 - i0)
        fill = np.isnan(bx[idx])
        bx[idx[fill]] = (trk.bx[i0] + frac * (trk.bx[i1] - trk.bx[i0]))[fill]
        by[idx[fill]] = (trk.by[i0] + frac * (trk.by[i1] - trk.by[i0]))[fill]
    return io.Tracking(trk.frame_id, trk.px, trk.py, trk.team, bx, by, trk.pitch)


def _bursty_mask(rng, shape, p_on, mean_len):
    T, S = shape
    mask = np.zeros(shape, bool)
    starts = rng.random(shape) < p_on / mean_len
    for s in range(S):
        for t in np.flatnonzero(starts[:, s]):
            mask[t:t + int(rng.geometric(1.0 / mean_len)), s] = True
    return mask


def read_csv_tracking(home_path, away_path, pitch=METRICA_PITCH):
    """Metrica sample games 1-2: one CSV per team, 3 header rows, x,y per player, ball last."""
    def load(path):
        with open(path) as fh:
            for _ in range(3):
                fh.readline()
            arr = np.loadtxt(fh, delimiter=",", dtype=np.float64)
        return arr
    home, away = load(home_path), load(away_path)
    if not np.array_equal(home[:, 1], away[:, 1]):
        raise ValueError("home and away frames differ")
    frame_id = home[:, 1].astype(np.int64)
    hxy, axy = home[:, 3:-2], away[:, 3:-2]
    L, W = pitch
    px = np.hstack([hxy[:, 0::2], axy[:, 0::2]]) * L
    py = np.hstack([hxy[:, 1::2], axy[:, 1::2]]) * W
    team = np.hstack([np.zeros(hxy.shape[1] // 2, np.int8), np.ones(axy.shape[1] // 2, np.int8)])
    team = np.tile(team, (len(frame_id), 1))
    team[np.isnan(px)] = -1  # substitutes not yet (or no longer) on the pitch
    bx, by = home[:, -2] * L, home[:, -1] * W
    return io.Tracking(frame_id, px.astype(np.float32), py.astype(np.float32), team,
                       bx.astype(np.float32), by.astype(np.float32), pitch)


def csv_events(path):
    """Games 1-2 event CSV -> the game-3 JSON event shape gt_from_events reads."""
    import csv
    out = []
    with open(path) as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            out.append({
                "index": i,
                "team": {"id": r["Team"]} if r["Team"] else None,
                "type": {"name": r["Type"]},
                "subtypes": {"name": r["Subtype"]} if r["Subtype"] else None,
                "period": int(r["Period"]),
                "start": {"frame": int(r["Start Frame"])},
                "end": {"frame": int(r["End Frame"]) if r["End Frame"] else None},
            })
    return out


def load_game(game):
    paths = [os.path.join(RAW, f) for f in FILES[game]]
    if game == 3:
        meta, raw, ev_path = paths
        trk = io.load(meta, raw, cache_dir=os.path.join(OUT, "cache"))
        with open(ev_path) as fh:
            events = json.load(fh)["data"]
        import xml.etree.ElementTree as ET
        root = io._strip_ns(ET.parse(meta).getroot())
        home_id = [t.get("id") for t in root.iter("Team")][0]
    else:
        ev_path, home_path, away_path = paths
        trk = read_csv_tracking(home_path, away_path)
        events = csv_events(ev_path)
        home_id = "Home"
    return trk, events, home_id


def save(path, trk):
    np.savez_compressed(path, **{k: np.asarray(v) for k, v in trk._asdict().items()})


def main():
    download()
    from possession.pipeline import scorer
    pm = scorer()
    for game in sorted(FILES):
        trk, events, home_id = load_game(game)
        gt = gt_from_events(events, trk.frame_id, home_id)
        graded = gt != "X"
        codes = pm.label_codes(list(gt))
        stats = pm.possession_stats(codes, pm.valid_runs(codes))
        print("game {}: {} graded frames, H {:.0%} A {:.0%} D {:.0%}, {} possessions, "
              "mean {:.1f}s".format(game, graded.sum(), (gt == "H").sum() / graded.sum(),
                                   (gt == "A").sum() / graded.sum(),
                                   (gt == "D").sum() / graded.sum(), stats["n_spells"],
                                   stats["mean_duration_s"]))
        stem = os.path.join(OUT, "game{}".format(game))
        np.savez_compressed(stem + "_gt.npz", labels=gt)
        save(stem + "_clean.npz", trk)
        for seed in DEGRADE_SEEDS:
            # Seeds differ per game so no two games share a dropout pattern.
            save(stem + "_degraded_s{}.npz".format(seed), degrade(trk, 100 * game + seed, graded)
                 if game != 3 else degrade(trk, seed, graded))
        visible = ball_through_stoppages(trk, gt)
        for seed in STOPBALL_SEEDS:
            save(stem + "_stopball_s{}.npz".format(seed),
                 degrade(visible, 1000 * game + 50 + seed, graded))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
