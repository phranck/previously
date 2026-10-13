# One way to do each thing, so none of it lives in anybody's memory.
#
# The service itself uses the standard library and nothing else, so it starts
# on a machine with no network and inside the package build. Checking it needs
# flake8 and pytest, which are not on the Pi: README.md says where to get them
# and how to point PYTHON at them.

PYTHON ?= python3
OXLINT ?= node_modules/.bin/oxlint
TSC ?= node_modules/.bin/tsc

.PHONY: help run test test-dom browser lint lint-service lint-interface types check kit web clean

help:
	@echo 'run      start the service in the foreground'
	@echo 'test     run the test suite: the service, and the kit and the page against a DOM'
	@echo 'browser  run what only a browser can show, in Safari Technology Preview'
	@echo 'lint     check both halves: flake8 on the service, oxlint and tsc on the interface'
	@echo 'check    lint and test, which is what a commit needs'
	@echo 'kit      put interface/nextstep.css and interface/nextstep.js back together'
	@echo 'web      build what the browser gets, out of interface/'

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

test: test-dom
	$(PYTHON) -m pytest tests -q

# The kit's elements and the page's own modules, run in Node against happy-dom
# with the kit's own stylesheet on the page. What a part does to the markup it
# is given, and what the page does with an answer, without a browser anybody
# has to drive. `npm install` puts happy-dom here.
test-dom:
	node --test tests/kit/*.test.js tests/page/*.test.js

# What only a browser laying the page out can show, such as a scroller's knob
# against what there is to scroll. Safari Technology Preview through its own
# safaridriver, against the real service in a temporary home. Not part of
# `check`, because it drives a browser. Run it when the kit's behavior changes.
browser:
	$(PYTHON) -m pytest browser -q

lint: lint-service lint-interface types

lint-service:
	$(PYTHON) -m flake8 --max-line-length=100 previously tests browser build_web.py

# The other half of this repository, which flake8 cannot see, by the rules in
# .oxlintrc.json. `no-undef` is what matters most, because the interface is
# modules: a name that is not imported bundles without a word and fails when
# somebody presses the thing that needs it. A warning fails it as well, so a
# rule turned down to one is still a rule. `npm install` puts Oxlint here.
lint-interface:
	$(OXLINT) --deny-warnings interface tests/kit tests/page

# And what the documentation comments say, read as types. The interface stays
# JavaScript: this compiles nothing and writes nothing, it only reads what is
# already written down beside each function and holds the code to it, the
# kit's included, under the strict rules.
types:
	$(TSC) -p tsconfig.json

check: lint test

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
