# Experiment log

One line per change that touched results. Dev numbers are `spellF1` from `scripts/score_dev.py`
(degraded mean ± seed spread / clean). Never record a choice made on the public 5 minutes.
From 2026-11-12 the dev set is three games, and the bracketed numbers are degraded scores for games 1 / 2 / 3.

| date | who | change | dev deg_mean | dev clean | notes |
|---|---|---|---|---|---|
| 2026-11-11 | setup | official baseline `smooth50` replicated on the dev set | 0.2541 | 0.3944 | reference; the real-match floor is 0.2433 |
| 2026-11-11 | setup | v0: nearest-player + dead-ball cues + Viterbi | 0.1217 | 0.3775 | player speed was measured frame to frame, so jitter read as motion |
| 2026-11-11 | setup | player speed over a 10-frame lag | 0.2220 ± 0.027 | 0.3783 | dead-ball detector now fires |
| 2026-11-11 | setup | sweep: switch 10, to/from dead 4, w_margin 2.5 | **0.4450 ± 0.024** | **0.5721** | plateau: the top 10 settings all fall within the seed spread |
| 2026-11-12 | segmenter | diagnosis: on the degraded copies 30% of GT possessions are <3 s and only 4% of those are matched; direct hand-overs are found a median 2.7 s late; stoppages under 8 s are mostly missed (but only 13 of 78 have the same team on both sides) | — | — | the leak is hand-over timing and short possessions, not dead balls |
| 2026-11-12 | segmenter | sweep: ball interpolation gap, control radius, fast-ball cutoff (`experiments/grids/evidence_v1.json`) | 0.4603 ± 0.022 | 0.5803 | **not adopted**: the gain is smaller than the seed spread |
| 2026-11-12 | segmenter | new carry signal: nearest player moving with the ball (`experiments/grids/carry_v1.json`) | 0.4634 ± 0.012 | 0.5672 | **not adopted**: the gain over the plain evidence sweep is noise; the code stays in, off by default (`w_carry` 0) |
| 2026-11-12 | validation | dev set grows to Metrica sample games 1-2 (CSV format); the label rule now treats a shot that goes out or scores as a stoppage (game 3 had missed these, so its D share rose 24% → 28%) | — | — | dead-ball share now 41% / 35% / 28%, plausible for a pro match. Every number above this line was on the old game-3 labels |
| 2026-11-12 | validation | re-baseline on 3 games: official `smooth50` | 0.2773 [0.297 0.280 0.256] | 0.4271 | |
| 2026-11-12 | validation | re-baseline on 3 games: v0.1 | 0.4323 [0.428 0.418 0.451] | 0.5631 | games 1-2 were never used to tune v0.1, so this is a held-out check, and it holds |
| 2026-11-12 | segmenter | **v0.2**: control radius 3 → 2 m, fast-ball cutoff 15 → 25 m/s | **0.4522 [0.455 0.436 0.466]** | **0.5777** | adopted: better in every game and on clean. `experiments/grids/recheck_3games.json` |
| 2026-11-12 | segmenter | carry signal on top of v0.2 | 0.4531 [0.455 0.436 0.469] | 0.5751 | not adopted: +0.001, flat in two games, clean drops |
| 2026-11-12 | possessor | measured ball-free team-shape signals on the clean dev games: the wider team has the ball 81-83% of the time in every game (77-78% while the ball is invisible). Collective movement toward goal reaches 58-65%, team length 61-69% | — | — | width is the only strong one |
| 2026-11-12 | possessor | width + movement as evidence on every frame, weight ≥ 1 (`experiments/grids/shape_v1.json`) | 0.38-0.40 | 0.52-0.56 | **rejected**: a smooth signal present on every frame adds up over a possession and drowns the ball |
| 2026-11-12 | segment | (from the same sweep) a direct team-switch cost above cost_to_dead + cost_from_dead = 8 changes nothing: the decoder switches through a one-frame D instead | — | — | tested below: closing it doesn't help |
| 2026-11-12 | possessor | **v0.3**: width evidence only while the ball is invisible, weight 0.05 (`experiments/grids/shape_v2.json`) | **0.4598 [0.457 0.449 0.473]** | **0.5774** | adopted: up +0.003 / +0.013 / +0.007, clean flat (−0.0003) |
| 2026-11-12 | possessor | same at weight 0.1 | 0.4615 [0.455 0.448 0.481] | 0.5761 | not adopted: game 1 +0.0007 is flat and clean drops |
| 2026-11-12 | segment | measured the one-frame-D shortcut: ~55 predicted dead spells per game last ≤ 5 frames and sit between two different teams; real stoppages under 1 s are 0-1% of GT | — | — | |
| 2026-11-12 | segment | new `segment.min_dead_frames` (a dead spell must last ≥ K frames, exact duration-chain Viterbi) swept with switch 5-40 and to/from dead 2-4 (`experiments/grids/min_dead_v1.json`, `min_dead_v2.json`) | best with K > 1: 0.4575 [0.458 0.444 0.471] | 0.5695 | **rejected**: every K > 1 scores below v0.3, and once the shortcut is closed a switch cost above 10 hurts too. The cap at 8 was never binding: the best switch cost is ~8-10 either way. Option stays in, default 1 = identical output |

