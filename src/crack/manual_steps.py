"""The work this pipeline cannot do for itself, and the code that records it.

SPEC.md section 5.3 makes the manifest a first class artifact and the provenance
panel renders it. Two pieces of work in this project are done by a human, and
both of them silently degrade the data if they are forgotten, so they are written
into the manifest rather than into a README nobody opens.

WHY THIS IS A MODULE OF ITS OWN, AND NOT PART OF scripts/refresh.py
--------------------------------------------------------------------
It used to live in scripts/refresh.py, which attached it to every entry at the
end of a run. That was right for refresh and wrong for everything else, because
refresh is not the only thing that writes the manifest. `make note` runs
crack.sources.dgec_note, which writes four entries of its own, and it replaced
them WITHOUT the manual_step field, so between `make note` and the next
`make data-offline` the manifest no longer recorded the weekly collection duty
and `node tools/validate-data.mjs` rejected the tree:

    FAIL  the manual steps are recorded and attached to the series they affect
          manual step dgec_weekly_note_collection names dgec_note_printed_weekly
          but that entry does not carry it

Nothing was lost if the documented order was followed. That is not the standard:
a collector must not leave the repository in a state its own validator rejects,
and the scheduled workflow runs the collector unattended. So the steps moved
here, apply() is pure, and crack.sources.base.manifest_upsert calls it on every
write. One command now leaves a valid tree, whichever command it is.

apply() is idempotent: attaching the same steps to the same payload twice gives
the same bytes, which is what scripts/refresh.py's offline byte idempotence
depends on.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = ["MANUAL_STEPS", "MANUAL_STEPS_NOTE", "steps_by_series", "apply"]


#: Two of them, both real, both discovered rather than assumed, and both with a
#: cost stated in words.
MANUAL_STEPS: tuple[dict[str, Any], ...] = (
    {
        "id": "momr_unarchived_2026",
        "series": ["opec_rotterdam_products_monthly"],
        "what": (
            "Six OPEC Monthly Oil Market Report issues, April to September 2026, are not in "
            "the Internet Archive and cannot be fetched by this pipeline."
        ),
        "why": (
            "opec.org answers HTTP 403 to every scripted request from this machine, recon 05 "
            "section 1.1, so the adapter resolves issues through the Wayback Machine instead. "
            "The archive holds every issue from January 2001 to March 2026 and stops there. "
            "Nothing in this repository can close that gap on its own."
        ),
        "cost_if_skipped": (
            "The headline monthly crack series ends at 2026-02 and the whole 2026 episode, "
            "which is the most interesting period in the sample, is missing from it. The "
            "weekly DGEC reconstruction covers 2026 and the official monthly MBR covers it, "
            "so the study is not blind, but its longest crack series is."
        ),
        "how": (
            "Open each issue in a browser from https://www.opec.org/monthly-oil-market-report.html "
            ", save the PDF into data/private/momr/ under the name the index expects, then run "
            "python -m crack.sources.opec_momr to reparse. The PDFs are never committed, only "
            "the parsed values are."
        ),
        "cadence": "monthly, or once when the archive catches up",
        "status": "outstanding",
    },
    {
        "id": "dgec_weekly_note_collection",
        "series": [
            "dgec_note_decoded_index",
            "dgec_note_decoded_weekly",
            "dgec_note_decoded_printed",
            "dgec_note_decoded_monthly",
            "dgec_note_printed_weekly",
            "dgec_note_printed_monthly",
            "dgec_note_reconstructed_weekly",
            "dgec_note_reconstructed_cracks_weekly",
        ],
        "what": (
            "The DGEC weekly note has to be downloaded in the week it is published. It is the "
            "only source of the weekly Rotterdam quotations."
        ),
        "why": (
            "The ministry publishes one note at a time and DELETES the previous one when the "
            "next appears, recon 02 section 2.3. There is no archive on the ministry site and "
            "the Internet Archive caught only ten of them. A note that is missed is gone: the "
            "week it prints cannot be recovered from anywhere, at any price, ever."
        ),
        "cost_if_skipped": (
            "A permanent hole in the weekly layer. Every week missed also removes two "
            "calibration anchors from the chart reconstruction, because the reconstruction is "
            "fitted on the printed figures of the same note. Collecting one also restitches "
            "the weeks already published, which is the method working and which the Method "
            "view measures."
        ),
        "how": (
            "make note, or python scripts/note.py, two requests, which saves the note "
            "that is online now into data/private/dgec_notes and then rebuilds the "
            "weekly series. IT IS ON A WEEKLY SCHEDULE: .github/workflows/refresh.yml "
            "runs it first, before every other source, and opens an issue of its own if "
            "it fails. Check that the issue is not sitting unread. The PDF stays "
            "private; what is committed is the decode of it, in the four "
            "dgec_note_decoded_* caches, which is what lets a runner that has only this "
            "week's note restitch the whole four year series."
        ),
        "cadence": "weekly, every week, without exception",
        "status": "standing",
    },
)

MANUAL_STEPS_NOTE = (
    "Work this pipeline cannot do for itself. Each entry says what it is, why it exists, "
    "what it costs to skip it and how to do it. They are repeated against the series they "
    "affect in the manual_step field of those entries."
)


def steps_by_series() -> dict[str, list[dict]]:
    """series name -> the steps that affect it, each without its series list."""
    out: dict[str, list[dict]] = {}
    for step in MANUAL_STEPS:
        for name in step["series"]:
            out.setdefault(name, []).append(
                {k: v for k, v in step.items() if k != "series"}
            )
    return out


def apply(payload: dict) -> dict:
    """Attach the manual steps to a manifest payload, in place. Idempotent.

    A series named by a step gets that step in manual_step; a series named by
    none has the field REMOVED rather than left behind, so a step that stops
    applying stops being printed instead of lingering on the provenance panel.
    """
    by_series = steps_by_series()
    for entry in payload.get("series", []):
        steps = by_series.get(entry.get("series"))
        if steps:
            entry["manual_step"] = steps
        else:
            entry.pop("manual_step", None)
    payload["manual_steps"] = [dict(step) for step in MANUAL_STEPS]
    payload["manual_steps_note"] = MANUAL_STEPS_NOTE
    return payload
