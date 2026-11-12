"""Competition data -> submissions/<team>.csv. The ONE command the organisers will re-run.

    export MTAH_DATA_DIR=/path/to/unpacked/bundle     # or unpack into ./data
    python scripts/make_submission.py --team <TeamName>

Deterministic: same data + same config + same pinned deps -> byte-identical file. It prints the
file's sha256; record it in experiments/LOG.md next to the commit that produced it.

--sanity-public scores the file against the public 5 minutes, purely as an automatic alignment
check (an off-by-one or swapped H/A shows up as a near-zero score). The organisers' 2026-11-11
clarification bans fitting, calibrating or tuning on that ground truth. Never change a
parameter, rule or threshold because of this number. Decisions come from scripts/score_dev.py.
"""

import argparse
import hashlib
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("MTAH_DATA_DIR", os.path.join(ROOT, "data"))
sys.path.insert(0, os.path.join(ROOT, "vendor", "mtah"))
import games  # noqa: E402  (the organisers' own constants and paths)
from possession import io, pipeline  # noqa: E402

N_FRAMES = games.GAMES[games.GAME]["n_video_frames"]

# From the challenge's DATA.md: "Home is Barcelona (H), away is Athletic (A)." The Smart Tagging
# spells the away club "Atletic", so both spellings are accepted.
EXPECTED_HOME = "Barcelona"
EXPECTED_AWAY = ("Athletic", "Atletic")


def build_labels(cfg):
    meta, raw = games.require(["atd_meta", "atd_raw"])
    io.check_home_team(meta, EXPECTED_HOME, EXPECTED_AWAY)
    print("home/away check OK: the tracking's first team is the home side, so H = Barcelona")
    trk = io.load(meta, raw, cache_dir=os.path.join(ROOT, "data", "cache"),
                  pitch=tuple(games.GAMES[games.GAME]["pitch"]))
    if len(trk.frame_id) != N_FRAMES or trk.frame_id[0] != 1:
        raise SystemExit("ATD has {} records starting at {}; expected {} from 1".format(
            len(trk.frame_id), trk.frame_id[0], N_FRAMES))
    # Row i of the tracking is video frame i (frame_id - 1), which is submission row i.
    # Graded halves are published boundaries (DATA.md), not answers: outside them we write X.
    blocks = [(first, last + 1) for _, first, last in games.half_video_blocks(games.GAME)]
    return pipeline.predict(trk, cfg, blocks)


def write(path, labels):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write("frame,label\n")
        fh.writelines("{},{}\n".format(i, lab) for i, lab in enumerate(labels))
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True, help="file is named after the team, per SUBMISSION.md")
    ap.add_argument("--config")
    ap.add_argument("--sanity-public", action="store_true")
    args = ap.parse_args()

    cfg = pipeline.load_config(args.config)
    labels = build_labels(cfg)
    assert len(labels) == N_FRAMES
    path = os.path.join(ROOT, "submissions", "{}.csv".format(args.team))
    digest = write(path, labels)
    print("wrote {}  sha256 {}".format(path, digest))
    counts = {k: int(np.sum(labels == k)) for k in "HADX"}
    print("label counts", counts)

    validator = os.path.join(ROOT, "vendor", "mtah", "evaluation", "validate_submission.py")
    rc = subprocess.call([sys.executable, validator, path])
    if rc:
        raise SystemExit("validation FAILED -- do not submit this file")

    if args.sanity_public:
        gt_path = os.path.join(ROOT, "vendor", "mtah", "evaluation", "gt",
                               "BAR-ATH_possession_gt_public.csv")
        import pandas as pd
        gt = pd.read_csv(gt_path)["label"].astype(str).str.strip().str.upper().to_numpy()
        print("public-window SANITY check (not a decision metric):", pipeline.score(gt, labels))


if __name__ == "__main__":
    main()
