# BAP PM&T — technical document

More than a Hack 2027, Phase 1: per-frame possession (`H` / `A` / `D` / `X`) for FC Barcelona –
Athletic Club. Repository: github.com/nbagkar/mtah2027. Submitted model: **v0.7**
(`configs/default.json`); submission file sha256
`bd56dd7c9ff24bac899f2562308b7df886dce1413293d753d608dd59af618e70`.

## 1. Approach, and why

```
tactical ATD ──> features ──┬─> possessor: log-odds HOME vs AWAY, per frame
                            └─> dead ball: log-odds DEAD vs ALIVE, per frame
                                      │
                    3-state Viterbi over {H, A, D}, per graded half,
                    with a penalty for each kind of switch;
                    a weak hand-over waits for stronger evidence
                                      │
                         frame,label CSV (X outside the graded halves)
```

**Per-frame evidence.** Two small hand-built models turn the tracking into evidence, each frame on
its own:

- *Possessor* (`possession/possessor.py`). The distance from the ball to the nearest home player
  and the nearest away player. The closer team gets the evidence, capped at 5 m of difference.
  - It counts only when someone is within 2 m of the ball, and more the closer they are.
  - It counts less the faster the ball moves, and not at all above 25 m/s, because a pass in
    flight passes close to opponents without changing hands.
  - Ball gaps of up to 12 frames (0.5 s) are interpolated.
  - While the ball is still unknown, one weak ball-free cue speaks instead: the team in possession
    spreads wider. On the three clean dev games the wider team had the ball 81–83% of the time.
- *Dead ball* (`possession/deadball.py`). Pointing to a stoppage:
  - the ball is outside the pitch by more than 0.5 m;
  - a visible ball stays still over about 1 s;
  - the ball is lost for a stretch longer than 3 s;
  - the players are nearly still.

  Pointing to live play: the ball moves faster than 3 m/s over about 1 s.

**Segmentation** (`possession/segment.py`). `spellF1` counts whole possessions, so a flickering
per-frame answer invents many short ones and is punished for each. Instead of smoothing, we decode
the most likely sequence of states with a Viterbi pass. Each switch has a cost:

- 10 for a direct hand-over between teams;
- 10 to go into a dead ball;
- 10 to come out of one.

Those costs are what make the decoder hold a possession through a few frames of contrary evidence.
This was the largest single gain: the first sweep of the switch costs and the possessor weight
took the dev score from 0.22 to 0.45. Until v0.6 the dead-ball costs were 4 each. That let the
decoder hand the ball from one team to the other through a one-frame stoppage for less than the
cost of a direct hand-over, so short false stoppages were cheap.

**Late hand-overs** (v0.7). After decoding, each hand-over from one team to the other is checked.
If the new team's evidence is still weak there (log-odds under 1.0), the frames up to the point
where it becomes strong, at most 2 s, keep the previous team. A new possession that stays weak
from start to finish keeps the decoder's answer, so short real possessions are not erased. On the
dev set our hand-overs had been coming slightly early, and this moves them to where the new team
is actually in control.

**Why this rather than something else.**
- *A learned per-frame classifier* had nothing it could legitimately learn from. Labels for the
  match itself may not be used, and the only labelled tracking we used is Metrica's three public
  sample games. That is enough to choose about 30 interpretable parameters. It is not enough to
  train a model without it also learning Metrica's sample-data conventions.
- *Working from the video* (detection, ball tracking) would have repeated what the provided ATD
  already is, in four days, with no way to validate it on external data.
- *The official smoothing baseline* scores 0.277 on our degraded dev set; v0.7 scores 0.546.

Every parameter lives in one file, `configs/default.json`. Every change, with its before and after
dev scores, is in `experiments/LOG.md`.

**What changed after v0.1** (dev spellF1 on the degraded copies, mean of 3 games):

