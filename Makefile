# Makefile for crack-spread-study.
#
# make is not installed on every machine, notably a stock Windows box. Every
# target below is a single command you can paste into a shell instead, and the
# help target prints those commands. Recipes use tabs, POSIX sh.
#
# Targets are added as the phase gates in SPEC.md section 10 are approved. At
# Gate 2 the data layer and the engine exist. Still absent, and deliberately:
# build, and anything that writes a site facing JSON artifact, which SPEC.md
# section 10 forbids before the data and the engine are approved. There is no
# site to build yet.

.DEFAULT_GOAL := help
.PHONY: help data data-offline data-jobs note fixtures test validate gate serve

help:
	@echo "targets"
	@echo "  make data          refresh every source into data/cache and rewrite data/manifest.json"
	@echo "                     equivalent: python scripts/refresh.py"
	@echo "  make data-offline  revalidate the committed caches and rewrite the manifest, no network"
	@echo "                     equivalent: python scripts/refresh.py --offline"
	@echo "  make data-jobs     list the refresh jobs and the series each one owns, run nothing"
	@echo "                     equivalent: python scripts/refresh.py --list"
	@echo "  make note          collect this week's DGEC note before the ministry deletes it"
	@echo "                     equivalent: python -m crack.sources.dgec_note --collect"
	@echo "  make fixtures      re-export the engine parity fixture from src/crack/engine.py"
	@echo "                     equivalent: python scripts/gen_fixtures.py"
	@echo "  make test          the python suite, then the python to javascript parity check"
	@echo "                     equivalent: python -m pytest tests"
	@echo "                                 node tools/validate-engine.mjs"
	@echo "  make validate      run the node validators, no network, no python"
	@echo "                     equivalent: node tools/validate-data.mjs"
	@echo "                                 node tools/validate-engine.mjs"
	@echo "                                 node tools/check-dashes.mjs"
	@echo "  make gate          the deploy gate: everything that must pass before a change lands"
	@echo "                     equivalent: python scripts/refresh.py --offline"
	@echo "                                 python -m pytest tests"
	@echo "                                 node tools/validate-data.mjs"
	@echo "                                 node tools/validate-engine.mjs"
	@echo "                                 node tools/check-dashes.mjs"
	@echo "  make serve         serve the repo root over http on port 8000"
	@echo "                     equivalent: python -m http.server 8000"

# Fetches from the network. Keeps the previous cache on any failure, and exits
# non zero if any series ends up failed. SPEC.md section 5.4.
#
# It does not close the two gaps a machine cannot close. Six OPEC MOMR issues,
# April to September 2026, are not in the Internet Archive, and the DGEC weekly
# note has to be collected in the week it is published because the ministry
# deletes it. Both are recorded as manual_steps in data/manifest.json and both
# are printed at the end of every run.
data:
	python scripts/refresh.py

# Never fetches. Reads the committed caches, measures them again in Python, and
# rewrites the manifest from what it measured. This is the one a workflow should
# run when there is one, so that a third party outage cannot turn this
# repository red. SPEC.md section 10 puts both workflows at Gate 5 and
# .github/workflows/ is empty today.
#
# BYTE IDEMPOTENT. Running it on an unchanged tree leaves data/manifest.json
# byte identical, which is what makes "git diff --exit-code data/" after it a
# real check rather than a timestamp generator.
data-offline:
	python scripts/refresh.py --offline

# Prints the jobs, the series each one owns and which of them may not be
# committed. Touches nothing.
data-jobs:
	python scripts/refresh.py --list

# THE ONE THING IN THIS PROJECT THAT CANNOT WAIT. The ministry publishes one
# weekly note at a time and deletes the previous one when the next appears.
# There is no archive. A week that is missed is gone for good, and with it two
# calibration anchors for the chart reconstruction. Two requests. Run it weekly.
note:
	python -m crack.sources.dgec_note --collect

# Re-export data/fixtures/engine-cases.json from src/crack/engine.py. The
# fixture is COMMITTED, not built at gate time, so that an engine change shows
# up as a diff in the cases it moved, which a reviewer can read.
#
# Run this after any change to src/crack/engine.py, then read the diff. If the
# diff is bigger than the change you made, the change was bigger than you
# thought. If there is no diff, you changed a docstring.
#
# BYTE IDEMPOTENT. Regenerating an unchanged engine leaves the working tree
# clean: every draw comes from random.Random(20260913) in a fixed order, the
# file records the seed, and it is written as ASCII with LF endings on every
# platform. tests/test_fixtures.py asserts all of that, and
# `python scripts/gen_fixtures.py --check` makes the claim in one command
# without writing anything.
fixtures:
	python scripts/gen_fixtures.py

