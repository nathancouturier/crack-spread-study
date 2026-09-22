"""The content hashes in index.html, src/crack/versions.py.

What a stale map would cost: after a deploy a cache can pair yesterday's module
with today's artifact, and the page can print a wrong number with no error. So
the tests assert the committed index.html names the current hash of every file
the browser loads, that a build twice writes the same bytes, and, by planting a
change in a copy of the site, that the check names the stale file and that
`make build-check` fails on it.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from crack import export, versions

REPO_ROOT = Path(__file__).resolve().parents[1]


def _import_map(html: str) -> dict[str, str]:
    match = re.search(r'<script type="importmap">\s*(\{.*?\})\s*</script>', html, re.S)
    assert match, "index.html holds no import map"
    return json.loads(match.group(1))["imports"]


def _site_copy(tmp_path: Path) -> Path:
    """index.html, src/*.js, styles/*.css and data/*.json, nothing else."""
    root = tmp_path / "site"
    (root / "src").mkdir(parents=True)
    (root / "styles").mkdir()
    (root / "data").mkdir()
    shutil.copy2(REPO_ROOT / "index.html", root / "index.html")
    for directory, pattern in (("src", "*.js"), ("styles", "*.css"), ("data", "*.json")):
        for path in (REPO_ROOT / directory).glob(pattern):
            shutil.copy2(path, root / directory / path.name)
    return root


def test_the_committed_index_names_the_current_hash_of_every_file():
    assert versions.stale_entries(REPO_ROOT) == [], (
        "index.html names a stale hash. Run: make build"
    )


def test_every_module_and_artifact_is_in_the_map_with_the_hash_of_its_bytes():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    imports = _import_map(html)
    modules = sorted(p.name for p in (REPO_ROOT / "src").glob("*.js"))
    artifacts = sorted(p.name for p in (REPO_ROOT / "data").glob("*.json"))
    assert modules and artifacts
    expected = ["./src/%s" % name for name in modules] + ["./data/%s" % name for name in artifacts]
    assert sorted(imports) == sorted(expected)
    for key, target in imports.items():
        relative = key[len("./"):]
        digest = hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest()[: versions.HASH_LENGTH]
        assert target == "./%s?v=%s" % (relative, digest), key


def test_the_stylesheets_and_the_entry_module_carry_their_hashes():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    table = versions.hashes(REPO_ROOT)
    for sheet in sorted(p.name for p in (REPO_ROOT / "styles").glob("*.css")):
        relative = "styles/%s" % sheet
        assert 'href="%s"' % versions.versioned(relative, table[relative]) in html, relative
    assert 'src="%s"' % versions.versioned("src/ui.js", table["src/ui.js"]) in html
    # The import map precedes the first module script, or the browser ignores it.
    assert html.index('type="importmap"') < html.index('type="module"')


def test_rendering_is_byte_idempotent():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    table = versions.hashes(REPO_ROOT)
    once = versions.render(html, table)
    assert versions.render(once, table) == once


def test_a_planted_module_change_is_named_and_a_build_repairs_it(tmp_path):
    root = _site_copy(tmp_path)
    assert versions.stale_entries(root) == []
    module = root / "src" / "format.js"
    module.write_bytes(module.read_bytes() + b"\n// a change that a deploy must not cache\n")
    assert versions.stale_entries(root) == ["src/format.js"]
    assert versions.write(root) is True
    assert versions.stale_entries(root) == []
    assert versions.write(root) is False, "a second build over an unchanged tree rewrote index.html"


def test_a_planted_artifact_and_stylesheet_change_are_named(tmp_path):
    root = _site_copy(tmp_path)
    artifact = root / "data" / "now.json"
    artifact.write_bytes(artifact.read_bytes().replace(b'"schema_version": 1', b'"schema_version": 2', 1))
    sheet = root / "styles" / "layout.css"
    sheet.write_bytes(sheet.read_bytes() + b"\n/* changed */\n")
    assert versions.stale_entries(root) == ["data/now.json", "styles/layout.css"]


def test_a_hand_edit_that_removes_the_markers_fails_rather_than_shipping_unversioned(tmp_path):
    root = _site_copy(tmp_path)
    index = root / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace(versions.BLOCK_END, ""), encoding="utf-8")
    with pytest.raises(versions.VersionsError):
        versions.write(root)
    assert versions.stale_entries(root) and "markers" in versions.stale_entries(root)[0]


def test_build_check_fails_on_a_stale_map(monkeypatch, capsys):
    """make build-check is export.check on data/: a stale map alone fails it."""
    monkeypatch.setattr(export, "build", lambda inputs=None: {})
    monkeypatch.setattr(versions, "stale_entries", lambda root: ["src/format.js"])
    monkeypatch.setattr(versions, "crlf_entries", lambda root: [])
    assert export.check(export.DATA) == 1
    out = capsys.readouterr().out
    assert "index.html version of src/format.js" in out
    assert "make build" in out


# ---------------------------------------------------------------------------
# Line endings, because a CRLF here is a hash a clean checkout cannot reproduce
# ---------------------------------------------------------------------------
#
# .gitattributes declares "* text=auto eol=lf", so every tracked text file is
# stored and checked out with LF. A tool that writes one of these files through a
# text stream on Windows writes CRLF, git status stays clean because the clean
# filter normalises it away, and the hash `make build` puts in index.html is then
# the hash of bytes that exist on one machine only. That is exactly what happened
# to src/engine.js before this commit: index.html carried d4dd59c29a28 and a
# fresh clone of the same commit hashes deb06799ec27, so build-check would have
# failed on the first CI run of a tree the author had been told was green.


def test_no_versioned_file_carries_crlf():
    assert versions.crlf_entries(REPO_ROOT) == [], (
        "a versioned file is stored with LF by .gitattributes, so a CRLF copy on "
        "disk hashes to bytes no checkout reproduces. Rewrite it with LF and run: "
        "make build"
    )


def test_a_planted_crlf_is_named_and_build_check_fails_on_it(tmp_path, monkeypatch, capsys):
    root = _site_copy(tmp_path)
    assert versions.crlf_entries(root) == []
    module = root / "src" / "format.js"
    module.write_bytes(module.read_bytes().replace(b"\n", b"\r\n"))
    assert versions.crlf_entries(root) == ["src/format.js"]

    monkeypatch.setattr(export, "build", lambda inputs=None: {})
    monkeypatch.setattr(versions, "stale_entries", lambda root: [])
    monkeypatch.setattr(versions, "crlf_entries", lambda root: ["src/engine.js"])
    assert export.check(export.DATA) == 1
    out = capsys.readouterr().out
    assert "CRLF     src/engine.js" in out
    assert "make build" in out
