# Makefile for crack-spread-study.
#
# make is not installed on every machine, notably a stock Windows box. Every
# target below is a single command you can paste into a shell instead, and the
# help target prints those commands. Recipes use tabs, POSIX sh.
#
# Targets are added as the phase gates in SPEC.md section 10 are approved. Gates
# 1 to 3 built the data layer, the engine and the analysis. Gate 4 adds build and
# build-check, which write and check the site facing JSON artifacts in data/,
# and the four site checks in validate and gate.

.DEFAULT_GOAL := help
.PHONY: help data data-offline data-jobs note fixtures build build-check test validate gate serve layout screenshots

help:
	@echo "targets"
	@echo "  make data          refresh every source into data/cache and rewrite data/manifest.json"
	@echo "                     equivalent: python scripts/refresh.py"
	@echo "  make data-offline  revalidate the committed caches and rewrite the manifest, no network"
	@echo "                     equivalent: python scripts/refresh.py --offline"
	@echo "  make data-jobs     list the refresh jobs and the series each one owns, run nothing"
	@echo "                     equivalent: python scripts/refresh.py --list"
	@echo "  make note          collect this week's DGEC note before the ministry deletes it"
	@echo "                     equivalent: python scripts/note.py"
	@echo "  make fixtures      re-export the engine parity fixture from src/crack/engine.py"
	@echo "                     equivalent: python scripts/gen_fixtures.py"
	@echo "  make build         write the site facing artifacts data/*.json from the committed caches"
	@echo "                     equivalent: python scripts/export.py"
	@echo "  make build-check   rebuild the artifacts in memory, write nothing, fail if one is stale"
	@echo "                     equivalent: python scripts/export.py --check"
	@echo "  make test          the python suite, then the python to javascript parity check"
	@echo "                     equivalent: python -m pytest tests"
	@echo "                                 node tools/validate-engine.mjs"
	@echo "  make validate      run the node validators, no network, no python"
	@echo "                     equivalent: node tools/validate-data.mjs"
	@echo "                                 node tools/validate-engine.mjs"
	@echo "                                 node tools/validate-artifacts.mjs"
	@echo "                                 node tools/check-literals.mjs"
	@echo "                                 node tools/check-paths.mjs"
	@echo "                                 node tools/check-styles.mjs"
	@echo "                                 node tools/validate-format.mjs"
	@echo "                                 node tools/check-dashes.mjs"
	@echo "  make gate          the deploy gate: everything that must pass before a change lands"
	@echo "                     equivalent: python scripts/refresh.py --offline"
	@echo "                                 python -m pytest tests"
	@echo "                                 node tools/validate-data.mjs"
	@echo "                                 node tools/validate-engine.mjs"
	@echo "                                 python scripts/export.py --check"
	@echo "                                 node tools/validate-artifacts.mjs"
	@echo "                                 node tools/check-literals.mjs"
	@echo "                                 node tools/check-paths.mjs"
	@echo "                                 node tools/check-styles.mjs"
	@echo "                                 node tools/validate-format.mjs"
	@echo "                                 node tools/check-dashes.mjs"
	@echo "  make serve         serve the site at its Pages subpath, http://localhost:8000/crack-spread-study/"
	@echo "                     equivalent: python scripts/serve.py --port 8000"
	@echo "  make layout        measure the Now and History views in headless Chromium, needs make serve running"
	@echo "                     equivalent: node tools/check-layout.mjs --base http://localhost:8000/crack-spread-study/"
	@echo "  make screenshots   full page PNGs of Now and History into assets/, needs make serve running"
	@echo "                     equivalent: node scripts/screenshots.mjs --base http://localhost:8000/crack-spread-study/"

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
#
# scripts/note.py puts src on the path and runs crack.sources.dgec_note with
# --collect. The target used to call `python -m crack.sources.dgec_note
# --collect` directly, which fails on a fresh clone with "No module named
# crack": only pytest puts src on the path, and nothing is installed. After it,
# run make data-offline and make build, then read the diff.
note:
	python scripts/note.py

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

# Write the site facing JSON artifacts, SPEC.md sections 2 rule 2 and 8, from
# the committed caches through crack.series and crack.analysis. SPEC.md section
# 5.4: make build never fetches, and nothing under it opens a socket.
#
# Five files, one per concern: now, cracks, margin-stack, run-economics and
# provenance. An artifact whose bytes did not change is not rewritten.
#
# Then the content hashes in index.html, src/crack/versions.py: an import map
# giving every module in src/ and every artifact in data/ a ?v= of its sha256,
# and the same on the stylesheets and the entry module. Pages serves every file
# with a short max age, so without them a deploy can pair yesterday's module
# with today's artifact; with them, a changed file gets a new URL. What a query
# string cannot do is covered in src/state.js, which refuses an artifact whose
# schema_version or name it does not know and says so by file name.
#
# BYTE IDEMPOTENT. No artifact carries a generation timestamp, floats are
# rounded to six places, the threshold bootstrap has a fixed seed, and text is
# ASCII with LF. Building twice on an unchanged tree leaves it clean.
#
# ONE HONEST LIMIT. Utilisation divides by the Energy Institute capacity table,
# which lives in data/private because its terms forbid committing it. A fresh
# clone cannot run this target or build-check. Gate 5 has to decide how the
# workflow gets that file or what it checks instead; until then both targets
# run only on a machine that holds data/private.
build:
	python scripts/export.py

