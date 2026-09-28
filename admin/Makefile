# One way to do each thing, so none of it lives in anybody's memory.
#
# The service itself uses the standard library and nothing else, so it starts
# on a machine with no network and inside the package build. Checking it needs
# flake8 and pytest, which are not on the Pi: README.md says where to get them
# and how to point PYTHON at them.

PYTHON ?= python3

.PHONY: help run test lint check kit web clean

help:
	@echo 'run    start the service in the foreground'
	@echo 'test   run the test suite'
	@echo 'lint   check style and obvious mistakes'
	@echo 'check  lint and test, which is what a commit needs'
	@echo 'kit    put interface/nextstep.css and interface/nextstep.js back together'
	@echo 'web    build what the browser gets, out of interface/'

# The kit is generated from ../design/kit/, one source per component, into the
# interface beside everything else it is built from. Edit a component there and
# run this, then `make web`; the test suite fails when either has drifted.
kit:
	$(PYTHON) ../design/build.py

# What ships: one script, one stylesheet and a markup with no comments in it,
# out of interface/. Needs esbuild, which the Pi never does, because what this
# writes is committed.
web:
	$(PYTHON) build_web.py

run:
	$(PYTHON) -m previously

test:
	$(PYTHON) -m pytest tests -q

lint:
	$(PYTHON) -m flake8 --max-line-length=100 previously tests build_web.py

check: lint test

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
