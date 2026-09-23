"""Every published count of the reconstruction's weakest weeks, against the cache.

THE FINDING THIS FILE EXISTS FOR. The Gate 5 self audit found `README.md` saying
that "1 of its 221 weeks has no independent cross check at all" while
`data/cache/dgec_note_reconstructed_weekly.csv` said seven, in the section the
README tells a reader to read first and whose whole purpose is to be harder on
the study than anyone else will be. The count had been true once: it moves every
time a note is collected, `docs/methodology.md` section 1.12 says so in as many
words, and the site already counts it from the frame at build time. Prose in the
repository did not.

So this file reads the committed cache, counts the weeks, and then reads the
published documents and refuses any statement of the count that disagrees. It is
deliberately about the FILES A READER OPENS, not about the export: the artifacts
are covered by tests/test_export.py, which compares them with the same frame.

HOW A DATED SENTENCE IS ALLOWED TO KEEP ITS OLD NUMBERS. Three of these
documents describe the series as it stood at an earlier gate, on purpose, and
deleting that history would be worse than keeping it. A sentence is exempt when
it carries one of DATED_MARKERS, which are the phrases those documents use to
say "this was then". A sentence with no such marker is read as a claim about the
series today and has to agree with the cache.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = REPO_ROOT / "data" / "cache" / "dgec_note_reconstructed_weekly.csv"

#: The published files that state the count in prose. The site's own copies are
#: written from the frame by crack.export and are checked in tests/test_export.py.
PUBLISHED = (
    "README.md",
    "docs/methodology.md",
    "docs/design.md",
    "docs/open-questions.md",
)

#: A sentence that says "this was the count at an earlier vintage" rather than
#: "this is the count". Kept short and literal so that a new stale sentence
#: cannot slip through by accident: nobody writes one of these by mistake.
DATED_MARKERS = (
    "before the collection",
    "at gate 4 they read",
    "when this question was written",
    "them then and one of them now",
    "recon 05 section 12",
    "the count is right",
    "it moves nineteen of the twenty five",
)

#: "7 of 221", "7 of its 221 weeks", "214 of 221 weeks", "25 of 219".
PAIR = re.compile(r"\b(\d+)\s+of\s+(?:its\s+|the\s+)?(\d+)\b")

#: A sentence about cross checking rather than about anything else counted here.
ABOUT_CROSS_CHECK = re.compile(
    r"cross check|cross checked|uncorroborated|independent geometr", re.IGNORECASE
)


@pytest.fixture(scope="module")
def counted() -> dict[str, int]:
    """The counts, read from the committed cache rather than from anybody's prose."""
    frame = pd.read_csv(CACHE)
    checked = frame["cross_checked"].astype(str).str.strip().str.lower() == "true"
    single = frame[~checked]
    return {
        "weeks": int(len(frame)),
        "uncorroborated": int(len(single)),
        "cross_checked": int(checked.sum()),
        "oldest": int((frame["evidence_class"] == "single_geometry_oldest").sum()),
        "newest": int((frame["evidence_class"] == "single_geometry_newest").sum()),
    }


def _sentences(text: str):
    """Rough sentences: enough to hold one claim and its dated marker, if any.

    Markdown, so a table row is a sentence too: the methodology's summary table
    states the count in a cell, and a cell split on full stops alone would lose
    the row it belongs to.
    """
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            yield line
            continue
        for part in re.split(r"(?<=[.:])\s+", line):
            if part.strip():
                yield part


def test_the_cache_still_has_seven_uncorroborated_weeks(counted):
    """The measurement the Gate 5 audit made, asserted rather than remembered.

    If a collection moves these, this is the first test to fail and the failure
    message is the new count, which is the number every published sentence then
    has to carry.
    """
    assert counted["weeks"] == 221
    assert counted["uncorroborated"] == 7
    assert counted["cross_checked"] == 214
    assert counted["oldest"] == 6
    assert counted["newest"] == 1
    assert counted["oldest"] + counted["newest"] == counted["uncorroborated"]


@pytest.mark.parametrize("name", PUBLISHED)
def test_no_published_document_understates_the_uncorroborated_weeks(name, counted):
    """Any undated "N of M" in a cross checking sentence must be the cache's.

    The pair is read both ways round because both are published: "7 of 221" have
    no cross check and "214 of 221" have one. Anything else, in a sentence that
    does not declare itself historical, is a stale count on a page a reader is
    asked to trust.
    """
    text = (REPO_ROOT / name).read_text(encoding="utf-8")
    allowed = {
        (counted["uncorroborated"], counted["weeks"]),
        (counted["cross_checked"], counted["weeks"]),
        (counted["oldest"], counted["uncorroborated"]),
        (counted["oldest"], counted["weeks"]),
    }
    wrong = []
    for sentence in _sentences(text):
        if not ABOUT_CROSS_CHECK.search(sentence):
            continue
        lowered = sentence.lower()
        if any(marker in lowered for marker in DATED_MARKERS):
            continue
        for match in PAIR.finditer(sentence):
            pair = (int(match.group(1)), int(match.group(2)))
            # Only pairs whose larger half is the week count are claims about
            # this series; "0.17 to 0.44" and the like are not pairs at all, and
            # a "1 of 4" about products is not about weeks.
            if pair[1] not in (counted["weeks"], counted["uncorroborated"]):
                continue
            if pair not in allowed:
                wrong.append(sentence.strip())
    assert not wrong, (
        "%s states a week count that data/cache/dgec_note_reconstructed_weekly.csv "
        "does not support. The cache says %d of %d weeks have no independent cross "
        "check, %d have one, and %d of the uncorroborated seven are the oldest. "
        "Stale sentences:\n  %s"
        % (
            name,
            counted["uncorroborated"],
            counted["weeks"],
            counted["cross_checked"],
            counted["oldest"],
            "\n  ".join(wrong),
        )
    )


def test_the_readme_says_the_measured_figure_in_the_section_it_opens_with(counted):
    """The exact sentence the Gate 5 audit found wrong, now pinned to the cache.

    Not a regex over the whole file: this asserts that the pessimistic bullet in
    "What the study cannot do" carries the count, the six oldest weeks and their
    first date. A rewrite that drops any of the three fails here, which is the
    point, because the six are what the count is for.
    """
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    cannot = text.split("## What the study cannot do", 1)
    assert len(cannot) == 2, "the README no longer has a 'What the study cannot do' section"
    # Markdown wraps, so the claim is read with its line breaks flattened: the
    # sentence this pins is three lines long in the file.
    body = " ".join(cannot[1].split("\n## ", 1)[0].split())
    claim = [s for s in _sentences(body) if "no independent cross check" in s]
    assert claim, "the README no longer says how many weeks have no independent cross check"
    said = " ".join(claim)
    assert "%d of its %d weeks" % (counted["uncorroborated"], counted["weeks"]) in said
    assert "1 July" in body and "5 August 2022" in body
    assert "least defended" in body
