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

sweep:
	$(PY) -W ignore scripts/sweep.py

test:
	$(PY) -W ignore -m pytest -q

submission:
	$(PY) -W ignore scripts/make_submission.py --team '$(TEAM)'

guard:
	bash scripts/check_no_data.sh all

.PHONY: setup dev baseline sweep test submission guard
