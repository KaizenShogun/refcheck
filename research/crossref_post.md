I hit this from the consuming end and went looking for how widespread it is, so
here is a count and a list, in case it helps size CR-2746.

**Method.** Paged the REST API with a cursor over every `update-type` that
returns anything — retraction, correction, erratum, corrigendum, expression of
concern, withdrawal, removal, partial retraction — with `select=DOI,update-to`,
grouped each work's assertions by `(source, record-id)`, and flagged any group
holding more than one distinct `type`. Assertions without a `record-id` are
skipped: without one there is no evidence two entries share an origin, and a work
can legitimately be corrected and later retracted.

**Result, 2026-09-09: 417,618 update records scanned, 6 works affected.** All six
are `source: retraction-watch`. Then I settled each one against the current
[Retraction Watch CSV](https://gitlab.com/crossref/retraction-watch-data), which
holds one row per record id, so the leftover half is identifiable:

| work | record-id | the API serves | CSV `RetractionNature` | leftover |
|---|---|---|---|---|
| 10.1148/85.3.474 | 19937 | retraction · expression_of_concern | Expression of concern | `retraction` |
| 10.1109/bibe.2018.00052 | 45015 | retraction · expression_of_concern | Expression of concern | `retraction` |
| 10.1051/ocl/2024009 | 63890 | retraction · expression_of_concern | Expression of concern | `retraction` |
| 10.1007/s12275-015-0740-4 | 37343 | retraction · correction | Correction | `retraction` |
| 10.1038/s41598-022-06705-7 | 37754 | retraction · correction | Correction | `retraction` |
| 10.3892/etm.2024.12720 | 69356 | retraction · `68818` | Retraction | `68818` |

Six in 417,618 is rare, which seems worth knowing when prioritising. In all five
genuine cases the leftover is the `retraction`, which is also the loudest one.

**The last row looks like a different bug.** On 10.3892/etm.2024.12720, record
69356 carries a second assertion whose `type` **and** `label` are both the literal
string `68818`:

```json
{ "DOI": "10.3892/etm.2018.6349", "type": "68818", "label": "68818",
  "source": "retraction-watch", "record-id": "69356",
  "updated": { "date-time": "2024-09-18T00:00:00Z" } }
```

`68818` is itself a Retraction Watch record id — a live one, a retraction of a
different paper (10.3892/etm.2017.5600). So a record id from one record appears
to have landed in the type field of another. The CSV side looks clean: across
72,431 rows it holds exactly five distinct `RetractionNature` values (Retraction,
Expression of concern, Correction, Reinstatement, and blank), and record 69356's
is plain `Retraction`. Happy to open that as its own topic if you would rather
keep this one on the duplicate-assertion behaviour.

**Why the duplicates bite downstream.** Both assertions carry the same
`record-id`, the same `source` and the same timestamp, so a consumer reading only
the API has nothing to order them by. The obvious implementation — take the most
severe — then reports a paper as retracted when the current upstream state is an
expression of concern. My own reference checker did exactly that on
10.1148/85.3.474 until this measurement made me look, and telling somebody to drop
a citation that was never retracted is a worse failure than saying nothing. Once
CR-2746 lands and stale halves stop being served, that guesswork goes away for
everyone reading the API.

The script is here if it is useful as a regression check afterwards — standard
library only, no key, and `--csv` does the arbitration in the table above:
https://github.com/KaizenShogun/refcheck/blob/main/research/measure_conflicts.py

Thanks for publishing the data in the first place. It is easy to forget that
being able to run this query at all is not the normal state of affairs.
