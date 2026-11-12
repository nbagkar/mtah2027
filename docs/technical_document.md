# <Team name> — technical document

*Owner: role 5. Keep it to a few pages. Export to `<team>.pdf` for the form. SUBMISSION.md lists
what it must cover, and the headings below follow that list.*

## 1. Approach, and why

Per-frame evidence → 3-state Viterbi segmentation. Why segment rather than smooth: `spellF1`
counts whole possessions, and a decoder that pays for every switch is the direct way to stop
inventing possessions. (Fill in what changed after v0.1 and what each change bought on the dev set.)

## 2. Assets used and dropped

| asset | used? | how / why not |
|---|---|---|
| tactical ATD | yes | players + ball positions |
| Smart Tagging | | |
| homography | | |
| tactical video | | |
| broadcast video / ATD | | |

## 3. Training and validation data

No labels on the competition match were used for anything. The parameters were chosen on Metrica's public
sample game 3 (github.com/metrica-sports/sample-data): its hand-annotated event data was turned
mechanically into per-frame H/A/D labels (`devset/build.py`), and its tracking was degraded to
match the competition ATD (ball missing on ~41% of played frames, in bursts that are more likely in
crowds and in flight; player dropouts; position jitter).

Dev data source and acknowledgement: Metrica Sports sample data,
https://github.com/metrica-sports/sample-data. It is used for validation and tuning only, as
its README asks: responsibly, and with this acknowledgement.

Per the organisers' clarification of 2026-11-11: no parameter was trained, fitted, calibrated
or tuned on the competition match's ground truth or video, and our output was never checked
against the video.

## 4. Possession rules implemented

- Loose and contested balls: possession stays with the last team in control. The switch penalty
  is what enforces this.
- Restarts:
- Challenges and deflections:

## 5. Handling missing and noisy tracking

- Ball gaps ≤ 12 frames: linear interpolation. Longer gaps: no possessor evidence, so the
  decoder carries the current state.
- Identity switches: player speed is measured over a 10-frame lag and teleports over 12 m/s are
  dropped.

## 6. Limitations

## 7. Reproduction

See README → Reproduce. Final file sha256: `…`
