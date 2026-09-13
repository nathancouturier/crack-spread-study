"""crack, the Python side of the NWE crack spread study.

The package is deliberately thin at the top. Everything lives in a module that
says what it owns:

    crack.config            every constant and every source URL, each with the
                            citation next to it, SPEC.md section 4.1
    crack.sources.base      the contract every adapter sits on: paths, http,
                            frame validation, cache read and write, the manifest
    crack.sources.*         one module per source, one fetch each

Nothing is exported from here. Import the module you mean, so a reader of any
call site can see which layer it belongs to.
"""

from __future__ import annotations

__all__: list[str] = []

#: Bumped when the shape of what this package writes into data/ changes, not
#: when a number moves. The site reads data/manifest.json and expects the schema
#: version recorded there, see crack.sources.base.MANIFEST_SCHEMA_VERSION.
__version__ = "0.1.0"
