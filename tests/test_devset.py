"""The dev-set builders, on tiny synthetic files (no downloads in CI)."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from devset import build  # noqa: E402

HEADER_H = ",,,Home,,Home,,\n,,,1,,2,,\nPeriod,Frame,Time [s],Player1,,Player2,,Ball,\n"
HEADER_A = ",,,Away,,Away,,\n,,,3,,4,,\nPeriod,Frame,Time [s],Player3,,Player4,,Ball,\n"


def test_csv_tracking_reader(tmp_path):
    h, a = tmp_path / "h.csv", tmp_path / "a.csv"
    h.write_text(HEADER_H + "1,1,0.04,0.5,0.5,NaN,NaN,0.5,0.25\n1,2,0.08,0.5,0.5,0.1,0.1,0.5,0.25\n")
    a.write_text(HEADER_A + "1,1,0.04,0.2,0.2,0.3,0.3,0.5,0.25\n1,2,0.08,0.2,0.2,0.3,0.3,0.5,0.25\n")
    trk = build.read_csv_tracking(str(h), str(a))
    assert trk.px.shape == (2, 4)
    assert np.isclose(trk.px[0, 0], 52.5) and np.isclose(trk.by[0], 17.0)
    assert list(trk.team[0]) == [0, -1, 1, 1]  # a substitute not on the pitch is no team
    assert list(trk.team[1]) == [0, 0, 1, 1]


def ev(i, team, etype, sub, start, end=None, period=1):
    return {"index": i, "team": {"id": team} if team else None, "type": {"name": etype},
            "subtypes": {"name": sub} if sub else None, "period": period,
            "start": {"frame": start}, "end": {"frame": end if end is not None else start}}


def test_shot_out_stops_play_until_restart():
    frames = np.arange(1, 101)
    events = [ev(0, "Home", "SET PIECE", "KICK OFF", 1), ev(1, "Home", "PASS", None, 1, 10),
              ev(2, "Home", "SHOT", "OFF TARGET-OUT", 30, 35),
              ev(3, "Away", "PASS", "GOAL KICK", 60, 70), ev(4, "Away", "PASS", None, 90, 100)]
    gt = build.gt_from_events(events, frames, "Home")
    assert gt[20] == "H" and gt[45] == "D" and gt[65] == "A"
