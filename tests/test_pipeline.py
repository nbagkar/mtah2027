"""Fast tests on synthetic data only -- CI never sees the match data."""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import io, pipeline, segment  # noqa: E402

META = """<?xml version="1.0"?>
<main><Metadata><GlobalConfig><FrameRate>25</FrameRate></GlobalConfig>
<Sessions><Session><MatchParameters><FieldSize><Width>105</Width><Height>68</Height></FieldSize>
</MatchParameters></Session></Sessions>
<Teams><Team id="H1"><Name>Home</Name></Team><Team id="A1"><Name>Away</Name></Team></Teams>
<Players><Player id="p1" teamId="H1"/><Player id="p2" teamId="A1"/></Players>
<Devices><Device><Sensors><Sensor><Channels>
<PlayerChannel id="c1x" playerId="p1"/><PlayerChannel id="c1y" playerId="p1"/>
<PlayerChannel id="c2x" playerId="p2"/><PlayerChannel id="c2y" playerId="p2"/>
</Channels></Sensor></Sensors></Device></Devices></Metadata>
<DataFormatSpecifications>
<DataFormatSpecification startFrame="1" endFrame="10" separator=":">
<StringRegister name="frameCount"/>
<SplitRegister separator=";">
 <SplitRegister separator=","><PlayerChannelRef playerChannelId="c1x"/><PlayerChannelRef playerChannelId="c1y"/></SplitRegister>
 <SplitRegister separator=","><PlayerChannelRef playerChannelId="c2x"/><PlayerChannelRef playerChannelId="c2y"/></SplitRegister>
</SplitRegister></DataFormatSpecification>
<DataFormatSpecification startFrame="11" endFrame="20" separator=":">
<StringRegister name="frameCount"/>
<SplitRegister separator=";">
 <SplitRegister separator=","><PlayerChannelRef playerChannelId="c2x"/><PlayerChannelRef playerChannelId="c2y"/></SplitRegister>
 <SplitRegister separator=","><PlayerChannelRef playerChannelId="c1x"/><PlayerChannelRef playerChannelId="c1y"/></SplitRegister>
</SplitRegister></DataFormatSpecification>
</DataFormatSpecifications></main>"""


def test_io_reads_specs_and_three_field_groups(tmp_path):
    meta = tmp_path / "m.xml"
    raw = tmp_path / "r.txt"
    meta.write_text(META)
    lines = []
    for f in range(1, 21):
        # ATD-style groups carry a third (speed) field; the reader must ignore it.
        lines.append("{}:0.5,0.5,1.0;NaN,NaN,NaN:0.5,0.25,0".format(f))
    raw.write_text("\n".join(lines) + "\n")
    trk = io.load(str(meta), str(raw))
    assert trk.px.shape == (20, 2)
    assert np.isclose(trk.px[0, 0], 52.5) and np.isnan(trk.px[0, 1])
    assert np.isclose(trk.by[0], 17.0)
    # Slot order swaps at the second specification block (a substitution / re-mapping).
    assert list(trk.team[0]) == [0, 1] and list(trk.team[15]) == [1, 0]


def synthetic(T=3000, seed=0):
    """Home keeps the ball, then away, with a stoppage in between, ball missing 40%."""
    rng = np.random.default_rng(seed)
    S = 4
    px = np.tile(rng.uniform(20, 80, S), (T, 1)).astype(np.float32)
    py = np.tile(rng.uniform(10, 60, S), (T, 1)).astype(np.float32)
    # Players jog around (alive) except during the stoppage.
    t = np.arange(T)[:, None]
    px += (15 * np.sin(t / 50.0 + np.arange(S))).astype(np.float32)  # ~7 m/s jog
    team = np.tile(np.array([0, 0, 1, 1], np.int8), (T, 1))
    owner = np.where(t[:, 0] < 1200, 0, 2)
    bx = px[np.arange(T), owner] + 0.5
    by = py[np.arange(T), owner].copy()
    stop = (t[:, 0] >= 1100) & (t[:, 0] < 1300)
    px[stop] = px[1100]
    py[stop] = py[1100]
    bx[stop] = -5.0  # out of play
    gt = np.where(t[:, 0] < 1100, "H", np.where(stop, "D", "A")).astype("<U1")
    hide = rng.random(T) < 0.4
    bx = bx.astype(np.float32)
    bx[hide & ~stop] = np.nan
    by = by.astype(np.float32)
    by[hide & ~stop] = np.nan
    return io.Tracking(np.arange(1, T + 1), px, py, team, bx, by, (105.0, 68.0)), gt