# The python suite, then the parity check. SPEC.md section 7.1 puts the parity
# validator in `make test` by name, so it is here and not only in the gate:
# the engine exists twice and the inner loop has to be able to see them drift.
#
# The two halves catch different things and you need both.
#   pytest              includes tests/test_fixtures.py, which rebuilds the
#                       fixture from src/crack/engine.py and compares bytes. A
#                       Python engine change that was never re-exported fails
#                       HERE, in python, because node cannot see engine.py at
#                       all and would go on comparing engine.js against a
#                       Python that no longer exists.
#   validate-engine     runs src/engine.js over the same fixture and asserts
#                       agreement to 1e-9 on every line. A JavaScript change
#                       fails here.
# If they disagree, SPEC.md section 7.1 says fix the JavaScript to match Python,
# never the reverse.
test:
	python -m pytest tests
	node tools/validate-engine.mjs

# The node validators. Plain node, no npm install. They read the committed files
# in a different language from the one that wrote them, which is the point:
# a number both sides produce independently is a fact rather than a claim.
#
# validate-engine.mjs prints a measurement every run under "measured
# difference": the largest gap between what python recorded and what
# javascript computed, and where it was. It should read zero. It is printed
# rather than asserted at zero because floating point sums are not obliged to
# be bit identical across two languages, so a check demanding that could only
# ever be red. The bar that IS asserted, and that fails this target, is
# SPEC.md section 7.1's 1e-9. Read the measurement anyway: drift shows up there
# many orders of magnitude before it reaches the bar.
validate:
	node tools/validate-data.mjs
	node tools/validate-engine.mjs
	node tools/check-dashes.mjs

# The deploy gate, SPEC.md non negotiable 7. Five commands, in this order,
# none of which touches the network. Today it is the WHOLE gate, because it is
# the only gate: .github/workflows/ is empty and there is no CI. SPEC.md non
# negotiable 7 says the CI gate is the deploy gate and SPEC.md section 10 puts
# both workflows at Gate 5, so until Gate 5 builds them this target is what
# stands in their place and running it is a manual step, not an automatic one.
#
# The order is the order in which a failure is cheapest to read. The offline
# refresh first, because a broken cache makes everything after it lie. Then
# pytest, which is where a Python change fails. Then the data validator, then
# the parity validator, which is where a JavaScript change fails. Dashes last:
# it is the only one that never depends on a number.
#
# TWO STEPS ARE MISSING HERE AND BOTH BELONG IN THE WORKFLOW WHEN IT IS
# WRITTEN. Both are `git diff --exit-code` and both only mean anything on a
# clean checkout, which is why neither is run over your working tree:
#   git diff --exit-code data/manifest.json
#       after the offline refresh, to catch a committed manifest that does not
#       describe the committed caches.
#   python scripts/gen_fixtures.py && git diff --exit-code data/fixtures/
#       to catch a committed parity fixture that is not what the committed
#       engine produces. tests/test_fixtures.py already asserts this inside
#       pytest, by rebuilding and comparing bytes without writing, so the gate
#       is not blind to it today. The workflow version is the belt to that
#       braces, and it is the one that would also catch a fixture edited by
#       hand in a way that happened to match.
#
# The gate does assert values, not only shapes: tests/test_cache_values.py holds
# a committed digest of every committed cache plus the SPEC.md section 5.5
# anchors read out of data/seed/anchors.json, so a silent one digit edit to any
# cache fails this target. When you change a cache on purpose, regenerate the
# digests with: python tests/cache_digests.py --write
gate:
	python scripts/refresh.py --offline
	python -m pytest tests
	node tools/validate-data.mjs
	node tools/validate-engine.mjs
	node tools/check-dashes.mjs

# The site is served from a subpath on GitHub Pages, so open
# http://localhost:8000/ and check that every asset path is relative. There is
# no site yet: SPEC.md section 10 puts it behind Gate 4.
serve:
	python -m http.server 8000