# Rebuild every artifact in memory and compare bytes with the committed file,
# and recompute the content hashes in index.html. Writes nothing. Exits 1 naming
# each stale artifact and each file whose hash index.html no longer matches, so a change to a cache,
# the engine or the analysis that was never rebuilt fails the gate rather than
# shipping a page that disagrees with the model. About ten seconds, most of it
# the two 2,000 replication threshold bootstraps.
build-check:
	python scripts/export.py --check

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
#
# The four site checks, added at Gate 4, read the frontend rather than the data:
#   check-literals   SPEC.md section 2 rule 2: no number in src/ or index.html
#                    that no artifact supplied, outside a commented allowlist
#   check-paths      every path relative, nothing from another host, so the
#                    /crack-spread-study/ subpath cannot break
#   check-styles     the CSS docs/design.md Part 5 bans, and mono only on
#                    figures and ticks
#   validate-format  src/format.js, router.js and state.js under plain node, and
#                    the verdict read back through format.js
validate:
	node tools/validate-data.mjs
	node tools/validate-engine.mjs
	node tools/validate-artifacts.mjs
	node tools/check-literals.mjs
	node tools/check-paths.mjs
	node tools/check-styles.mjs
	node tools/validate-format.mjs
	node tools/check-dashes.mjs

# The deploy gate, SPEC.md non negotiable 7. Eleven commands, in this order,
# none of which touches the network. Today it is the WHOLE gate, because it is
# the only gate: .github/workflows/ is empty and there is no CI. SPEC.md non
# negotiable 7 says the CI gate is the deploy gate and SPEC.md section 10 puts
# both workflows at Gate 5, so until Gate 5 builds them this target is what
# stands in their place and running it is a manual step, not an automatic one.
#
# The order is the order in which a failure is cheapest to read. The offline
# refresh first, because a broken cache makes everything after it lie. Then
# pytest, which is where a Python change fails. Then the data validator, then
# the parity validator, which is where a JavaScript change fails. Then the
# artifacts: build-check first, because a stale artifact would make the artifact
# validator pass on numbers that no longer describe the caches, then the
# validator, which reads them in JavaScript. Then the four site checks, which
# read src/, styles/ and index.html: literals, paths, styles, then the format
# validator, which also reads the verdict in now.json back through format.js.
# Dashes last: it is the only one that never depends on a number.
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
	python scripts/export.py --check
	node tools/validate-artifacts.mjs
	node tools/check-literals.mjs
	node tools/check-paths.mjs
	node tools/check-styles.mjs
	node tools/validate-format.mjs
	node tools/check-dashes.mjs

# The site is served from a subpath on GitHub Pages. scripts/serve.py mounts
# the repository at /crack-spread-study/ and answers 404 everywhere else, so a
# root relative path fails here as it would on Pages. Open
# http://localhost:8000/crack-spread-study/
serve:
	python scripts/serve.py --port 8000

# The two browser tools. Neither is in the gate, because the gate runs with no
# browser and no server; both need `make serve` running in another shell, and
# any Chromium (Edge, Chrome, Chromium), found by tools/browser.mjs: --browser
# <path>, else the CRACK_BROWSER environment variable, else the usual install
# paths. Each run uses a fresh browser profile, because ES modules are cached
# hard and a reused profile can measure a module graph no longer on disk.
#
#   layout        tools/check-layout.mjs. The findings of the Gate 4 audit that
#                 only a rendered page shows, one check each: sticky columns,
#                 clipped captions, off screen columns the caption must name,
#                 clipped focus rings, Provenance prose, marks through labels,
#                 words in the figure face, page overflow, console errors. Five
#                 widths, both themes, every section open. About three minutes.
#   screenshots   scripts/screenshots.mjs. Whole page PNGs, every pixel of the
#                 height, desktop 1440 and mobile 375, light and dark, closed
#                 and open, into assets/. Prints each file's size and any
#                 console error. Point --base at the live subpath for Gate 5.
layout:
	node tools/check-layout.mjs --base http://localhost:8000/crack-spread-study/

screenshots:
	node scripts/screenshots.mjs --base http://localhost:8000/crack-spread-study/