| 2026-11-12 | segmenter | hand-over diagnosis, redone: switches are found slightly *early* (median −0.2 to −0.7 s), not late. On degraded tracking, frames with the ball visible are 90% right; with it invisible (45% of live frames) 67-75%, the errors split between false D (9-20%) and wrong team (13-17%). The 3-6 s possessions are the biggest recoverable group | — | — | the earlier "2.7 s late" figure does not reproduce |
| 2026-11-12 | dead ball | 80th-percentile player speed instead of the median (`experiments/grids/deadball_v1.json`) | below the median at matching settings | — | rejected, option removed (it was also 14x slower) |
| 2026-11-12 | dead ball | `w_slow` 1.0 → 0.5 (`deadball_v1.json`) | 0.5081 [0.506 0.506 0.513] | 0.6147 | first sign the slow-players term was far too strong |
| 2026-11-12 | dead ball | down to `w_slow` 0 (`deadball_v2.json`, `deadball_v3.json`) | 0.40-0.53 | 0.53-0.64 | cliffs: neighbouring settings differ by up to 0.08, because the running-players term and the long-missing term nearly cancel while the ball is missing. With `w_slow` 0, 0.445 |
| 2026-11-12 | dead ball | long-missing term gated on slow players (`deadball_v4.json`, option `long_missing_needs_slow`) | 0.44-0.51, best 0.5112 | 0.56-0.63 | smooth, but below the ungated peak; code in, off |
| 2026-11-12 | validation | stress test, dev games re-degraded with ball loss x0.5 / x1.6 / 2.4 s bursts and position jitter 0.07 / 0.30 / 0.45 m: the v0.4 setting beats v0.3 and the gated variant under every one (e.g. jitter 0.30 m: 0.503 vs 0.373 / 0.404). At 0.45 m everything falls to ~0.38 | — | — | the cliff is in parameter space, not in the noise; real-ATD jitter is the open risk |
| 2026-11-12 | dead ball | **v0.4**: `w_slow` 1.0 → 0.15, `w_long_missing` 0.5 → 0.25 | **0.5274 [0.531 0.528 0.523]** | **0.6306** | adopted: +0.074 / +0.079 / +0.050 per game, clean +0.053 |

## Submission files

| date | commit | config | sha256 | public-window sanity |
|---|---|---|---|---|
| 2026-11-11 | 292b142 | default.json (v0.1) | `160d12523e5271c11570349f937e2825d3aedb63161f8e669721c9f31cbee368` | not run; validates OK, X exactly on the 40,462 ungraded frames |
| 2026-11-12 | 5a0d60f | default.json (v0.2) | `18937a8f3088ad9dd4c53d9e5612fdadf6e6e255acaa579ae1c7e3a6bc1a21ca` | not run; validates OK, X exactly on the 40,462 ungraded frames |
| 2026-11-12 | 402cf23 | default.json (v0.3) | `ed0aed2f43f0237abba2c99a4a22ee9bdd10cb7df1828f95394ae9388d4ac1bd` | not run; validates OK, X exactly on the 40,462 ungraded frames, home/away check OK |
