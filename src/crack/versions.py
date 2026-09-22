"""Content hashes in index.html, so a deploy changes every URL whose bytes changed.

WHY. GitHub Pages serves every file with a short max age and no version in its
name. The site is an ES module graph plus data/*.json, all fetched by plain
relative URLs, so after a deploy a browser or the CDN in front of Pages can hand
the page a MIXED set: yesterday's src/section-cracks.js with today's
data/cracks.json. An old module reading a new artifact can print a wrong number
without any error. The main session's own preview served a stale module graph
for hours.

WHAT, with no build step and no bundler. `make build` rewrites three things in
index.html and nothing else, each from the bytes on disk:

  1  an import map between the markers BLOCK_START and BLOCK_END, mapping every
     module under src/ and every artifact under data/ to the same path with
     ?v=<the first HASH_LENGTH hex digits of its sha256>. Every relative import
     between modules resolves through the map, so a module whose bytes changed
     gets a new URL even when the module importing it did not change. The
     artifacts are in the same map because src/state.js asks for them through
     import.meta.resolve, which applies it.
  2  the ?v= on each stylesheet link to styles/*.css.
  3  the ?v= on the entry module, src/ui.js, which a script tag loads directly
     and the import map does not reach.

index.html itself carries no version: it is the one file that names all the
others, and a stale copy of it names a consistent old set.

WHAT IT DOES NOT DO, and the guard that covers it. A query string changes the
URL a cache keys on; it does not choose which bytes the server holds, because
Pages ignores the query. A visitor holding an index.html from before a deploy,
whose cache has since dropped an old file, fetches today's bytes under
yesterday's URL. src/state.js therefore refuses any artifact whose
schema_version or artifact name it does not know and says so by file name,
rather than drawing it.

BYTE IDEMPOTENT. The map is sorted, written with LF and no timestamp; a second
build over an unchanged tree rewrites nothing. `make build-check` recomputes it
and fails naming each entry that is stale.

THE HASH IS OF THE BYTES ON DISK, AND THAT IS A TRAP ON WINDOWS. .gitattributes
declares "* text=auto eol=lf", so every tracked text file is stored and checked
out with LF, and the bytes a Linux runner or a fresh clone holds are LF bytes. A
tool that writes src/engine.js through a Python or Node text stream on Windows
writes CRLF instead. git status stays clean, because the clean filter normalises
CRLF back to LF before comparing, so nothing anywhere says a word; but the hash
`make build` writes into index.html is then the hash of bytes that exist only on
that one machine, and `make build-check` fails in CI on a tree the author was
told was green. It happened here: src/engine.js was committed at Gate 5 with a
CRLF working copy and index.html carried d4dd59c29a28 where a clean checkout
hashes deb06799ec27. crlf_entries below is the guard, and export.py --check
calls it, so the condition is caught by the same command that checks the hashes
rather than by a runner three commits later.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX = "index.html"

#: Hex digits of the sha256 kept in a URL. Twelve is 48 bits: a collision
#: between two versions of one file would leave a stale URL, and at 48 bits
#: that is not a risk a site of this size meets.
HASH_LENGTH = 12

BLOCK_START = "<!-- build:versions, written by make build from the bytes on disk; do not edit by hand -->"
BLOCK_END = "<!-- /build:versions -->"

#: What is versioned, as (directory, suffix). Top level of each directory only:
#: src/crack is the Python package and never reaches the browser.
MODULE_DIRECTORY = ("src", ".js")
ARTIFACT_DIRECTORY = ("data", ".json")
STYLE_DIRECTORY = ("styles", ".css")
ENTRY_MODULE = "src/ui.js"


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:HASH_LENGTH]


def _files(root: Path, directory: str, suffix: str) -> list[str]:
    folder = root / directory
    if not folder.is_dir():
        return []
    return sorted(
        "%s/%s" % (directory, path.name)
        for path in folder.iterdir()
        if path.is_file() and path.name.endswith(suffix)
    )


def hashes(root: Path = REPO_ROOT) -> dict[str, str]:
    """Every versioned file, by its path relative to index.html, to its hash."""
    out: dict[str, str] = {}
    for directory, suffix in (MODULE_DIRECTORY, ARTIFACT_DIRECTORY, STYLE_DIRECTORY):
        for relative in _files(root, directory, suffix):
            out[relative] = content_hash((root / relative).read_bytes())
    return out


def crlf_entries(root: Path = REPO_ROOT) -> list[str]:
    """Each versioned file whose bytes on disk carry a CRLF. Empty when clean.

    A versioned file is one whose sha256 goes into index.html, so a CRLF in it is
    not a style question: it is a hash that a checkout of the same commit cannot
    reproduce. See the module docstring for the incident this exists to stop
    happening twice. The fix is always to rewrite the file with LF and re-run
    `make build`, never to relax the check.
    """
    return [
        relative
        for relative in sorted(hashes(root))
        if b"\r\n" in (root / relative).read_bytes()
    ]


def versioned(relative: str, digest: str) -> str:
    return "%s?v=%s" % (relative, digest)


def import_map(table: Mapping[str, str]) -> str:
    """The import map block, markers included, for the modules and artifacts."""
    imports = {
        "./" + relative: "./" + versioned(relative, digest)
        for relative, digest in sorted(table.items())
        if relative.startswith(MODULE_DIRECTORY[0] + "/") or relative.startswith(ARTIFACT_DIRECTORY[0] + "/")
    }
    body = json.dumps({"imports": imports}, indent=2, ensure_ascii=True, sort_keys=True)
    return "\n".join([BLOCK_START, '<script type="importmap">', body, "</script>", BLOCK_END])


_BLOCK = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.S)
_STYLE_LINK = re.compile(r'href="(styles/[\w.-]+\.css)(?:\?v=[0-9a-f]*)?"')
_ENTRY = re.compile(r'src="(' + re.escape(ENTRY_MODULE) + r')(?:\?v=[0-9a-f]*)?"')


class VersionsError(ValueError):
    """index.html has no place to write the versions into."""


def render(html: str, table: Mapping[str, str]) -> str:
    """index.html with the import map, the stylesheet links and the entry module
    carrying the hashes in `table`. Raises VersionsError when a marker, the entry
    module or a stylesheet named in the table has nowhere to go, so a hand edit
    that removed one fails the build instead of shipping unversioned URLs."""
    if html.count(BLOCK_START) != 1 or html.count(BLOCK_END) != 1:
        raise VersionsError(
            "%s must hold the markers %r and %r exactly once each" % (INDEX, BLOCK_START, BLOCK_END)
        )
    out = _BLOCK.sub(lambda _: import_map(table), html)

    def style(match: re.Match) -> str:
        relative = match.group(1)
        if relative not in table:
            raise VersionsError("%s links %s, which does not exist" % (INDEX, relative))
        return 'href="%s"' % versioned(relative, table[relative])

    out = _STYLE_LINK.sub(style, out)
    if len(_ENTRY.findall(out)) != 1:
        raise VersionsError("%s must load %s exactly once" % (INDEX, ENTRY_MODULE))
    out = _ENTRY.sub(lambda m: 'src="%s"' % versioned(m.group(1), table[m.group(1)]), out)
    return out


def expected_index(root: Path = REPO_ROOT) -> str:
    return render((root / INDEX).read_bytes().decode("utf-8"), hashes(root))


def write(root: Path = REPO_ROOT) -> bool:
    """Rewrite index.html if its versions are stale. Returns True when written."""
    path = root / INDEX
    current = path.read_bytes()
    wanted = expected_index(root).encode("utf-8")
    if current == wanted:
        return False
    path.write_bytes(wanted)
    return True


def stale_entries(root: Path = REPO_ROOT) -> list[str]:
    """Each versioned path whose hash in index.html is not its bytes' hash, or
    that index.html does not version at all. Empty when index.html is fresh."""
    html = (root / INDEX).read_bytes().decode("utf-8")
    try:
        wanted = render(html, hashes(root))
    except VersionsError as exc:
        return [str(exc)]
    if wanted == html:
        return []
    out = []
    for relative, digest in hashes(root).items():
        if versioned(relative, digest) not in html:
            out.append(relative)
    return out or ["index.html differs from its rebuild outside the versioned URLs"]
