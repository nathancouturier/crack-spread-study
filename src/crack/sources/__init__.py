"""One module per data source, plus the contract they all sit on.

    base.py     paths, http, validation, cache, manifest, the Adapter class

Adapters are added by later gates. Nothing is re exported here on purpose: an
adapter is imported by name, so a traceback and a grep both say which source
was involved.
"""

from __future__ import annotations

__all__: list[str] = []
