PY ?= .venv/bin/python
TEAM ?= BAP PM&T

setup:
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt
	git submodule update --init
	bash scripts/install_hooks.sh

dev:
	$(PY) devset/build.py
	$(PY) -W ignore scripts/score_dev.py

baseline:
	$(PY) -W ignore scripts/baseline_dev.py

bootstrap:
	$(PY) -W ignore scripts/bootstrap_dev.py

sweep:
	$(PY) -W ignore scripts/sweep.py

test:
	$(PY) -W ignore -m pytest -q

submission:
	$(PY) -W ignore scripts/make_submission.py --team '$(TEAM)'

guard:
	bash scripts/check_no_data.sh all

# The technical document as a PDF named after the team, for the submission form. Uses its own
# venv so the pinned pipeline environment is untouched. Needs Google Chrome for printing.
pdf:
	test -d .venv-pdf || (python3 -m venv .venv-pdf && .venv-pdf/bin/pip install -q markdown-it-py==3.0.0)
	.venv-pdf/bin/python scripts/build_pdf.py docs/technical_document.md 'submissions/$(TEAM).pdf'

.PHONY: setup dev baseline bootstrap sweep test submission guard pdf
