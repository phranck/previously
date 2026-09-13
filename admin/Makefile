# One way to do each thing, so none of it lives in anybody's memory.
#
# Everything here runs with what Debian ships: python3, python3-pytest and
# python3-flake8. Nothing is fetched, so it all works on a machine with no
# network and inside the package build.

PYTHON ?= python3

.PHONY: help run test lint check clean

help:
	@echo 'run    start the service in the foreground'
	@echo 'test   run the test suite'
	@echo 'lint   check style and obvious mistakes'
	@echo 'check  lint and test, which is what a commit needs'

run:
	$(PYTHON) -m nextstep_admin

test:
	$(PYTHON) -m pytest tests -q

lint:
	$(PYTHON) -m flake8 --max-line-length=100 nextstep_admin tests

check: lint test

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
