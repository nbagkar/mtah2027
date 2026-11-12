# Ball possession from automatic tracking — More than a Hack 2027

Our entry to [Phase 1](https://github.com/metrica-sports/more-than-a-hack-2027): one label per
video frame (`H` / `A` / `D` / `X`) for FC Barcelona – Athletic Club, ranked on `spellF1`.

**Team members: read [TEAM.md](TEAM.md) first.** It has the rules that can get us disqualified,
who owns what, and the schedule.

## Approach (v0.2)

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
  trusted only when someone is within 2 m and the ball isn't moving faster than 25 m/s.
- **Dead ball** — ball outside the pitch, players nearly static, long ball absence, ball moving.
- **Segmenter** — Viterbi decoding. Its switch penalties are what turn flickering frame evidence
  into whole possessions, which is what `spellF1` counts.

All parameters were chosen on a **dev set built from other matches**: Metrica's three public
sample games, with labels derived from their event data and tracking degraded to look like the
competition ATD. None was chosen on the competition match. See [devset/build.py](devset/build.py).

| spellF1 on the dev set (3 games) | clean tracking | degraded (mean of 3 seeds × 3 games) | degraded, per game |
|---|---|---|---|
| official baseline `smooth50` | 0.4271 | 0.2773 | 0.297 / 0.280 / 0.256 |
| ours, v0.1 | 0.5631 | 0.4323 | 0.428 / 0.418 / 0.451 |
| **ours, v0.2** | **0.5777** | **0.4522** | **0.455 / 0.436 / 0.466** |

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
