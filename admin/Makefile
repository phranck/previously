# One way to do each thing, so none of it lives in anybody's memory.
#
# The service itself uses the standard library and nothing else, so it starts
# on a machine with no network and inside the package build. Checking it needs
# flake8 and pytest, which are not on the Pi: README.md says where to get them
# and how to point PYTHON at them.

PYTHON ?= python3

.PHONY: help run test lint check kit clean

help:
	@echo 'run    start the service in the foreground'
	@echo 'test   run the test suite'
	@echo 'lint   check style and obvious mistakes'
	@echo 'check  lint and test, which is what a commit needs'
	@echo 'kit    put web/nextstep.css and web/nextstep.js back together'

# The two files the browser gets are generated from ../design/kit/, one source
# per component. Edit a component there and run this; the test suite fails when
# the two have drifted from it.
kit:
	$(PYTHON) ../design/build.py

run:
	$(PYTHON) -m previously

test:
	$(PYTHON) -m pytest tests -q

lint:
	$(PYTHON) -m flake8 --max-line-length=100 previously tests

check: lint test

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