| version | change | degraded | clean |
|---|---|---|---|
| baseline | official `smooth50` | 0.277 | 0.427 |
| v0.1 | nearest player + dead-ball cues + Viterbi, switch costs swept | 0.432 | 0.563 |
| v0.2 | control radius 3 → 2 m, fast-ball cutoff 15 → 25 m/s | 0.452 | 0.578 |
| v0.3 | team width as evidence, only while the ball is invisible | 0.460 | 0.577 |
| v0.4 | slow-players term 1.0 → 0.15, long-missing 0.5 → 0.25 (it had been calling stoppages in slow build-up play) | 0.527 | 0.631 |
| v0.5 | player speed over 25 frames instead of 10, to survive noisier tracking | 0.523 | 0.630 |
| v0.6 | ball speed over 1 s; a still visible ball counts as a stoppage cue | 0.521 | 0.637 |
| v0.7 | late hand-overs; dead-ball costs 4 → 10, from a joint re-sweep of the segmenter | 0.546 | 0.668 |

v0.5 to v0.7 were not chosen for this column; §3 explains the robustness score they were chosen
on.

**Tried and dropped**, each measured on the dev set:
- a "carry" signal (the nearest player moving with the ball);
- team width or collective movement on every frame (a smooth signal drowns the ball);
- a minimum duration for dead spells, decoded exactly;
- an 80th-percentile player speed instead of the median;
- smoothing positions before measuring speed;
- gating the long-missing cue on slow players;
- pass detection: frames between two touches of the same team, and sustained control (+0.001);
- restart geometry: a still ball on a touchline, in a corner, in the goal area or on the centre
  spot (+0.001);
- writing `X` at weak hand-overs instead of the previous team's label: the scorer fills `X` with
  the previous label, so spellF1 is identical, but macroF1 counts every `X` as a miss.

Some of this code is still there, switched off; all of it is logged.

## 2. Assets used and dropped

| asset | used? | how / why not |
|---|---|---|
| tactical ATD (metadata + raw) | **yes**, the only input to the labels | player and ball positions and team membership. We do not read slot identities, because slots swap players. Per-slot speed is measured over 25 frames, and jumps faster than 12 m/s are discarded as identity switches. |
| tactical video | no | We built no vision pipeline, for the reasons in §1, and never compared our output with the video. |
| Smart Tagging | no | It is an allowed input, and its set pieces and team-tagged phases are an obvious prior. But none of our external games has Smart Tagging. So any weight on it would have had to be chosen on this match, which the rules forbid. |
| tactical homography | no | We work in pitch coordinates from the ATD. Ball-out detection uses the pitch size from `games.py`. |
| broadcast video / ATD / homography | no | Not synchronised with the tactical timeline, and covers less of the match (65.8% usable homography). |
| challenge repository (`vendor/mtah`, pinned submodule) | yes | The official scorer and validator, unchanged; frame count and pitch size from `games.py`; the graded-half boundaries published in DATA.md (outside them we write `X`). |

## 3. Training and validation data

**No labelled data from the provided game was used for anything.** That includes the public
5 minutes of ground truth: we chose no parameter on it and never scored our output on it.

**The one labelled dataset: Metrica Sports' public sample data**
(github.com/metrica-sports/sample-data, pinned to commit `e706dd5`, every file checked by sha256).
- **What it is:** three full professional matches with tracking and event data. The events were
  annotated by Metrica Sports.
- **How we labelled it:** `devset/build.py` turns the events into per-frame `H` / `A` / `D` labels
  mechanically, with no hand edits:
  - `D` runs from a stoppage event (ball out, foul, goal, or a shot that goes out) to the next
    restart;
  - otherwise a frame belongs to the team of the latest controlling event (pass, carry, recovery,
    set piece, shot);
  - challenges, ball losses and deflections change nothing.
- **How much:** 424,886 labelled frames, about 283 minutes:

| game | labelled frames | H / A / D | possessions |
|---|---|---|---|
| 1 | 142,074 | 30% / 30% / 41% | 325 |
| 2 | 140,114 | 36% / 30% / 35% | 304 |
| 3 | 142,698 | 38% / 35% / 28% | 370 |

