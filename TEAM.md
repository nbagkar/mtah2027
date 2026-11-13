# Team playbook — More than a Hack 2027, Phase 1

Deadline **Tue Nov 17, 23:59 CET** (17:59 New York). We submit by **Tue 12:00 CET** and keep the rest of
the day as buffer. Scored on `spellF1` on the private full match; floor to beat is 0.2433.

## Non-negotiables (each one can disqualify us)

The organisers' clarification email (received 2026-11-11) overrides everything else, including
the challenge repo's docs. These rules follow it.

1. **No match data in git, ever.** The repo goes public at submission and history is forever.
   Run `scripts/install_hooks.sh` once after cloning; CI runs the same check on every push.
2. **No match data in any AI service.** That covers ChatGPT, Claude, Gemini, Copilot chat and any
   other hosted model, and the videos, tracking, tagging, homography and *any extract* of them.
   Code, error messages and our own pass/fail results are fine. Rows, frames, screenshots and
   plots of the match are not. When you ask an AI for help, paste the code, not the data.
3. **Every tuned or trained number comes from external data only.** Fitting, calibrating or
   tuning on the possession ground truth (public 5 minutes included) or on the video is banned.
   So is "training" on the competition match in any form. Parameters are chosen by
   `scripts/sweep.py` / `scripts/score_dev.py` on the dev set (other games), full stop.
4. **Never check our output against the video.** Watching the video and inspecting the data to
   understand *what counts as possession* is allowed. Putting our labels next to the footage to
   see where we're wrong is not, and neither is any frame-specific constant ("the second half
   kicks off at frame N"). Detect such things with code.
5. **No hand labels or human-made data about the match**, from us or anyone else (event data,
   corrected tracking, annotations).
6. **Only datasets we have the rights to use.** The dev set is Metrica's public sample data; its
   README asks for responsible use and acknowledgement, which the technical document gives.
7. **The final file must regenerate byte-for-byte from the repo.** Pinned deps, no randomness
   without a fixed seed, sha256 recorded in `experiments/LOG.md`.

Allowed, per the same email: automatic checks that use only the provided data (e.g. "does the
file validate", "are frames aligned"); the video, tracking, smart tagging and homography as
*inputs*; and publishing intermediate files.

**Asking doesn't help.** On Nov 13 the organisers answered our three questions by restating the
clarification email, adding: "anything that is not explicitly allowed is not permitted." So:

- **Never compute statistics on the provided tracking to set anything**, including the dev set's
  noise model. It isn't explicitly allowed. We hedge instead: every change must hold up on both
  kinds of dev copy and across the jitter stress tests (`experiments/LOG.md`).
- **Metrica's sample data is fine**: "any dataset you have the rights to use" is explicitly
  allowed, and its README asks only for responsible use and acknowledgement, which
  `docs/technical_document.md` gives.
- **Smart Tagging is an explicitly allowed input**, but any parameter on it would have to be tuned
  on external data, and our external games have none. Only parameter-free rules, and only with
  the whole team's agreement.

If an idea isn't clearly covered by the allowed list above, don't build it.

## Roles

Each owns one module, so five people can work at once without merge conflicts. Owners review PRs
that touch their file.

| # | role | owns | first things to try |
|---|---|---|---|
| 1 | **Lead / integration** | `possession/pipeline.py`, `configs/`, `scripts/make_submission.py`, the form | run v0 on the real data today; sanity-check alignment; own the final file, the Google account upload, the reproducibility check |
| 2 | **Dead ball** | `possession/deadball.py` | Smart Tagging SET PIECES as restart anchors; restart geometry (ball still on a line/corner/centre spot); kickoff detection; ball out of bounds from the homography |
| 3 | **Possessor** | `possession/possessor.py`, `possession/features.py` | control = same player near the ball for N frames; pass detection (ball leaves team T, arrives at team T); team shape when the ball is missing (41% of frames); Smart Tagging team phases as a prior |
| 4 | **Segmenter** | `possession/segment.py` | minimum-duration / semi-Markov decoding; separate costs for H↔A vs via D; when to write `X` (free inside a possession, costly at a hand-over — see EVALUATION.md) |
| 5 | **Validation + write-up** | `devset/`, `docs/technical_document.md` | bootstrap intervals on the robust score; own the technical document; Monday's fresh-clone reproducibility check. (Calibrating the dev noise to the real ATD is ruled out, see above.) |

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
