PYTHON ?= python3

.PHONY: test

test:
	$(PYTHON) tests/test_rtk_codex_hook.py