As its README asks, we use this data responsibly and acknowledge it here: *tracking and event data
courtesy of Metrica Sports.*

**Making the sample data look like automatic tracking.** The sample tracking is clean. Each game
is therefore scored in three versions:

- **Degraded copies** (6 random seeds per game):
  - ball lost on about 41% of played frames, in bursts that are more likely in crowds and when the
    ball is fast;
  - 7% of player positions missing, in bursts of about 2 s;
  - 0.15 m of player position noise and 0.3 m of ball position noise.

  The 41% is the figure DATA.md publishes for the competition ATD ("41% of the graded" frames).
  The other values are our own assumptions. We computed no statistic from the competition data to
  set any of them.
- **"Stopball" copies** (3 seeds per game). Metrica's public tracking drops the ball on 82–99% of
  dead-ball frames, against 6–12% of live ones, so a model tuned on it learns that "ball gone a
  while" means a stoppage. An automatic tracker may instead keep the ball through stoppages. In
  these copies the ball stays visible through each stoppage, moving in a straight line from where
  it was lost to where play restarts. They are then degraded as above.
- **Clean copies**, for reference.

**How a change was accepted.**
- **v0.1:** tuned on game 3 alone. On games 1–2, which it had never seen, it beat the official
  baseline by 0.13–0.14 spellF1, so the method is not specific to one match.
- **v0.2 to v0.5:** a change was kept only if it raised the degraded score in every one of the
  three games.
- **From v0.6:** the deciding number is the **robust** score, which is, per game, the mean of the
  degraded and stopball scores. With 6 seeds, the standard error of one game's mean is about
  0.006, so per-game changes under 0.01 count as noise.
- **v0.7** came from a joint re-sweep of the segmenter after the feature freeze: 81 + 64 + 18
  settings around the candidate. Every one beat v0.6, and the scores level off once the dead-ball
  costs reach about 8, so we took a setting from the middle of that flat region rather than the
  single best one. Paired with v0.6 on the same resampled possessions, the gain is +0.033, 90%
  [0.026, 0.039], and all three games go up in every one of 1,000 draws.
- **One exception, decided by the team.** v0.5 lost 0.009 / 0.008 in two games to make the
  dead-ball cue survive heavier position noise. We re-degraded the dev games with 0.07–0.60 m of
  noise. At 0.45 m, v0.4 fell from 0.53 to 0.38, while v0.5 held at 0.53.

| v0.7 on the dev set | degraded | stopball | robust | clean |
|---|---|---|---|---|
| game 1 / 2 / 3 | 0.551 / 0.544 / 0.543 | 0.498 / 0.490 / 0.510 | 0.525 / 0.517 / 0.527 | 0.694 / 0.647 / 0.661 |
| mean | **0.546** | **0.500** | **0.523** | **0.668** |
| v0.6, for comparison | 0.521 | 0.459 | 0.490 | 0.637 |

**How much of that is luck.** `scripts/bootstrap_dev.py` (`make bootstrap`) puts a 90% interval on
each number. It uses the official scorer's own method: it resamples each game's real possessions
with replacement, 1,000 times, and rescores. In every draw, all copies of a game share the same
resampled possessions, so `robust` is resampled as one number. The seed is fixed, so the intervals
regenerate exactly.

| v0.7, 90% interval | robust | degraded | stopball | clean |
|---|---|---|---|---|
| game 1 | 0.525 [0.488, 0.560] | 0.551 [0.513, 0.587] | 0.498 [0.460, 0.536] | 0.694 [0.654, 0.730] |
| game 2 | 0.517 [0.480, 0.555] | 0.544 [0.502, 0.586] | 0.490 [0.452, 0.528] | 0.647 [0.601, 0.693] |
| game 3 | 0.527 [0.492, 0.563] | 0.543 [0.506, 0.581] | 0.510 [0.472, 0.546] | 0.661 [0.624, 0.700] |
| mean of 3 | **0.523 [0.501, 0.545]** | 0.546 [0.524, 0.569] | 0.500 [0.477, 0.522] | 0.668 [0.643, 0.691] |

