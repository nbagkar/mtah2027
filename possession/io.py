"""Read Metrica FIFA/EPTS tracking (metadata XML + raw text) into plain numpy arrays.

One reader for both the challenge ATD and Metrica's public sample game 3, which share the format
but differ in detail: the ATD has 46 tracklet slots with x,y,speed per slot; the sample game has
22 slots with x,y, and its slot -> player mapping changes at every substitution (one
DataFormatSpecification block per stretch). Both are handled by reading the specification blocks
instead of assuming a fixed order.

Output (a Tracking namedtuple), all indexed by *row* = frame_id - first_frame_id:
    frame_id  (T,)    int64   the raw frame counter
    px, py    (T, S)  float32 player positions in metres, NaN where missing
    team      (T, S)  int8    0 = home, 1 = away, -1 = slot unused in that frame
    bx, by    (T,)    float32 ball position in metres, NaN where missing
    pitch     (L, W)  metres

Parsing 199k ATD lines is ~1 min in pure Python, so the result is cached as .npz next to the raw
file's name under data/cache/ (gitignored). Delete the cache to force a re-read.
"""

import hashlib
import os
import xml.etree.ElementTree as ET
from collections import namedtuple

import numpy as np

Tracking = namedtuple("Tracking", "frame_id px py team bx by pitch")

HOME, AWAY = 0, 1


def _strip_ns(root):
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def team_names(meta_path):
    """(home, away) club names as listed in the metadata. Home is the first team, which is
    the convention read_metadata() uses to assign slots to HOME (0) and AWAY (1)."""
    root = _strip_ns(ET.parse(meta_path).getroot())
    names = [(t.findtext("Name") or "").strip() for t in root.iter("Team")]
    if len(names) != 2:
        raise ValueError("{}: expected 2 teams, found {}".format(meta_path, len(names)))
    return names[0], names[1]


def check_home_team(meta_path, expected_home, expected_away):
    """Raise unless the metadata's first team is the expected home side.

    If this were wrong, every H in the submission would really mean A. That would destroy the
    score, and the validator can't detect it. Each expected name may be a string or a tuple of
    accepted spellings (the challenge's own files spell Athletic Club two ways).
    """
    home, away = team_names(meta_path)

    def norm(s):
        return "".join(ch for ch in s.lower() if ch.isalnum())

    def matches(name, expected):
        options = (expected,) if isinstance(expected, str) else expected
        return any(norm(o) in norm(name) for o in options)

    if not matches(home, expected_home) or not matches(away, expected_away) \
            or matches(home, expected_away):
        raise SystemExit(
            "HOME/AWAY CHECK FAILED: the tracking metadata lists ({!r}, {!r}) but the challenge "
            "says home is {!r} and away is {!r}. The H and A labels would be swapped, so do not "
            "submit.".format(home, away, expected_home, expected_away))
    return home, away


def read_metadata(meta_path):
    """(specs, pitch). specs = [(start_frame, end_frame, [team code per slot])]."""
    root = _strip_ns(ET.parse(meta_path).getroot())
    team_ids = [t.get("id") for t in root.iter("Team")]
    if len(team_ids) != 2:
        raise ValueError("{}: expected 2 teams, found {}".format(meta_path, len(team_ids)))
    home_id = team_ids[0]  # FIFA/EPTS convention: first team listed is home
    player_team = {p.get("id"): (HOME if p.get("teamId") == home_id else AWAY)
                   for p in root.iter("Player")}
    channel_player = {c.get("id"): c.get("playerId") for c in root.iter("PlayerChannel")}

    length = width = None
    for el in root.iter("FieldSize"):
        length = float(el.findtext("Width") or 0) or None
        width = float(el.findtext("Height") or 0) or None
    pitch = (length or 105.0, width or 68.0)

    specs = []
    for spec in root.iter("DataFormatSpecification"):
        slots = []
        players_register = None
        for reg in spec.findall("SplitRegister"):
            players_register = reg  # the per-player block: SplitRegister(";") of SplitRegister(",")
            break
        if players_register is not None:
            for group in players_register.findall("SplitRegister"):
                refs = [r.get("playerChannelId") for r in group.iter("PlayerChannelRef")]
                pid = channel_player.get(refs[0]) if refs else None
                slots.append(player_team.get(pid, -1))
        specs.append((int(spec.get("startFrame")), int(spec.get("endFrame")), slots))
    if not specs:
        # Fallback used by the challenge baseline: Player order is slot order.
        slots = [player_team[p.get("id")] for p in root.iter("Player")]
        specs = [(0, 10 ** 12, slots)]
    return specs, pitch


def _parse_pair(group):
    """First two comma fields of a group as floats; NaN if missing."""
    if not group or group[0] in "Nn":
        return np.nan, np.nan
    a = group.split(",")
    try:
        return float(a[0]), float(a[1])
    except (ValueError, IndexError):
        return np.nan, np.nan


def read_raw(raw_path, specs, pitch):
    length, width = pitch
    n_slots = max(len(s[2]) for s in specs)
    frame_ids, px, py, tm, bx, by = [], [], [], [], [], []
    spec_i = 0
    with open(raw_path) as handle:
        for line in handle:
            parts = line.rstrip("\n").split(":")
            if len(parts) < 3:
                continue
            fid = int(parts[0])
            while spec_i + 1 < len(specs) and fid > specs[spec_i][1]:
                spec_i += 1
            slot_team = specs[spec_i][2]
            groups = parts[1].split(";")
            xs = np.full(n_slots, np.nan, np.float32)
            ys = np.full(n_slots, np.nan, np.float32)
            ts = np.full(n_slots, -1, np.int8)
            for s, g in enumerate(groups[:n_slots]):
                x, y = _parse_pair(g)
                xs[s], ys[s] = x, y
                if s < len(slot_team):
                    ts[s] = slot_team[s]
            x, y = _parse_pair(parts[2])
            frame_ids.append(fid)
            px.append(xs); py.append(ys); tm.append(ts); bx.append(x); by.append(y)
    px = np.vstack(px) * length
    py = np.vstack(py) * width
    return Tracking(np.array(frame_ids, np.int64), px.astype(np.float32), py.astype(np.float32),
                    np.vstack(tm), (np.array(bx, np.float32) * length),
                    (np.array(by, np.float32) * width), pitch)


def load(meta_path, raw_path, cache_dir=None, pitch=None):
    """Load tracking, using/refreshing an .npz cache keyed on the raw file's size and mtime."""
    st = os.stat(raw_path)
    key = hashlib.sha1("{}|{}|{}|{}".format(os.path.abspath(raw_path), st.st_size,
                                            int(st.st_mtime), pitch).encode()).hexdigest()[:12]
    cache = None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cache = os.path.join(cache_dir, "{}_{}.npz".format(
            os.path.basename(raw_path).rsplit(".", 1)[0], key))
        if os.path.exists(cache):
            z = np.load(cache)
            return Tracking(z["frame_id"], z["px"], z["py"], z["team"], z["bx"], z["by"],
                            tuple(z["pitch"]))
    specs, meta_pitch = read_metadata(meta_path)
    trk = read_raw(raw_path, specs, pitch or meta_pitch)
    if cache:
        np.savez_compressed(cache, **{k: np.asarray(v) for k, v in trk._asdict().items()})
    return trk
