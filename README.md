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
DOIs found in it are sent, straight from your machine to Crossref. Save the page
and it keeps working from your own disk — it is one HTML file with no
dependencies, no cookies and no analytics.

It is built to be usable rather than just claimed to be: every colour pair is
measured at WCAG **AAA** contrast in both light and dark, the focus ring is never
removed, severity is stated in words and not by colour alone, and the whole thing
is driven by a 41-check battery in a real headless browser against the real API.

## Use it from the command line

```
python3 refcheck.py refs.bib          # a BibTeX file
python3 refcheck.py dois.txt          # one DOI per line, or a pasted bibliography
python3 refcheck.py refs.bib --json   # machine-readable, for pipelines
echo 10.1371/journal.pone.0161231 | python3 refcheck.py -
```

Real output:

```
  5 reference(s) checked · 3 carry a change notice
  1 not found in Crossref (preprints, books, bad DOI) — not checked

  RETRACTED — do not cite this as evidence
    RETRACTED: LRRK2 kinase activity mediates toxic interactions between genet
    10.1016/j.nbd.2012.05.020
      → Retraction (2012-09-01): https://doi.org/10.1016/j.nbd.2012.05.020

  CORRECTED — check the number you are quoting is still there
    Virus-Like Nanoparticle Vaccine Confers Protection against Toxoplasma gond
    10.1371/journal.pone.0161231
      → Correction (2024-03-21): https://doi.org/10.1371/journal.pone.0301214
```

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
  Watch data — and shows you the answer. All credit for the data is theirs.
- **Not complete.** It only sees what publishers registered. A correction that
  was never deposited is invisible here, and so is anything without a DOI.
  Preprints, books and chapters are frequently outside the checked set — the tool
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

| work | Retraction Watch record | the API says both |
|---|---|---|
| `10.1148/85.3.474` | 19937 | retraction · expression of concern |
| `10.1109/bibe.2018.00052` | 45015 | retraction · expression of concern |
| `10.1051/ocl/2024009` | 63890 | retraction · expression of concern |
| `10.1007/s12275-015-0740-4` | 37343 | retraction · correction |
| `10.1038/s41598-022-06705-7` | 37754 | retraction · correction |
| `10.3892/etm.2024.12720` | 69356 | retraction · `68818` |

Six in 417,618 is rare. It is also, in every one of the six, the loudest wrong
answer the tool can give. Run the scan yourself — no key, about half an hour:

```
python3 research/measure_conflicts.py --out conflicts.json
```

That last row is a different bug and was reported separately: the assertion's
`type` **and** `label` are both the literal string `68818`, which is another
Retraction Watch record id sitting in a field that should hold a notice type.

## Tests

```
python3 test_refcheck.py                  # 35 tests, offline
REFCHECK_RED=1 python3 test_refcheck.py   # 39, adding the live-API cases
```

One of those live tests asserts that `10.1148/85.3.474` still arrives
contradictory. If Crossref fixes CR-2746 the test goes red — which is exactly
how I want to find out.

The browser version has its own battery — 41 checks driving the real page in
headless chromium against the real Crossref API, including forced network
failures, because the interesting bugs live there:

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
