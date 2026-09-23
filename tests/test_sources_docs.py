"""Every citation in a published document resolves to something a reader can use.

GATE 5 FINDING 5. `docs/methodology.md` and `docs/open-questions.md` cite
"recon 02 section 4.3", "recon 03 section 2.3", "recon 05 section 12" and about
thirty others as the authority for constants and measurements. The five
reconnaissance reports those citations name are this study's own, written before
Gate 1, and they are not in the repository: recon 03 reproduces the Energy
Institute capacity table, which carries ICIS and S&P Global data and may not be
redistributed, so committing the report would publish the table the report
itself says not to publish (docs/sources.md sections 2.7 and 6).

They are therefore cited the way this study cites any document it may not
redistribute: the reader is told what the document is, what it covers, and which
public primary source to fetch instead. `docs/sources.md` section 6 is that
register, and these tests fail if a report is cited and not in it, or if a row
of it stops naming where to go.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = REPO_ROOT / "docs" / "sources.md"
REGISTER_HEADING = "## 6. The Gate 1 reconnaissance reports, and what to read instead"

#: "recon 03", "Recon 3", "recon 05 section 12".
CITATION = re.compile(r"\brecon[ _-]?(\d{1,2})\b", re.IGNORECASE)
#: A row of the register: | recon 03, physical | date | scope | where to go |
REGISTER_ROW = re.compile(r"^\|\s*recon (\d{2}), ([^|]+?)\s*\|(.+)$", re.IGNORECASE)


def _register() -> dict[int, list[str]]:
    text = SOURCES.read_text(encoding="utf-8")
    assert REGISTER_HEADING in text, "docs/sources.md has lost its recon register"
    section = text.split(REGISTER_HEADING, 1)[1]
    rows = {}
    for line in section.splitlines():
        match = REGISTER_ROW.match(line.strip())
        if match:
            rows[int(match.group(1))] = [cell.strip() for cell in match.group(3).split("|") if cell.strip()]
    return rows


def _cited_in() -> dict[int, set[str]]:
    where: dict[int, set[str]] = {}
    files = sorted((REPO_ROOT / "docs").glob("*.md"))
    files += sorted((REPO_ROOT / "src").rglob("*.py"))
    files += [REPO_ROOT / "README.md"]
    for path in files:
        if path.name == "sources.md":
            continue
        for match in CITATION.finditer(path.read_text(encoding="utf-8")):
            where.setdefault(int(match.group(1)), set()).add(str(path.relative_to(REPO_ROOT)))
    return where


def test_the_register_lists_the_five_reports_with_somewhere_to_go():
    register = _register()
    assert sorted(register) == [1, 2, 3, 4, 5], register
    for number, cells in register.items():
        # date, scope, and where a reader goes instead: three cells, each said.
        assert len(cells) >= 3, (number, cells)
        assert all(cells), (number, cells)


def test_every_recon_a_published_document_cites_is_in_the_register():
    register = _register()
    problems = []
    for number, files in sorted(_cited_in().items()):
        if number not in register:
            problems.append("recon %02d is cited in %s and is not in docs/sources.md section 6" % (number, ", ".join(sorted(files))))
    assert problems == [], "\n".join(problems)


def test_the_two_documents_that_cite_a_recon_say_what_one_is():
    """A reader who meets "recon 03 section 2.3" in the middle of a document
    should not have to go looking for what that is."""
    for name in ("methodology.md", "open-questions.md"):
        text = (REPO_ROOT / "docs" / name).read_text(encoding="utf-8")
        if not CITATION.search(text):
            continue
        head = text[:4000]
        assert 'What "recon NN" means' in head, name
        assert "data/private/recon/" in head, name
        assert "docs/sources.md` section 6" in head, name


def test_no_reconnaissance_report_is_committed():
    """The register's whole reason. If one is ever added to the repository, this
    fails and the licence question in docs/sources.md section 6 has to be
    answered again rather than passed by accident."""
    private = REPO_ROOT / "data" / "private" / "recon"
    if not private.exists():
        return
    committed = [p for p in (REPO_ROOT / "docs").rglob("*.md") if p.name.startswith(("01-", "02-", "03-", "04-", "05-"))]
    assert committed == [], committed