def test_pipeline_recovers_synthetic_possessions():
    trk, gt = synthetic()
    cfg = pipeline.load_config()
    pred = pipeline.predict(trk, cfg, [(0, len(gt))])
    s = pipeline.score(gt, pred)
    assert s["n_pred_spells"] == 2, s
    assert s["spell_f1_mean"] > 0.9, s


def test_pipeline_is_deterministic():
    trk, _ = synthetic(seed=3)
    cfg = pipeline.load_config()
    a = pipeline.predict(trk, cfg, [(0, 3000)])
    b = pipeline.predict(trk, cfg, [(0, 3000)])
    assert (a == b).all()


def test_outside_blocks_is_X():
    trk, _ = synthetic()
    pred = pipeline.predict(trk, pipeline.load_config(), [(100, 2000)])
    assert (pred[:100] == "X").all() and (pred[2000:] == "X").all()
    assert set(pred[100:2000]) <= {"H", "A", "D"}


def test_viterbi_switch_cost_suppresses_flicker():
    e = np.zeros((100, 3))
    e[::2, 0] = 1.0
    e[1::2, 1] = 1.0
    path = segment.viterbi(e, np.array([[0, 50, 50], [50, 0, 50], [50, 50, 0]], float))
    assert len(set(path.tolist())) == 1


def _meta_with_teams(tmp_path, home, away):
    meta = tmp_path / "teams.xml"
    meta.write_text(META.replace("<Name>Home</Name>", "<Name>{}</Name>".format(home))
                        .replace("<Name>Away</Name>", "<Name>{}</Name>".format(away)))
    return str(meta)


def test_home_team_check_passes_and_accepts_both_spellings(tmp_path):
    import pytest  # noqa: F401
    for away in ("Athletic Club", "Atletic Club"):
        m = _meta_with_teams(tmp_path, "FC Barcelona", away)
        assert io.check_home_team(m, "Barcelona", ("Athletic", "Atletic"))[0] == "FC Barcelona"


def test_home_team_check_catches_a_swap(tmp_path):
    import pytest
    m = _meta_with_teams(tmp_path, "Athletic Club", "FC Barcelona")
    with pytest.raises(SystemExit, match="HOME/AWAY CHECK FAILED"):
        io.check_home_team(m, "Barcelona", ("Athletic", "Atletic"))


def test_viterbi_min_dead_matches_brute_force():
    import itertools
    rng = np.random.default_rng(7)

    def total(path, e, c):
        return sum(e[t, path[t]] for t in range(len(path))) - \
            sum(c[path[t - 1], path[t]] for t in range(1, len(path)))

    def dead_runs_ok(path, k):
        runs = [(s, len(list(g))) for s, g in itertools.groupby(path)]
        return all(n >= k for s, n in runs if s == segment.D)

    for _ in range(100):
        T, k = int(rng.integers(1, 8)), int(rng.integers(1, 5))
        e = rng.normal(0, 3, (T, 3))
        c = rng.uniform(0, 6, (3, 3))
        np.fill_diagonal(c, 0)
        feasible = [p for p in itertools.product(range(3), repeat=T) if dead_runs_ok(p, k)]
        got = tuple(segment.viterbi(e, c, k))
        assert dead_runs_ok(got, k)
        assert abs(total(got, e, c) - max(total(p, e, c) for p in feasible)) < 1e-9


