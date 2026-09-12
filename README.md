# refcheck

**Has anything you cite been quietly corrected?**

Retractions are the famous case, and they are well covered: Zotero warns you,
Retraction Watch keeps the list, and both are free. A retraction is also the
*rarest* kind of change to the scientific record.

I counted the rest against the Crossref API on 2026-09-08:

| change notice | registered | Zotero / Retraction Watch warns you |
|---|---:|:---:|
| retraction | 75,265 | yes |
| **correction** | **213,113** | **no** |
| **erratum** | **116,091** | **no** |
| **expression of concern** | **4,233** | **no** |
| **new edition** | **10,874** | **no** |
| **withdrawal / removal / addendum / clarification / partial retraction** | **6,328** | **no** |

**350,639 change notices — 4.7 times the retractions.** The tools most people
actually have will not mention them: Zotero's own documentation is explicit that
it "only shows actual retractions, not expressions of concern", and Retraction
Watch is, by name and by design, about retractions.

<sub>Two notes against my own figures. Crossref also registers 44,228 `new_version`
records; I leave them out because they are mostly preprint versioning, not a
warning about anything. And this is a snapshot of a register that moves — I first
counted on 2026-09-06 and the retraction row alone rose by 9,291 in two days, so
treat the ratio as the finding, not the digits.</sub>

These are the quiet ones, and they are quiet for a reason: unlike a retraction,
the paper stays valid. Only a number moved. Nobody emails you to say that the
figure you built an argument on was corrected two years after you read it.

**That gap is a reasonable decision, not an oversight, and it is worth saying so.**
When a Zotero developer was asked about showing corrections, the answer was that
"corrections have become so common that this would be a mess" — and inside a
reference manager that sits in your library all year, that is plainly right. A
permanent red flag on a paper whose axis label was fixed would train you to ignore
red flags. But a check you run *deliberately*, once, when you are about to submit,
has the opposite economics: there the noise is the point, because you are the one
deciding what to read. Different shape of tool, not a better one.

`refcheck` reads your bibliography and tells you which references carry a
published change notice, what kind, and where to read it.

## Use it in your browser — nothing to install

