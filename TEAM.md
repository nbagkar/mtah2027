# Team playbook — More than a Hack 2027, Phase 1

Deadline **Tue Nov 17, 23:59 CET** (17:59 New York). We submit by **Tue 12:00 CET** and keep the rest of
the day as buffer. Scored on `spellF1` on the private full match; floor to beat is 0.2433.

## Five non-negotiables (each one can disqualify us)

1. **No match data in git, ever.** The repo goes public at submission and history is forever.
   Run `scripts/install_hooks.sh` once after cloning; CI runs the same check on every push.
2. **No match data in any cloud LLM.** The terms forbid uploading the videos, tracking, tagging or
   *any extract* to ChatGPT / Claude / Gemini / Copilot chat. Code, error messages and aggregate
   scores are fine; frames, rows, screenshots and plots of the match are not. Local models are fine.
3. **No hand labels and no frame-specific constants on the match.** Watching the video to get ideas
   is fine. Writing down "the second half kicks off at frame N" and hard-coding it is not — detect
   it with code.
4. **Never choose between versions on the public 5 minutes.** It's 17 possessions; it picks the wrong
   answer even for the official baseline. Decisions come from `scripts/score_dev.py` (another game).
   `make_submission.py --sanity-public` exists only to catch alignment bugs.
5. **The final file must regenerate byte-for-byte from the repo.** Pinned deps, no randomness
   without a fixed seed, sha256 recorded in `experiments/LOG.md`.

## Roles

Each owns one module, so five people can work at once without merge conflicts. Owners review PRs
that touch their file.

| # | role | owns | first things to try |
|---|---|---|---|
| 1 | **Lead / integration** | `possession/pipeline.py`, `configs/`, `scripts/make_submission.py`, the form | run v0 on the real data today; sanity-check alignment; own the final file, the Google account upload, the reproducibility check |
| 2 | **Dead ball** | `possession/deadball.py` | Smart Tagging SET PIECES as restart anchors; restart geometry (ball still on a line/corner/centre spot); kickoff detection; ball out of bounds from the homography |
| 3 | **Possessor** | `possession/possessor.py`, `possession/features.py` | control = same player near the ball for N frames; pass detection (ball leaves team T, arrives at team T); team shape when the ball is missing (41% of frames); Smart Tagging team phases as a prior |
| 4 | **Segmenter** | `possession/segment.py` | minimum-duration / semi-Markov decoding; separate costs for H↔A vs via D; when to write `X` (free inside a possession, costly at a hand-over — see EVALUATION.md) |
| 5 | **Validation + write-up** | `devset/`, `docs/technical_document.md` | calibrate the degradation to the real ATD's *aggregate* stats (ball-missing rate in crowds/in flight, slot churn); add sample games 1–2 as a second dev game; bootstrap intervals; own the technical document |

## How a change gets in

1. Branch from `main`, change your module.
2. `python scripts/score_dev.py` before and after. Paste both tables in the PR.
3. Keep it only if `deg_mean` improves by more than the seed spread and `clean` doesn't drop.
4. One line in `experiments/LOG.md`: date, who, what, before → after.
5. CI green (tests + data guard), one review, squash-merge.

Parameter changes go through `scripts/sweep.py` on the dev set, never by hand-tuning to a number.

## Calendar

| day | goal |
|---|---|
| **Wed 11** | everyone: clone, `make setup`, `make dev` reproduces the table in README. Lead: `make submission` on the real data, confirm it validates |
| **Thu 12 – Sat 14** | parallel workstreams. Merge to `main` daily so integration never piles up. Submission instructions arrive by the 14th — lead reads them the same day |
| **Sun 15** | feature freeze at 20:00 CET. Joint re-sweep of all parameters on the dev set |
| **Mon 16** | final file. #5 regenerates it from a **fresh clone on a different laptop** and checks the sha256 matches. Finish the doc. Make the repo public after a last `scripts/check_no_data.sh all` |
| **Tue 17** | validate the exact file, upload `<team>.csv` + `<team>.pdf` by 12:00 CET. Every member double-checks they registered under the identical team name |
