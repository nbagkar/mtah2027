# Ball possession from automatic tracking — More than a Hack 2027

Our entry to [Phase 1](https://github.com/metrica-sports/more-than-a-hack-2027): one label per
video frame (`H` / `A` / `D` / `X`) for FC Barcelona – Athletic Club, ranked on `spellF1`.

**Team members: read [TEAM.md](TEAM.md) first.** It has the rules that can get us disqualified,
who owns what, and the schedule.

## Approach (v0.7)

```
ATD tracking ──> features ──┬─> possessor: log-odds HOME vs AWAY per frame
                            └─> dead ball: log-odds DEAD vs ALIVE per frame
                                      │
                         3-state Viterbi over {H, A, D}, per half,
                         with penalties for each kind of switch
                                      │
                               frame,label CSV
```

- **Possessor** — nearest player of each team to the ball (ball gaps ≤ 0.5 s interpolated),
  trusted only when someone is within 2 m and the ball isn't moving faster than 25 m/s. While
  the ball is invisible, a weak ball-free cue speaks instead: the team in possession plays wider.
- **Dead ball** — ball outside the pitch, ball moving or sitting still over 1 s, long ball absence, and players
  nearly static (speed over 1 s, so tracking jitter can't fake movement). The last is only a light nudge: weighted heavily, it calls stoppages during slow
  build-up play whenever the ball is invisible.
- **Segmenter** — Viterbi decoding. Its switch penalties (10 for a hand-over, 10 into and out of a
  dead ball) are what turn flickering frame evidence into whole possessions, which is what
  `spellF1` counts. A hand-over made on weak evidence is moved later, to where the new team's
  evidence is strong (at most 2 s); those frames keep the previous team's label.

All parameters were chosen on a **dev set built from other matches**: Metrica's three public
sample games, with labels derived from their event data and tracking degraded to look like the
competition ATD. None was chosen on the competition match. See [devset/build.py](devset/build.py).

| spellF1 on the dev set (3 games) | clean tracking | degraded (mean of seeds × 3 games; 6 seeds from v0.3 on, 3 above) | degraded, per game |
|---|---|---|---|
| official baseline `smooth50` | 0.4271 | 0.2773 | 0.297 / 0.280 / 0.256 |
| ours, v0.1 | 0.5631 | 0.4323 | 0.428 / 0.418 / 0.451 |
| ours, v0.2 | 0.5777 | 0.4522 | 0.455 / 0.436 / 0.466 |
| ours, v0.3 | 0.5774 | 0.4601 | 0.454 / 0.447 / 0.479 |
| ours, v0.4 | 0.6306 | 0.5266 | 0.528 / 0.524 / 0.528 |
| ours, v0.5 | 0.6300 | 0.5234 | 0.523 / 0.520 / 0.528 |
| ours, v0.6 | 0.6365 | 0.5211 | 0.520 / 0.523 / 0.521 |
| ours, v0.7 | 0.6675 | 0.5461 | 0.551 / 0.544 / 0.543 |

**Since v0.6, decisions use `robust` spellF1.** Metrica's public tracking drops the ball during
nearly every stoppage, which an automatic tracker may not do. So the dev set also has "stopball"
copies where the ball stays visible through stoppages, and `robust` is, per game, the mean of
the two kinds of copy:

| robust spellF1 (3 games) | degraded | stopball | robust, per game |
|---|---|---|---|
| ours, v0.5 | 0.5234 | 0.4081 | 0.466 / 0.459 / 0.472 |
| ours, v0.6 | 0.5211 | 0.4593 | 0.490 / 0.487 / 0.493 |
| **ours, v0.7** | **0.5461** | **0.4995** | **0.525 / 0.517 / 0.527** |

## Reproduce

Python 3.11+ recommended (tested on 3.12).

```bash
git clone --recurse-submodules <this repo> && cd mtah2027
make setup                         # venv + pinned deps + pre-commit data guard
make dev                           # build the dev set and score the pipeline on it
export MTAH_DATA_DIR=/path/to/bundle   # or unpack the bundle into ./data
make submission TEAM=<TeamName>    # -> submissions/<TeamName>.csv, validated, sha256 printed
```

`vendor/mtah` is the organisers' repository pinned as a submodule, so the scorer and validator we
use are byte-for-byte the official ones.

## Layout

```
possession/      io (EPTS reader) · features · possessor · deadball · segment · pipeline
configs/         default.json — every parameter, in one place
devset/          builds the dev set from the public sample game
scripts/         score_dev · sweep · baseline_dev · make_submission · data guard
tests/           synthetic-data tests (CI never sees match data)
docs/            technical document (submitted)
experiments/     LOG.md — every change, with before/after dev scores
vendor/mtah/     official challenge repo (submodule, pinned)
```