- **One match is noisy.** A single game's interval is about ±0.037 wide, close to the official
  scorer's own noise band of 0.04 for a full match. The real match is one game, so its score could
  differ from our dev mean by that much from the choice of possessions alone.
- **We still clear the floor by a wide margin.** The lowest end of any single-game interval, on
  the hardest copies (stopball), is 0.452. The official baseline scores 0.277 on our dev set and
  0.2433 on the real match.
- **Seeds add little.** The standard error between random copies of one game is 0.004–0.011 for
  the degraded copies and 0.001–0.021 for the stopball copies, smaller than the possession noise.
- **What this does not cover:** how far the real tracking differs from our simulated copies
  (§6). That risk is not random, so no bootstrap can measure it.

Following the organisers' clarification of 2026-11-11:
- no parameter was trained, fitted, calibrated or tuned on the competition match's ground truth or
  video;
- our output was never checked against the video;
- no competition data was uploaded to an AI service.

The code was written with the help of an AI coding assistant (Claude, Anthropic). It never saw
competition data or frame-level output. It saw only dev-set scores and the summary lines of the
submission script: row count, format check, checksum and label shares.

## 4. Possession rules implemented

- **Loose and contested balls.** Possession stays with the last team in control. Nothing in the
  evidence says "loose". Near a contested ball both teams are close, so the evidence for either
  side is small, and the 10-point cost of a hand-over keeps the current team in possession.
- **Challenges, touches and deflections.** A team takes over only once its evidence has outweighed
  the switch cost for long enough. So a touch, a deflection or a duel won without control does not
  move possession. A ball faster than 25 m/s gives no possessor evidence at all, so a pass that
  flies past an opponent does not count as an interception. When a hand-over does happen on weak
  evidence, it is dated to the first frame where the new team's evidence is strong, up to 2 s
  later (§1).
- **Restarts.** Every stoppage is `D`, and `D` carries no team, as the challenge asks. After a
  stoppage the decoder may start with either team. The team that restarts is the one whose player
  is nearest the ball once it moves.
- **Where `D` starts and ends.** `D` starts when the ball leaves the pitch, or stops dead while the
  players are nearly still. It ends when the ball moves again over about 1 s and the players speed
  up. Going into and out of a dead ball costs 10 each, so a stoppage needs clear evidence, and a
  momentary one inside a possession is absorbed by it. We set no hard minimum duration: that did
  not help (§1).
- **`X`** is written only outside the graded halves published in DATA.md, never as an abstention
  inside them. Frames held back at a weak hand-over carry the previous team's label, not `X`.

## 5. Handling missing and noisy tracking

- **Missing ball (41% of graded frames).**
  - Gaps up to 0.5 s are interpolated.
  - In longer gaps there is no possessor evidence, so the decoder keeps the current state.
  - The team-width cue speaks only there, at a low weight.
  - A ball lost for more than 3 s is weak evidence of a stoppage. It is deliberately weak (0.25),
    because the stopball copies showed how much that cue depends on the tracker's conventions.
- **Position noise.**
  - Player speed is measured as displacement over 25 frames, not frame to frame. On its own, 0.15
    m of noise reads as about 5 m/s at a 1-frame lag, but only about 0.3 m/s at 25 frames.
  - Ball speed for the dead-ball cues is measured over 1 s for the same reason: 0.3 m of ball
    noise makes a still ball look like it moves at about 5 m/s over 3 frames.
- **Tracking identities.** Slots appear, vanish and swap players. We use only positions and team
  membership, take the median speed over all visible slots, and drop jumps over 12 m/s.
- **Missing players.** Distances and medians use whichever slots are present on each frame.

