# Experiment log

One line per change that touched results. Dev numbers are `spellF1` from `scripts/score_dev.py`
(degraded mean ± seed spread / clean). Never record a choice made on the public 5 minutes.

| date | who | change | dev deg_mean | dev clean | notes |
|---|---|---|---|---|---|
| 2026-11-11 | setup | official baseline `smooth50` replicated on the dev set | 0.2541 | 0.3944 | reference; the real-match floor is 0.2433 |
| 2026-11-11 | setup | v0: nearest-player + dead-ball cues + Viterbi | 0.1217 | 0.3775 | player speed was measured frame to frame, so jitter read as motion |
| 2026-11-11 | setup | player speed over a 10-frame lag | 0.2220 ± 0.027 | 0.3783 | dead-ball detector now fires |
| 2026-11-11 | setup | sweep: switch 10, to/from dead 4, w_margin 2.5 | **0.4450 ± 0.024** | **0.5721** | plateau: the top 10 settings all fall within the seed spread |
| 2026-11-12 | segmenter | diagnosis: on the degraded copies 30% of GT possessions are <3 s and only 4% of those are matched; direct hand-overs are found a median 2.7 s late; stoppages under 8 s are mostly missed (but only 13 of 78 have the same team on both sides) | — | — | the leak is hand-over timing and short possessions, not dead balls |
| 2026-11-12 | segmenter | sweep: ball interpolation gap, control radius, fast-ball cutoff (`experiments/grids/evidence_v1.json`) | 0.4603 ± 0.022 | 0.5803 | **not adopted**: the gain is smaller than the seed spread |
| 2026-11-12 | segmenter | new carry signal: nearest player moving with the ball (`experiments/grids/carry_v1.json`) | 0.4634 ± 0.012 | 0.5672 | **not adopted**: the gain over the plain evidence sweep is noise; the code stays in, off by default (`w_carry` 0) |

## Submission files

| date | commit | config | sha256 | public-window sanity |
|---|---|---|---|---|
| 2026-11-11 | 292b142 | default.json (v0.1) | `160d12523e5271c11570349f937e2825d3aedb63161f8e669721c9f31cbee368` | not run; validates OK, X exactly on the 40,462 ungraded frames |
