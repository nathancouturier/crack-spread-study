"""Serve the repository at the subpath GitHub Pages uses, and nowhere else.

    python scripts/serve.py              http://localhost:8000/crack-spread-study/
    python scripts/serve.py --port 8123

The site is published at https://nathancouturier.github.io/crack-spread-study/,
a project page under a subpath, never at a domain root. SPEC.md section 0.1
calls a root relative path the most common way this deployment breaks, and a
plain `python -m http.server` run from the repository root cannot show it: there
`/styles/tokens.css` and `styles/tokens.css` resolve to the same file, so the
broken path works on your machine and fails on Pages.

This server reproduces the Pages layout exactly enough to break the same way:

* The repository root is mounted at /crack-spread-study/. Anything outside that
  prefix is a 404, so a root relative src, href, url() or fetch fails locally
  exactly as it would on Pages, and shows in the log as a 404 outside the prefix.
* /crack-spread-study without the trailing slash redirects to the slash, as
  Pages does, because relative paths resolve against the directory.
* data/private/ answers 404. It is gitignored, so it never reaches Pages, and a
  page that reads it locally would pass here and break there. So would any dot
  directory such as .git, which Pages never serves either.
* Directory listings are off: Pages serves index.html or a 404, never a list.

Plain standard library, binds to 127.0.0.1 only, no build step. `make serve`.
"""

from __future__ import annotations

import argparse
import posixpath
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
PREFIX = "/crack-spread-study/"
DEFAULT_PORT = 8000

# Paths under the prefix that GitHub Pages would never serve, because git never
# carries them there. Checked on the decoded path relative to the repository.
NEVER_DEPLOYED = ("data/private/",)

# Windows reads MIME types from the registry, where .js is sometimes text/plain,
# and a browser refuses to run a module served that way. Pinned here.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    "": "application/octet-stream",
}


def relative_under_prefix(raw_path: str) -> str | None:
    """The repository relative path a request names, or None if it is outside
    the prefix or tries to leave the repository."""
    path = unquote(urlsplit(raw_path).path)
    if not path.startswith(PREFIX):
        return None
    rest = path[len(PREFIX):]
    normalised = posixpath.normpath("/" + rest).lstrip("/")
    if normalised in ("", "."):
        return ""
    if normalised.startswith("..") or any(part.startswith(".") for part in normalised.split("/")):
        return None
    for blocked in NEVER_DEPLOYED:
        if (normalised + "/").startswith(blocked):
            return None
    return normalised + ("/" if rest.endswith("/") and normalised else "")


class SubpathHandler(SimpleHTTPRequestHandler):
    extensions_map = CONTENT_TYPES

    def do_GET(self) -> None:  # noqa: N802, the stdlib name
        if self._route():
            super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802, the stdlib name
        if self._route():
            super().do_HEAD()

    def _route(self) -> bool:
        path = urlsplit(self.path).path
        if path == PREFIX.rstrip("/"):
            self.send_response(HTTPStatus.MOVED_PERMANENTLY)
            self.send_header("Location", PREFIX)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False
        relative = relative_under_prefix(self.path)
        if relative is None:
            self.send_error(
                HTTPStatus.NOT_FOUND,
                "Not under " + PREFIX,
                "GitHub Pages serves this site only under " + PREFIX + ". A request for "
                + path + " is a root relative path or a file Pages never receives.",
            )
            return False
        return True

    def translate_path(self, path: str) -> str:
        relative = relative_under_prefix(path)
        if relative is None:
            return str(REPO_ROOT / "__outside_the_prefix__")
        return str(REPO_ROOT / relative)

    def list_directory(self, path):  # type: ignore[override]
        self.send_error(HTTPStatus.NOT_FOUND, "No directory listings", "Pages serves index.html or a 404.")
        return None

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    handler = partial(SubpathHandler, directory=str(REPO_ROOT))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print("serving " + str(REPO_ROOT))
    print("open    http://localhost:" + str(args.port) + PREFIX)
    print("anything outside " + PREFIX + " and anything under data/private/ answers 404, as on Pages")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