## 6. Limitations

- **We cannot see our real-match score.** Every number above comes from Metrica's games, and our
  degraded copies only imitate automatic tracking. The real ATD's noise level and its handling of
  the ball during stoppages are unknown to us. They are the two settings our score depended on
  most.
- **Very noisy tracking.** We re-noised the dev games to see where v0.7 stops paying. It beats
  v0.6 by 0.02–0.04 with half or twice our assumed position noise, with the ball lost half or 1.6
  times as often, with ball-loss bursts twice as long and with 15% of player positions missing. It
  also holds with four times the noise on the players alone. With three to four times the noise
  on ball and players together (0.45–0.6 m and 0.9–1.2 m), every version falls to 0.32–0.43, and
  v0.7 falls 0.01–0.03 further than v0.6.
- **Different labelling conventions.** Our dev labels come from annotated events. The real ground
  truth comes from corrected tracking. The two can disagree on exactly when a stoppage starts and
  when a new team counts as in control.
- **Stoppages with a visible ball.** These remain the weakest case: 0.500 on the stopball copies,
  against 0.546 on the degraded ones.
- **Fewer, longer possessions.** v0.7 resists switching, so on degraded tracking it finds about 245
  possessions per game where the labels have 333 (v0.6: 280). Short possessions inside a scramble
  are merged into their neighbours. On the dev set that trade pays, but a match with many quick
  turnovers would suffer.
- **Wrong team in live play.** About 9% of live frames went to the wrong team on v0.6, whether
  the ball was visible or not. Possessions of 3–6 s are the largest group we could still recover.
- **Invisible ball.** With the ball invisible in live play, about 23% of frames are labelled dead
  (54% once it has been gone for more than 3 s; measured on v0.5).
- **No player-level reasoning.** We never follow one player over time, so a short possession by
  one player looks the same as a scramble.

**What we would fix with more time:**
- *A learned pass model.* Our hand-built pass cue did not help (§1). The wrong-team frames still
  need a better account of who receives the ball, which would take more labelled games than three.
- *Kick-off detection:* both teams in their own halves and the ball on the centre spot. The plain
  restart-geometry cue did not help, partly because a goalkeeper holds the ball in the goal area
  in live play.
- *Smart Tagging set pieces as restart anchors,* once there is an external match with Smart
  Tagging to validate them on.
- *More external games,* in more tracking formats, so that fewer of the parameters rest on three
  matches from one provider.

## 7. Reproduction

Python 3.11+ (tested on 3.12); dependencies pinned in `requirements.txt`. About 6 minutes
end to end.

```bash
git clone --recurse-submodules https://github.com/nbagkar/mtah2027 && cd mtah2027
make setup                               # venv, pinned deps, pre-commit data guard
make test                                # 13 tests on synthetic data
make dev                                 # build the dev set from the sample games, score it
make bootstrap                           # 90% intervals on the dev scores (section 3)
export MTAH_DATA_DIR=/path/to/bundle     # the organisers' data bundle (or unpack into ./data)
make submission                          # -> submissions/BAP PM&T.csv, validated, sha256 printed
```

The output is deterministic: the same data, config and pinned dependencies give a byte-identical
file. v0.7's sha256 is `bd56dd7c9ff24bac899f2562308b7df886dce1413293d753d608dd59af618e70`, and
`make dev` prints robust 0.5228, degraded 0.5461, stopball 0.4995 and clean 0.6675. On 2026-11-16
a fresh clone of the repository reproduced all of these: the file byte for byte, the dev scores and
the bootstrap intervals. A second team member's laptop gave the same sha256.

Across platforms: `scripts/dev_fingerprint.py` hashes the pipeline's labels on all 30 dev copies
(4.3 million frames). macOS on Intel, Linux on x86-64 and Linux on arm64 give the same hash, so we
expect the submission file to regenerate identically on Linux too. We could not test that
directly, because the match data never leaves our laptops.