def test_control_and_bridge_pass_vs_turnover():
    from possession.features import control_and_bridge
    nan = np.nan
    # home controls 0-4, ball in flight 5-9, home again 10-14 (a pass) -> bridged home;
    # in flight 15-19, away controls 20-24 (a turnover) -> not bridged.
    team = np.array([0] * 5 + [nan] * 5 + [0] * 5 + [nan] * 5 + [1] * 5, float)
    d = np.where(np.isnan(team), 9.0, 1.0)
    speed = np.zeros(25)
    ctrl, run, bridge = control_and_bridge(team, d, speed, 2.0, 8.0, 10, None)
    assert list(ctrl[:5]) == [1] * 5 and list(ctrl[20:]) == [-1] * 5
    assert run[0] == 5 and run[7] == 0
    assert list(bridge[5:10]) == [1] * 5
    assert not bridge[15:20].any() and not bridge[:5].any()
    # A gap longer than max_gap is not bridged; nor is one that crosses a block boundary.
    assert not control_and_bridge(team, d, speed, 2.0, 8.0, 4, None)[2].any()
    assert not control_and_bridge(team, d, speed, 2.0, 8.0, 10, [(0, 8), (8, 25)])[2][5:8].any()
    # A fast ball is not control.
    fast = np.full(25, 20.0)
    assert not control_and_bridge(team, d, fast, 2.0, 8.0, 10, None)[0].any()


def test_restart_geometry_cue():
    from possession.deadball import dead_logodds, restart_distance
    L, W = 105.0, 68.0
    # touchline, corner, goal area, centre spot, open midfield
    bx = np.array([40.0, 0.5, 3.0, 52.5, 30.0])
    by = np.array([0.2, 67.5, 34.0, 34.0, 20.0])
    d = restart_distance(bx, by, (L, W))
    assert np.allclose(d[:4], [0.2, 0.5, 0.0, 0.0]) and d[4] > 10
    assert np.isnan(restart_distance(np.array([np.nan]), np.array([1.0]), (L, W))).all()

    cfg = pipeline.load_config()
    n = len(bx)
    feat = {"ball_seen": np.ones(n), "ball_out": np.zeros(n), "player_speed": np.full(n, np.nan),
            "ball_missing_run": np.zeros(n), "ball_speed": np.zeros(n),
            "ball_speed_1s": np.zeros(n), "bx": bx, "by": by, "pitch": (L, W)}
    off = dead_logodds(feat, cfg)
    on = dead_logodds(feat, pipeline.with_overrides(cfg, {"deadball.w_restart": 2.0}))
    assert (on[:4] > off[:4] + 1.0).all() and on[4] == off[4]
    # A moving ball at a restart spot gets nothing.
    feat["ball_speed_1s"] = np.full(n, 10.0)
    on = dead_logodds(feat, pipeline.with_overrides(cfg, {"deadball.w_restart": 2.0}))
    assert (on == dead_logodds(feat, cfg)).all()


def test_handover_previous_label_matches_scorer_fill():
    # A weak hand-over from H to A: with x_handover the masked frames carry H. Writing X instead
    # must give the same labels once X is forward-filled, which is what the scorer does.
    T = 200
    home = np.full(T, 3.0)
    home[100:] = -0.5          # A ahead, but weakly at first
    home[130:] = -3.0
    dead = np.full(T, -3.0)
    cfg = pipeline.with_overrides(pipeline.load_config(), {
        "segment.x_handover": True, "segment.x_weak_lo": 1.0, "segment.x_max_frames": 50,
        "segment.x_bridge_dead": 3, "segment.cost_team_switch": 2.0})
    prev = segment.decode(home, dead, cfg, [(0, T)])
    xs = segment.decode(home, dead, pipeline.with_overrides(cfg, {"segment.x_handover_write": "X"}),
                        [(0, T)])
    assert "X" not in set(prev) and "X" in set(xs)
    filled = xs.copy()
    for i in range(1, T):
        if filled[i] == "X":
            filled[i] = filled[i - 1]
    assert (filled == prev).all()
    off = segment.decode(home, dead, pipeline.with_overrides(cfg, {"segment.x_handover": False}),
                         [(0, T)])
    first_a = lambda lab: int(np.flatnonzero(lab == "A")[0])
    assert first_a(prev) > first_a(off)   # the hand-over moved later
