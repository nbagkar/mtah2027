# Experiment log

One line per change that touched results. Dev numbers are `spellF1` from `scripts/score_dev.py`
(degraded mean ± seed spread / clean). Never record a choice made on the public 5 minutes.

| date | who | change | dev deg_mean | dev clean | notes |
|---|---|---|---|---|---|
| 2026-11-11 | setup | official baseline `smooth50` replicated on the dev set | 0.2541 | 0.3944 | reference; the real-match floor is 0.2433 |
| 2026-11-11 | setup | v0: nearest-player + dead-ball cues + Viterbi | 0.1217 | 0.3775 | player speed was measured frame to frame, so jitter read as motion |
| 2026-11-11 | setup | player speed over a 10-frame lag | 0.2220 ± 0.027 | 0.3783 | dead-ball detector now fires |
| 2026-11-11 | setup | sweep: switch 10, to/from dead 4, w_margin 2.5 | **0.4450 ± 0.024** | **0.5721** | plateau: the top 10 settings all fall within the seed spread |

## Submission files

| date | commit | config | sha256 | public-window sanity |
|---|---|---|---|---|