**→ [kaizenshogun.github.io/refcheck](https://kaizenshogun.github.io/refcheck/)**

Paste your reference list, press one button. No account, no upload, no terminal.

There is no server behind that page: your text stays in the browser and only the
identifiers found in it are sent — straight from your machine to Crossref and to
NCBI, both of which are asked about every reference. (Until 2026-09-11 only your
PMIDs reached NCBI. That changed when the tool started asking both registers, and
it is better said plainly than left as a tidier old sentence.) Nothing passes
through me. Save the page and it keeps working from your own disk — it is one
HTML file with no dependencies, no cookies and no analytics.

It is built to be usable rather than just claimed to be: every colour pair is
measured at WCAG **AAA** contrast in both light and dark, the focus ring is never
removed, severity is stated in words and not by colour alone, and the whole thing
is driven by a 67-check battery in a real headless browser against the real APIs.

## Use it from the command line

```
python3 refcheck.py refs.bib          # a BibTeX file
python3 refcheck.py dois.txt          # one DOI per line, or a pasted bibliography
python3 refcheck.py pubmed.txt        # PMIDs work too — see below
python3 refcheck.py refs.bib --json   # machine-readable, for pipelines
echo 10.1371/journal.pone.0161231 | python3 refcheck.py -
```

Real output:

```
  5 reference(s) checked · 3 carry a change notice
  1 not found in Crossref (preprints, books, bad DOI) — not checked

  RETRACTED — do not cite this as evidence
    RETRACTED: LRRK2 kinase activity mediates toxic interactions between genet
    10.1016/j.nbd.2012.05.020 (PMID 22668778)
      → Retraction (2012-09-01): https://doi.org/10.1016/j.nbd.2012.05.020
      → Retraction (2025): https://doi.org/10.1016/j.nbd.2025.106930  [per PubMed]
      → Erratum (2025-06-15): https://doi.org/10.1016/j.nbd.2025.106930
      Two of the lines above are the same notice (10.1016/j.nbd.2025.106930),
      filed at different severities. Read it and judge for yourself.

  EXPRESSION OF CONCERN — the journal itself is unsure
    Delta-Like Ligand 4–Notch Blockade and Tumor Radiation Response
    10.1093/jnci/djr419 (PMID 22010178)
      → Expression Of Concern (2024): https://doi.org/10.1093/jnci/djae263  [per PubMed]
      → Erratum (2025): https://doi.org/10.1093/jnci/djae337  [per PubMed]

  CORRECTED — check the number you are quoting is still there
    Virus-Like Nanoparticle Vaccine Confers Protection against Toxoplasma gond
    10.1371/journal.pone.0161231 (PMID 27548677)
      → Correction (2024-03-21): https://doi.org/10.1371/journal.pone.0301214
```

The middle one is the whole point of asking two registers: Crossref's record for
`10.1093/jnci/djr419` is empty, and this tool used to call that reference clean.

Exit codes, so it can gate a CI job — a journal checking submissions, a lab
checking a manuscript before it goes out, a systematic review checking its own
included studies:

| code | meaning |
|---|---|
| `0` | everything checked, nothing found |
| `1` | at least one reference carries a change notice |
| `2` | bad usage, **or a reference that could not be looked up** |

That last one matters. A failed lookup is not a clean reference, so it does not
let the gate go green.

**No installation, no account, no key.** One file, Python 3.9+, standard library
only. Set `REFCHECK_MAILTO=you@example.org` to identify yourself politely to
Crossref and get their faster pool.

References are looked up **40 per request** rather than one at a time. Measured on
20 references: 6.3 s and 20 requests before, 0.3 s and 1 request after — 19× faster
and 20× less traffic aimed at a public service that nobody funds.

And it now runs at the speed Crossref says it may, rather than the speed I
guessed. Read off the response headers on 2026-09-09:

| pool | how you get there | stated limit |
|---|---|---|
| `public-array` | no mailto — the default | **1 request/second** |
| `polite-array` | `REFCHECK_MAILTO` set | 3 requests/second |

refcheck used to pause a flat 0.4 s, which is 2.5 requests a second: two and a
half times over the limit for every user who never set a mailto, which is most
of them. It now reads `x-rate-limit-limit` back off each response and paces
itself to that, starting from the conservative 1/s. I found this by rate-limiting
myself into 429s while measuring something else — the README had been asking you
to be kind to a public service the code was leaning on.

The browser version paces to 1/s too, hardcoded, because Crossref's CORS policy
exposes only the `Link` header and JavaScript cannot read the limit back.

## PMIDs work, and here is exactly how far they get you

Half of biomedicine does not cite by DOI. It cites `PMID: 9500320`, or pastes a
`pubmed.ncbi.nlm.nih.gov/9500320` link, and until now this tool answered that
with "No DOIs found in that file" — which is a useless thing to say to somebody
holding a perfectly good reference list. Paste PMIDs and they now get looked up:

```
$ python3 refcheck.py pubmed.txt
  3 reference(s) checked · 2 carry a change notice
  1 PMID(s) have no DOI in PubMed — nothing to ask Crossref about, so NOT checked
  1 PMID(s) do not exist in PubMed — check the citation

  RETRACTED — do not cite this as evidence
    RETRACTED: Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and p
    10.1016/s0140-6736(97)11096-0 (PMID 9500320)
      → Retraction (2010-02-06): https://doi.org/10.1016/s0140-6736(10)60175-4
```

The reference is named back to you the way *you* cited it, PMID and all, so you
can find the line in your own document. Mixed lists are fine, and a paper cited
twice — once by DOI, once by PMID — is one reference, not two.

**Crossref is indexed by DOI, so a PMID has to be translated first**, through
NCBI's public E-utilities. That translation has a hole in it, and the size of the
hole decides how the tool has to behave, so I measured it instead of guessing:
1,600 random PMIDs across four eras, `research/measure_pmid_doi.py`, run
2026-09-10.

| PMID range | roughly | records that exist | of those, with a DOI |
|---|---|---:|---:|
| 1–5M | pre-1990 | 397 | **48.6%** |
| 5–15M | 1990–2005 | 390 | 59.0% |
| 15–28M | 2005–2017 | 378 | 87.6% |
| 28–40M | 2017–today | 393 | **95.7%** |
| all four | | 1,558 | 72.5% |

So a 2024 paper is nearly always reachable and a 1979 paper is a coin flip. **A
PMID with no DOI is reported as `not checked`, by name, never silently dropped** —
that is the whole reason the number matters. Silence in a tool like this reads as
"clean", and a 1979 paper that nobody checked is not a clean 1979 paper. Same for
a PMID that does not exist in PubMed at all: you are told, because a citation
pointing at nothing is worth knowing about before a reviewer finds it.

NCBI states 3 requests/second without an API key. refcheck starts at 1/s and
looks up 100 PMIDs per request. `--no-pubmed` skips NCBI entirely if you would
rather not talk to them.

## What else is out there

This space is crowded, and I would rather send you to a better tool than keep you
here. I checked before building, missed something, corrected it, and checked
again on 2026-09-08. The honest landscape:

- **[Zotero](https://www.zotero.org/) + [Retraction Watch](https://retractionwatch.com/)** —
  excellent, free, already inside the tool most researchers use. Retractions only.
- **[CiteGuard](https://github.com/lonexreb/cite-guard)** (`pip install retractguard`) —
  OpenAlex-native, and it *does* cover corrections and expressions of concern.
  If you want an institution-scale watchdog with a package behind it, look there
  first. I found it after publishing this, which says more about my search than
  about their work.
- **[RefIntegrity](https://refintegrity.com/)** — free, no login, upload a whole
  `.bib` or `.ris`. Checks against Retraction Watch: retractions.
- **[Scholar Sidekick](https://scholar-sidekick.com/tools/retraction-checker)** —
  free, and it covers "retracted, corrected, or had an expression of concern
  raised". One identifier at a time.
- **[CiteProve](https://citeprove.com/)**, **[ReferenceVerify](https://referenceverify.com/)**,
  **[RetractionCheck](https://retractioncheck.com/)** — batch reference checkers
  aimed mainly at fabricated and mistyped citations, with retraction flagging.
- **[agbarnett/retraction_watch](https://github.com/agbarnett/retraction_watch)** —
  a Shiny app for a BibTeX file. Retractions.
- **scite.ai**, **Proofig RefGuard** — commercial, and they do far more than this.

**The gap this fills, stated narrowly enough to be checkable:** among the free
tools with no login, the ones that take a *whole bibliography* report retractions,
and the one that reports *every kind of change notice* takes one identifier at a
time. This does both at once, and it does it without an account, an install, or a
server that sees your reading list. That is the whole claim — if one of the tools
above already suits you, use it.

## One register was not enough, and here is the size of the hole

Crossref's `updated-by` field only holds what somebody deposited. PubMed keeps
the same information separately, compiled by NLM indexers rather than by the
publisher's pipeline. I assumed the two roughly agreed. They do not.

`research/measure_pubmed_gap.py` samples PubMed by publication type — retracted
articles, erratum notices followed back to the article they correct, expressions
of concern likewise — and asks Crossref about each one. Sampling is stratified
over publication *date*, split down to single days where needed, because NCBI's
history server refuses `retstart` past 9,998: without the split, the sample would
only ever have come from the last three years of deposit practice.

**2026-09-11, 400 records per category.** Of the papers PubMed says carry a
notice, the share Crossref's data would let a DOI-only checker find:

| PubMed says | in the sample | Crossref flags it | Crossref silent | not in Crossref at all |
|---|---:|---:|---:|---:|
| retracted | 394 | **93.7%** | 3.8% | 2.5% |
| expression of concern | 366 | **91.8%** | 8.2% | 0% |
| **corrected / erratum** | 391 | **78.8%** | 21.0% | 0.3% |

And corrections are worse the older the paper: 83.8% for papers from 2020 on,
69.3% for 2015–19, **60.0% for 2010–14**.

**One corrected paper in five used to come back from this tool clean.** So it
now asks both, and prints where each notice came from:

```
  EXPRESSION OF CONCERN — the journal itself is unsure
    Delta-Like Ligand 4–Notch Blockade and Tumor Radiation Response
    10.1093/jnci/djr419 (PMID 22010178)
      → Expression Of Concern (2024): https://doi.org/10.1093/jnci/djae263  [per PubMed]
      → Erratum (2025): https://doi.org/10.1093/jnci/djae337  [per PubMed]
```

That paper has an expression of concern from its own journal and an erratum, and
Crossref's record for it is empty: no `updated-by`, no `update-to`, no
`relation`. Checked by hand on 2026-09-11.

<sub>What this number is not: it measures Crossref's recall **against PubMed**,
not against the truth, and only inside biomedicine, because that is all PubMed
covers. The honest claim is "the union beats either alone", not "now it is
complete". For a while it also did not know the size of PubMed's own holes —
that is the next section.</sub>

### And the mirror: what PubMed alone would miss

A tool that asks two registers should know the shape of both blind spots, or
"we ask PubMed too" is a claim rather than a measured improvement. So
`research/measure_crossref_gap.py` runs the same measurement backwards: take the
change notices Crossref holds, follow each one back to the article it is about,
and ask PubMed whether it says anything. Sampling is Crossref's own `sample=`,
which draws at random from the filtered set — the price is that it takes no
seed, so every sampled DOI is written to `--json` and a run can be audited even
though it cannot be repeated exactly.

**2026-09-12, 400 articles per category:**

| Crossref says | not in PubMed at all | PubMed says the same | different kind | **PubMed silent** |
|---|---:|---:|---:|---:|
| retraction | 44.5% | 94.6% | 0.5% | **5.0%** |
| expression of concern | 26.8% | 92.8% | 3.8% | **3.4%** |
| correction | 39.5% | 92.1% | 0.8% | **7.0%** |
| **erratum** | 46.2% | 79.5% | 5.1% | **15.3%** |

The last three columns are shares of the articles PubMed actually holds. The
first column is not a failure: PubMed indexes biomedicine and nothing else, so a
correction on a paper about concrete or Kant is simply outside its remit. It is
still the reason the practical figure is blunt — **asking PubMed alone would
have missed between 29% and 55% of what Crossref knows**, and most of that is
scope, not error.

**Errata are the weak spot of both registers, in both directions.** Crossref is
silent for 21% of the ones PubMed knows; PubMed is silent for 15% of the ones
Crossref knows, inside its own subject area. Of every kind of change notice, the
one nobody warns you about is also the one neither register holds reliably.

Neither register is a superset of the other, which is the whole case for asking
both — and it is now measured in both directions rather than assumed in one.

**When the two disagree, you are told rather than picked for.** On the 1998
Lancet paper, notice `10.1016/s0140-6736(04)15715-2` is a *correction* to
Crossref and a *retraction* to PubMed. Both lines are printed with their source.
Merging is keyed on (severity, notice DOI), so `correction` and `erratum` — one
word in two vocabularies — collapse into one line, while a genuine severity
disagreement never silently loses the graver verdict.

`--no-pubmed` turns all of this off, along with PMID translation, if you would
rather not talk to NCBI.

## Who this is for

Anyone whose argument rests on somebody else's numbers: people writing a thesis,
a systematic review, a clinical guideline, a policy brief, a fact-check. You do
not need to be a programmer to run it — you need a file with your references in
it and one command.

## What this is NOT

- **Not a verdict on the science.** A correction usually means a typo, a wrong
  unit, a mislabelled axis. Most corrected papers are perfectly good papers. The
  tool tells you *something changed*; reading what changed is your job.
- **Not a retraction database.** It carries no list of its own. It asks
  [Crossref](https://www.crossref.org/) — which now also includes the Retraction
  Watch data — and [PubMed](https://pubmed.ncbi.nlm.nih.gov/), and shows you the
  answer. All credit for the data is theirs.
- **Not complete.** Two registers beat one; two registers are still not all of
  them. Anything that never got a DOI is invisible to both — including 51% of
  pre-1990 PubMed records, measured above — and preprints, books and chapters are
  frequently outside the checked set. PubMed only covers biomedicine. The tool
  says so instead of pretending they came back clean.
- **Not a citation checker.** It does not tell you whether the paper says what
  you claim it says. Nothing does that for you yet.

## When Crossref contradicts itself, you get told

Look up `10.1148/85.3.474` and the API hands you two notices for the same paper,
from the same Retraction Watch record (#19937), with the same timestamp, and
different verdicts: **retraction** and **expression of concern**. Upstream, the
retraction was downgraded to an expression of concern in March 2026. Crossref
appends the new verdict instead of overwriting the old one, so both are served
and nothing in the response says which is current. A user
[reported this in May 2026](https://community.crossref.org/t/15831); Crossref
confirmed the cause and opened CR-2746 at medium priority. It is still live.

Until this was measured, refcheck took the worst notice and printed
**RETRACTED — do not cite this as evidence** over a paper that was never
retracted. That is the single most expensive thing this tool can get wrong: it
does not waste your time, it makes you throw away a good citation. It now says
the notices contradict each other and sends you to
[retractiondatabase.org](https://retractiondatabase.org/) to settle it yourself.

`research/measure_conflicts.py` is the script that sized it. On 2026-09-09 it
scanned **417,618 update records** — every retraction, correction, erratum,
corrigendum, expression of concern, withdrawal, removal and partial retraction
Crossref holds — and found **6 works** carrying assertions that share a
record-id and disagree about what happened:

| work | record | the API serves | upstream CSV says | leftover |
|---|---|---|---|---|
| `10.1148/85.3.474` | 19937 | retraction · EoC | Expression of concern | `retraction` |
| `10.1109/bibe.2018.00052` | 45015 | retraction · EoC | Expression of concern | `retraction` |
| `10.1051/ocl/2024009` | 63890 | retraction · EoC | Expression of concern | `retraction` |
| `10.1007/s12275-015-0740-4` | 37343 | retraction · correction | Correction | `retraction` |
| `10.1038/s41598-022-06705-7` | 37754 | retraction · correction | Correction | `retraction` |
| `10.3892/etm.2024.12720` | 69356 | retraction · `68818` | Retraction | `68818` |

Six in 417,618 is rare. It is also, in five of the six, the loudest possible
wrong answer: the leftover half is the retraction. Run the scan yourself — no
key, about half an hour:

```
python3 research/measure_conflicts.py --out conflicts.json
python3 research/measure_conflicts.py --csv retraction_watch.csv   # who is stale
```

Those last two columns come from the
[Retraction Watch CSV](https://gitlab.com/crossref/retraction-watch-data) that
Crossref publishes, which holds one row per record id and so can settle which
half is current. **refcheck itself does not do this** and will not: it is a 66 MB
download to resolve six works, and the browser version has no business fetching
it at all. Knowing the answer here is what tells you the tool is right to refuse
to guess, not a licence for it to start guessing.

That last row is a different bug, reported alongside: the assertion's `type`
**and** `label` are both the literal string `68818` — itself a live Retraction
Watch record id, for a retraction of an unrelated paper. The CSV is clean there
(72,431 rows, five distinct `RetractionNature` values, and record 69356's is a
plain `Retraction`), so that string is not coming from upstream.

## Tests

```
python3 test_refcheck.py                  # 75 tests, offline
REFCHECK_RED=1 python3 test_refcheck.py   # 81, adding the live-API cases
```

One of those live tests asserts that `10.1148/85.3.474` still arrives
contradictory. If Crossref fixes CR-2746 the test goes red — which is exactly
how I want to find out. Another asks NCBI for three real records — one with a
DOI, one from 1979 without, one that does not exist — so a change in the shape of
their answer surfaces as a failure rather than as a wrong report to a reader. A
third asserts that `10.1093/jnci/djr419` still reaches PubMed with two notices
and Crossref with none — if Crossref ever deposits them, that goes red too.

The browser version has its own battery — 67 checks driving the real page in
headless chromium against the real APIs, including forced network failures and a
PubMed outage that must not take Crossref down with it, because the interesting
bugs live there:

```
node /path/to/accesible_cdp.js --url file://$PWD/docs/index.html \
     --script tests/test_web.js --limite 240000
```

That runner is a small dependency-free CDP driver of mine that is not in this
repo; any headless-browser harness will do. What the battery defends is worth
saying plainly, because the first version failed it: when a lookup fails, the
result must be reported as **unknown**, never merged into the clean pile.

## Licence

MIT. Use it, fork it, put it in your pipeline, no attribution needed.

Data from the [Crossref REST API](https://api.crossref.org). Please be kind to
it: it is a public good funded by nobody in particular.
