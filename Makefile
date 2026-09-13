# Makefile for crack-spread-study.
#
# make is not installed on every machine, notably a stock Windows box. Every
# target below is a single command you can paste into a shell instead, and the
# help target prints those commands. Recipes use tabs, POSIX sh.
#
# Targets are added as the phase gates in SPEC.md section 10 are approved. At
# Gate 1 the data layer exists and nothing else does, so a target that would
# only pretend to work is not listed here. Notably absent, and deliberately:
# build, fixtures and the engine parity validator, which belong to Gate 2, and
# anything that writes a site facing JSON artifact, which SPEC.md section 10
# forbids before the data and the engine are approved.

.DEFAULT_GOAL := help
.PHONY: help data data-offline data-jobs note test validate gate serve

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
	@echo "  make test          run the python test suite"
	@echo "                     equivalent: python -m pytest tests"
	@echo "  make validate      run the node validators, no network, no python"
	@echo "                     equivalent: node tools/validate-data.mjs"
	@echo "                                 node tools/check-dashes.mjs"
	@echo "  make gate          the deploy gate: everything that must pass before a change lands"
	@echo "                     equivalent: python scripts/refresh.py --offline"
	@echo "                                 python -m pytest tests"
	@echo "                                 node tools/validate-data.mjs"
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

# The python suite. Fast, offline, and the inner loop while you work.
test:
	python -m pytest tests

# The node validators. Plain node, no npm install. They read the committed files
# in a different language from the one that wrote them, which is the point:
# a number both sides produce independently is a fact rather than a claim.
validate:
	node tools/validate-data.mjs
	node tools/check-dashes.mjs

# The deploy gate, SPEC.md non negotiable 7. Four commands, in this order,
# none of which touches the network. Today it is the WHOLE gate, because it is
# the only gate: .github/workflows/ is empty and there is no CI. SPEC.md non
# negotiable 7 says the CI gate is the deploy gate and SPEC.md section 10 puts
# both workflows at Gate 5, so until Gate 5 builds them this target is what
# stands in their place and running it is a manual step, not an automatic one.
#
# ONE STEP IS MISSING HERE AND BELONGS IN THE WORKFLOW WHEN IT IS WRITTEN:
# git diff --exit-code data/manifest.json after the offline refresh, to catch a
# committed manifest that does not describe the committed caches. It only means
# anything on a clean checkout, so it is not run over your working tree.
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
	node tools/check-dashes.mjs

# The site is served from a subpath on GitHub Pages, so open
# http://localhost:8000/ and check that every asset path is relative. There is
# no site yet: SPEC.md section 10 puts it behind Gate 4.
serve:
	python -m http.server 8000
