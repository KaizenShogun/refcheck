# Draft: no update-type for a reversed retraction

**Status: WRITTEN, NOT SENT (2026-09-16).**

Not sent because ticket **647180** is open with a reply promised and I have not
been able to read the inbox yet. Writing again before reading what someone has
already written back is rude and risks repeating a point they have answered. This
goes as a follow-up on that thread once it is read — or, if the thread stays
silent, as a separate note, because it is a different kind of problem: CR-2746 is
an ingestion bug, this is a **missing field**.

Prior art checked 2026-09-16, both of their own venues:

- `CrossRef/rest-api-doc` issues, `reinstate` / `reinstatement` — **0 results**,
  open and closed.
- `community.crossref.org/search.json?q=reinstate` — 2 topics, neither on this
  ("Unauthorized web deposit form", "Doi not working").

So the request does not exist anywhere of theirs. Nobody is being interrupted.

The vocabulary claim is verified against the authoritative source rather than
from memory: `data.crossref.org/schemas/common5.3.1.xsd` enumerates exactly
twelve `update-type` values and `reinstatement` is not among them. (It also
confirms refcheck's own severity table is complete against the schema — all
twelve are handled, none invented.)

---

## Draft

Subject: No `update-type` for a reinstated paper — 31 reversed retractions served as retractions

Hello,

A separate issue from the one in ticket 647180, and a smaller one. It is not an
ingestion bug; it is a vocabulary gap.

When a retraction is **reversed** — the journal got it wrong, or the authors were
cleared — there is no `update-type` a publisher can deposit to say so. The
enumeration in `common5.3.1.xsd` has twelve values — `addendum`,
`clarification`, `correction`, `corrigendum`, `erratum`,
`expression_of_concern`, `new_edition`, `new_version`, `partial_retraction`,
`removal`, `retraction`, `withdrawal` — and none of them undoes another.

The effect is that the API keeps serving the retraction, alone, indefinitely.

**Measured, as a census rather than a sample.** The Retraction Watch CSV you
republish carries `RetractionNature = Reinstatement`. There are 160 such rows,
155 with a usable original DOI, so I checked all of them rather than sampling:

| | n | |
|---|---:|---|
| no notice served | 105 | 67.7% |
| a milder notice only | 19 | often a real notice published after the reinstatement |
| **still served as a retraction** | **31** | **20.0%** |

Those 31 papers stand today. Their notes in your own republished CSV say so
plainly — "Retracted in error and reinstated", "This article was incorrectly
retracted and was reinstated in October 2016", "article reinstated on unknown
date with no explanation". Eleven of the 31 are `Retract and Replace`, where a
superseded version genuinely existed; the rest were simply restored.

**Where the information goes instead.** Taylor & Francis reinstated nine papers
in *Bioengineered* in 2024 and published a notice for each — all nine are in the
31. They are deposited as ordinary
`journal-article` records titled "Publisher's Note", with `update-to: null` and
no relation to the paper they restore. For example
`10.1080/21655979.2021.2005742` is still served with a single `updated-by`
retraction from 2024-02-01, while `10.1080/21655979.2024.2326361` — the notice
reinstating it — is linked to nothing. I do not think that is the publisher being
careless: with no update-type for a reversal, a plain article is the only place
left to put it.

One case shows it resolving correctly and why that does not help much:
`10.1007/s00404-012-2548-3` now carries a 2024 `correction` and Crossref has
dropped the retraction — but PubMed still lists it, so any checker asking both
registers still reports the paper retracted.

**Why it matters beyond one tool.** Anything built on `updated-by` inherits this,
and telling a reader to discard a citation that was never withdrawn is the
costliest thing such a tool can do — worse than missing a notice, because the
reader acts on it. Tools reading the Retraction Watch database directly (Zotero)
are fine; tools reading your API are not.

I am not asking for a turnaround, and I realise a vocabulary addition is a schema
change rather than a bug fix. Mostly I wanted the 31 on record with the method
attached, in case it is useful when the list is next revised.

Method and the full census, MIT and no key needed:
https://github.com/KaizenShogun/refcheck — `research/measure_rw_gap.py --nature
Reinstatement --all`, and the per-DOI results in
`research/rw_reinstatement_20260916.json`.

Thanks,
Midas
