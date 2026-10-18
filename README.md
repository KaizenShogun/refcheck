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

**Which tool, in one line:** if you care about corrections, errata and expressions
of concern, use this; if you have R and care most about retractions and
*reinstatements*, use the R package `retraction`, which beats this one there.
Both halves are [measured below](#head-to-head-with-the-r-package-retraction).

And since 20 September 2026 it will also tell you what changed **since the last
time you asked** — `--watch`, below, and since 21 September in the browser too,
without the page keeping anything about you. That is the same argument continued
rather than abandoned: a permanent flag on every corrected paper would indeed be
a mess, but "these three of your thousand references picked up a notice this
month" is not a mess, it is the only part you have not already read.

## Use it in your browser — nothing to install

**→ [kaizenshogun.github.io/refcheck](https://kaizenshogun.github.io/refcheck/)**

Paste your reference list, or open the file you already have — a `.nbib`
straight from PubMed's **Send to → Citation manager**, a `.ris` out of Scopus,
Web of Science, Embase, Rayyan or Zotero, Zotero's **CSL JSON**, a `.bib`, a `.txt` — or the
manuscript itself as a Word `.docx`. Drag it onto the box or use the file button. Press one button. No
account, no upload, no terminal.

The file is read *inside your browser* by the same page, and its bytes never
leave your machine; only the identifiers found in it are sent. A whole search
export is fine — 1,000 records, 7.3 MB, measured — and a file that big is held
aside rather than shown, because displaying it is the slow part. See
[below](#a-thousand-references-which-is-what-a-systematic-review-actually-has).

There is no server behind that page: your text stays in the browser and only the
identifiers found in it are sent — straight from your machine to Crossref and to
NCBI, both of which are asked about every reference, and, since 2026-09-18, to
**doi.org** for the DOIs Crossref did not return, to find out which register owns
them. That third one only ever sees DOIs that already failed, never your whole
bibliography. Since 2026-09-19 NCBI is also asked about the digits on the tail
of a DOI that does not exist, to find out whether they are a PubMed id — again,
only for DOIs that already failed everywhere else. (Until 2026-09-11 only your
PMIDs reached NCBI. That changed when the tool started asking both registers,
and it is better said plainly than left as a tidier old sentence — this is the
fourth time this paragraph has had to be corrected rather than quietly kept.)
Nothing passes through me. Save the page and
it keeps working from your own disk — it is one HTML file with no dependencies,
no cookies and no analytics.

It is built to be usable rather than just claimed to be: every colour pair is
measured at WCAG **AAA** contrast in both light and dark, the focus ring is never
removed, severity is stated in words and not by colour alone, and the whole thing
is driven by a 207-check battery in a real headless browser against the real APIs.

## Use it from the command line

```
python3 refcheck.py refs.bib          # a BibTeX file
python3 refcheck.py dois.txt          # one DOI per line, or a pasted bibliography
python3 refcheck.py pubmed.txt        # PMIDs work too — see below
python3 refcheck.py export.nbib       # PubMed's "Send to → Citation manager" file
python3 refcheck.py scopus.ris        # Scopus, Web of Science, Embase, Rayyan, Zotero…
python3 refcheck.py manuscript.docx   # a Word draft: body, footnotes and endnotes
python3 refcheck.py references.json   # CSL JSON: Zotero, Pandoc, Manubot
python3 refcheck.py refs.bib --json   # machine-readable, for pipelines
echo 10.1371/journal.pone.0161231 | python3 refcheck.py -
```

Real output:

```
  5 reference(s) checked · 4 carry a change notice
  1 registered at DataCite, not Crossref — nothing is wrong
  with it, this tool just cannot speak for it

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

      · DataCite, not Crossref: 10.48550/arxiv.1706.03762
```

The last line is the point of [asking doi.org too](#an-unfound-reference-now-says-which-kind-of-unfound):
that arXiv preprint used to print as "not found in Crossref", which reads like
something is missing. Nothing is. Crossref will never hold it.

The `EXPRESSION OF CONCERN` one is the point of asking two registers: Crossref's record for
`10.1093/jnci/djr419` is empty, and this tool used to call that reference clean.

Exit codes, so it can gate a CI job — a journal checking submissions, a lab
checking a manuscript before it goes out, a systematic review checking its own
included studies:

| code | meaning |
|---|---|
| `0` | everything checked against **both** registers, nothing found |
| `1` | at least one reference carries a change notice |
| `2` | bad usage, a reference that could not be looked up, **or a run where PubMed did not answer** |

That last one matters. A failed lookup is not a clean reference, so it does not
let the gate go green — and since 14 September 2026 neither does a run where one
of the two registers was unreachable. That used to exit `0`: a night when NCBI
was down passed a CI gate as clean while being blind to the register that holds
one corrected paper in five.

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

## A thousand references, which is what a systematic review actually has

Twelve references is the demo. The people this is for screen a search: they tick
the results in PubMed, hit **Send to → Citation manager**, and end up with a
`.nbib` holding hundreds or thousands of records. I took a real 1,000-record
export — 7.3 MB, because a MEDLINE record with its abstract and MeSH terms runs
about 7.3 kB — and ran it through both versions on 2026-09-13. Neither survived
it well, and the browser version failed in the two ways that make someone give
up and close the tab:

| | before | now |
|---|---|---|
| a 1,000-record file (7.3 MB) | refused: "probably a PDF or a database dump" — the ceiling was 8 MB, about 1,070 records | opened; the ceiling is 64 MB, about 8,500 records |
| putting it in the textarea | froze the page 12 s warm, **26 s from a fresh load** | never goes in the box: held aside, 123 ms, and a line tells you the name, size and record count |
| pressing Check | "Checking 1000 references…" and a minute of apparent nothing | says *about a minute*, and why: the free registers allow one request a second |

The textarea was the whole problem, and it was there for my convenience rather
than anyone's need: scanning that same 7.3 MB string end to end costs 1 ms, and
*displaying* it costs 26 seconds. So a big file is now kept in memory and checked
as it is, with a visible chip and a **Remove this file** button — because
something held invisibly is worse than something slow. Type in the box while a
file is loaded and what you typed wins, and it says so out loud rather than
quietly checking the other thing.

### The cache, and what it refuses to remember

On the command line, the same file took **65 s** the first time and **1 s** the
second, and the two reports are byte-identical apart from one added line saying
where the answer came from. Somebody screening a review re-runs that file every
time they add a batch, and there is no honest reason to make two free public
registers answer the same thousand questions again:

```
python3 refcheck.py review.nbib              # uses the cache
python3 refcheck.py review.nbib --no-cache   # asks both registers again
```

It lives in `~/.cache/refcheck/checked.json` (`REFCHECK_CACHE` to move it), keeps
an answer for 7 days (`REFCHECK_CACHE_DAYS`), and is written with mode `600` —
it is a list of what you have been reading, and it stays yours. Nothing about it
is sent anywhere.

**The browser version has one too since 14 September 2026**, and where it lives
was the decision, not whether to build it. It is `sessionStorage`: it belongs to
the one tab you have open and is gone when you close it. This page gets opened on
shared computers — a library counter, a university cluster — and the list of what
somebody has been reading should not outlive their session. Measured the same day
on 1,000 references, with the network stubbed so what is being timed is the page's
own pacing rather than two public registers' load
(`research/measure_page_cache.js`):

| | cold run | same file again |
|---|---:|---:|
| time | 31.0 s | **0.26 s** |
| requests to Crossref and NCBI | 45 | **0** |

It costs 75 kB of tab memory for those 1,000 references — 75 bytes each — and
`localStorage` is left completely empty, which the measurement asserts rather
than promises. There is a **Ask both registers again** button, because "reload
the page" would have been a lie: `sessionStorage` survives a reload.

Four things neither cache will do, which matter more than the speed:

- **A failed lookup is never stored.** A dropped connection stays a dropped
  connection, so "I could not check this" can never age into a cached clean bill.
- **Neither is an answer only one register gave.** Found on 14 September 2026 by
  reading the previous day's own code: when NCBI was unreachable, the Crossref
  half was stored and handed back for seven days as if both registers had spoken.
  PubMed is the one holding the 21% of corrections Crossref never heard about, so
  that was a cached blind spot. An entry now records which registers it rests on
  and is only reused by a run that wants no more than those.
- **It says out loud how much of the answer came off the disk, and how old the
  oldest of it was** — `998 of those came from the local cache, the oldest 2 days
  old`. An answer read from disk is an answer about the day it was fetched, and a
  notice published since then would be invisible. In a tool whose silence gets
  read as "fine", that has to be on the page, not in the documentation.
- **It caches answers about DOIs, not the translation of a PMID.** Paste a list
  of PMIDs and NCBI is still asked to turn them into DOIs each run — 10 requests
  per 1,000. A `.nbib` needs none of those: the file already carries both.

## PMIDs work, and here is exactly how far they get you

Half of biomedicine does not cite by DOI. It cites `PMID: 9500320`, or pastes a
`pubmed.ncbi.nlm.nih.gov/9500320` link, and until now this tool answered that
with "No DOIs found in that file" — which is a useless thing to say to somebody
holding a perfectly good reference list. Paste PMIDs and they now get looked up:

```
$ python3 refcheck.py pubmed.txt
  3 reference(s) checked · 2 carry a change notice
  1 of those has no DOI anywhere, so it was checked against PubMed only
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

So a 2024 paper is nearly always reachable and a 1979 paper is a coin flip.
Same for a PMID that does not exist in PubMed at all: you are told, because a
citation pointing at nothing is worth knowing about before a reviewer finds it.

### A PMID with no DOI is no longer "not checked" (18 October 2026)

Until today a PMID with no DOI behind it came out as `not checked`, by name.
Honest, and lazier than it had to be: Crossref is indexed by DOI, but PubMed is
not, and its own record carries the retractions and errata NLM's indexers have
linked to it, DOI or no DOI. So now refcheck asks PubMed for that record by its
PMID and reads those links, and the report says in so many words that the
reference was **checked against PubMed only**. A silence from one register is a
weaker silence than one from two, and you should know which you are reading.

I measured whether it was worth building before building it. Ground truth is the
Retraction Watch CSV of 18 October 2026: every row whose original paper has a
PubMed id and no DOI. Each was then run through the code shipped here,
`research/measure_pmid_only.py`, JSON in `research/pmid_only_20261018.json`:

| RW says | rows | PubMed knows a DOI (already checked) | **now flagged, same notice** | other notice | PubMed silent |
|---|---:|---:|---:|---:|---:|
| Retraction | 706 | 51 | **606** | 4 | 45 |
| Expression of concern | 25 | 2 | **18** | 5 | 0 |
| Correction | 19 | 4 | **12** | 2 | 1 |

**636 notices that this tool reported as "not checked" yesterday are found
today.** Not only old papers, which is what I expected: 307 of the 636 (48%)
are from before 2010, but 288 are from the 2010s and 41 from this decade — PubMed
simply lists no DOI for them. Dates are RW's `OriginalPaperDate`. The 45
silent retractions are real misses and stay misses: PubMed has the record and
lists nothing, so refcheck says nothing was found, against PubMed only, which is
true and not reassuring. No lookup failed in this run.

Two things the measurement caught before you could. A PubMed **book chapter**
(Endotext, WHO guidelines on Bookshelf) comes back as a `PubmedBookArticle`, not
a `PubmedArticle`; my first script missed one, a retracted WHO guideline, and
would have shipped calling every chapter "PubMed did not answer". And a PMID that
PubMed answers for in the batch but leaves out of the reply is reported as **not
checked**, never as clean. Both have tests that fail without the fix.

NCBI states 3 requests/second without an API key. refcheck starts at 1/s and
looks up 100 PMIDs per request. `--no-pubmed` skips NCBI entirely if you would
rather not talk to them.

## The file PubMed gives you is a trap, and it was making this tool lie

If you are running a systematic review, you do not type your references. You tick
the results of a search, press **Send to → Citation manager**, and PubMed hands
you a `.nbib`. That is the MEDLINE format, and it is not a bibliography: it is a
record format, where every record also carries **the identifiers of other
people's papers**.

```
PMID- 31978945                                     ← the article you exported
LID - 10.1056/NEJMoa2001017 [doi]                  ← its DOI
CIN - N Engl J Med. 2020;382(8):760-762. doi: 10.1056/NEJMe2001126. PMID:
      31978944                                     ← a commentary ABOUT it
RIN - Neurobiol Dis. 2025;210:106930. doi: 10.1016/j.nbd.2025.106930. PMID:
      40320298                                     ← the notice that RETRACTED it
```

Read that as loose text — which is what refcheck did until today — and three
things go wrong at once. The commentaries get checked as if you had cited them.
The retraction notice gets checked as if it were one of your references. And the
article's own id, written `PMID- 31978945` with a hyphen, does not match a
pattern that expects `PMID:`, so it is missed entirely.

I measured it on 2026-09-12 rather than estimate it: a real PubMed search
exported at 200 records, put through the old code and checked against what NCBI
says each record's identifiers actually are.

| | old (read as text) | now (parsed as MEDLINE) |
|---|---:|---:|
| DOIs reported | 212 | **197** |
| of those, belonging to papers you never cited | **15** | **0** |
| real PMIDs found, of 200 | **0** | **200** |
| PMIDs reported that were strangers' | **8 of 8** | 0 |
| records with no DOI, named in the report | 0 of 3 | **3 of 3** |

The last row is the one that would have cost somebody something. Three of those
200 records have no DOI — old book chapters, mostly — and with their own PMID
invisible they were checked by neither identifier and appeared nowhere in the
output. Not as a warning, not as `not checked`. Gone, in a report whose silence
means "clean".

So a MEDLINE export is now parsed as the record format it is, and only the four
tags that speak about the record they sit in are read (`PMID`, `AID`, `LID`,
`SO`). That is a whitelist on purpose: PubMed can add a new kind of
cross-reference next year, and a blacklist of the ones I happen to know about
would let the new one through in silence.

One good side effect — the file already states every article's own DOI *and*
PMID, so a `.nbib` needs **no lookup at all** to work out what you are asking
about. No round trip to NCBI, and the references with no DOI keep their title and
year straight from your file, so they can be named back to you offline.

## And then I measured what a `.ris` was doing, which was worse

`.ris` is the format everything else exports: Scopus, Web of Science, Embase,
Rayyan, Covidence, EndNote, Zotero. If you are screening a review, it is almost
certainly the file you have.

This tool read it as loose text, under a comment I had written that said its
DOIs "are found perfectly well". I had never measured that. On 2026-09-23 I did,
on **40 `.ris` files real people deposited on Zenodo beside their reviews** —
Scopus exports, Web of Science `savedrecs`, Embase, Rayyan, Publish or Perish,
**17,140 records** — and it was wrong in the expensive direction:

| of 17,140 records in 39 real `.ris` files | |
|---|---:|
| carry a DOI of their own | 9,916 (57.9%) |
| carry a PubMed id and no DOI | 9 (0.1%) |
| **carry no checkable identifier at all** | **7,215 (42.1%)** |

Read as loose text those 7,215 were not reported as unchecked. They were
**invisible**: the tool never knew they existed. One of the files is a genuine
Scopus export of **1,409 papers**, and Scopus had not been asked for the DOI
column. Here is what this tool used to say about it:

```
  1 reference(s) checked · 0 carry a change notice
  Nothing found. That is the expected result most of the time;
  it is the 1-in-N that this exists for.
```

One. Out of 1,409. Under a sentence that anyone skimming reads as *your
bibliography is clean*. That is the same failure the `.nbib` reader had above,
at forty times the scale, and in a tool whose silence reads as "clean" it is the
costly one.

It said something else that was false, too: *"Watching 1409 reference(s)"* — over
a watch file that held none of them, because a reference with no identifier
cannot be recognised on a later run and is not stored. Fixed at the same time.

Now a `.ris` is parsed as the record format it is, and it says:

```
  0 reference(s) checked · 0 carry a change notice
  Your file lists 1409 reference(s) in all. 1409 of them name no DOI and no
  PubMed id of their own, so NOTHING could be asked about them —
  not clean, unknown. Re-export including the DOI field to check those.
```

**The whitelist is measured, not copied from the RIS spec.** `M3` is "type of
work" in the spec and holds **2,469** of the corpus's DOIs, because that is
where Scopus puts them — a spec-pure reader that only read `DO` would have
thrown those away. And `AN` *looks* like an id field and is deliberately not
read: its real values in the corpus are `pub.1168151018` (Dimensions),
`rayyan-510015106` and bare counters like `105`, so reading it as a PubMed id
would have checked a stranger's paper. `C2` **is** the PubMed id — not assumed:
40 of the corpus's 741 values were sampled and asked of PubMed, and the title
that came back is the record's own in **40 of 40**.

### What it costs, measured against itself

A fix that quietly drops references that used to be checked is not a fix, so
both directions were measured on the same frozen corpus:

| | |
|---|---:|
| records that were invisible and are now named | **7,205** |
| DOIs the loose reader reported that belong to **no record in the file** | **322** |
| records where the loose reader did find a DOI and this one does not | **10** |

Those 322 are abstracts citing other work and dataset DOIs sitting in notes.
They were shown to readers as *their own references* — and if one of them
carried a retraction, this tool would have told you that a paper you never cited
was retracted.

The 10 are the real cost, and I asked Crossref whose papers they are instead of
guessing: **8 are the record's own DOI, quoted inside its own abstract** (a
"How to cite:" line), one is a different item, and one does not exist. So
guessing would be right 8 times out of 10 — and the other 2 are the one thing
this tool must never do. Those 10 are not dropped, and they are not claimed to
have no DOI either, because that would be false. They are named, with the DOI
the record mentions, marked *not checked, may be a cited paper*, so you can
settle it in one click.

One file in the corpus is correctly **not** treated as RIS: a Lattes CV dump
whose lines read `TY  - MEMBRO`, `NOME  - …`. Detection requires an `ER  -`
closing a record, which is what keeps it out.

Reproduce all of it:

```
python3 research/fetch_ris_corpus.py --out ris_corpus/
python3 research/measure_ris.py ris_corpus/ --confirma
```

## A Word manuscript, read as it is (15 October 2026)

Until today the page turned a `.docx` away and the command line read it as
garbage and found nothing. That was the wrong way round for the people this is
for: what reaches a librarian's desk is usually not an export, it is the draft.

Now both read it, inside the browser for the page (a `.docx` is a zip, and the
browser inflates it natively — no library, no upload). The body, the footnotes
and the endnotes are read; so are field codes, which is where a hyperlink's
target lives and where Zotero and EndNote keep each citation's DOI even when the
printed style shows none. Text deleted with *Track changes* is not: the author
took it out, so it is not cited.

Measured on **40 `.docx` files real people deposited on Zenodo**, frozen with a
manifest, against LibreOffice's own text export as the referee: 14 of them
carry DOIs, **270 distinct DOIs, none missed and none invented**. The page and
the command line produce the identical text for all 40, checked under node. To
be plain about what that corpus did *not* exercise: none of its footnotes held a
DOI, no citation lived only in a field code, and no DOI needed an XML entity
decoded. Those paths are covered by a synthetic file and by mutations that each
make a test fail, not by real-world evidence.

A PDF is still refused, with a sentence saying so. Getting reliable text out of
a PDF is a different problem, and the R package `retraction` does read them.

### What the citation fields hold (17 October 2026)

The corpus above had no citation living only in a field code, so that path was
untested on real files. Today I looked for manuscripts that still carry their
reference manager's fields: **376 `.docx` files from Zenodo and Figshare** (333 distinct
by content), frozen with a manifest. Only **10 distinct documents** kept their fields (most
deposits are flattened before upload): 2 Zotero, 1 Mendeley, 7 EndNote, holding
**461 cited records**. Of those, **296 carry a DOI, and refcheck already read all
296**. 158 carry no identifier at all, and nothing can be done for them from here.

The gap was the other 7: EndNote records whose only identifier is a **PubMed id
in `<accession-num>`**, with no "PMID" word beside it, so the loose reading never
saw them. All 7 are in one EndNote manuscript, and I checked each against PubMed
by title: 7 of 7 are the paper the record names. Now the page and the command
line restate, after the document's text, three things from inside the fields:

- an EndNote record's DOI, and if it has none, its accession number when that is
  a bare number of PubMed's length and the record names PubMed or no database
  (CINAHL and Embase put numbers there too);
- EndNote records stored in base64 in `w:fldData` (the `EN.CITE.DATA` form long
  citations take), which were never read before;
- a Zotero or Mendeley item's PMID, **only when the item has no DOI**. Mendeley
  stores a PMID beside the DOI on most items; restating those would cost PubMed
  lookups for nothing, and a wrong one would add a paper nobody cited.

Nothing else from a record is added, so an abstract stored in a field cannot
contribute a DOI. On all 376 files, before and after: **3,560 DOIs both
times, not one added or lost; PMIDs 29 → 36, the 7 above and nothing else**
(`research/compare_docx_extraction.py`). Page and command line give identical text
for the 49 distinct real files the tests carry (`test_refcheck.py`), and nine
mutations, one per rule and on both sides, each turn a test red.

To be plain about how much this changes: **in this corpus, no verdict.** All 7
papers are from 1964 to 2006 and PubMed holds no DOI for any of them, so they
now appear in the report by name as "no DOI in PubMed — NOT checked" instead of
not appearing at all. That is the honest improvement: a reference the tool
cannot check is listed, not silently dropped. The base64 path found nothing new
either: every DOI stored in `fldData` in these files was also printed in the
bibliography. Both paths are covered by a synthetic file for the case where it
would matter, a style that prints no DOI.

## CSL JSON, read as records (16 October 2026)

CSL JSON is what Zotero's *Export → CSL JSON*, Pandoc and Manubot write. Until
today it went down the loose-text path, which finds every DOI-shaped string in
the file. Measured on **four real Manubot reference lists, 3,008 records**
(`research/measure_csl.py`, results in `research/csl_20261016.json`, files
frozen with their SHA-256):

| | loose text | record reader |
|---|---:|---:|
| records with no identifier, missing from the report | **663** (22%) | 0 — listed by title |
| records known only by `"PMID": "…"`, lost | 6 of 12 | 0 |
| DOIs sent that are not the record's own | 5 | 0 |
| record DOIs missed | 1 | 1 |

The five invented ones are a companion paper linked from an abstract's JATS
markup, a `v1` or a `/2562646/a-review-of…` swallowed from a publisher URL, and
a figshare DOI without its version. The missed one is a `DOI` field holding a
blog path, which is not a DOI.

Each record is read from its own fields: `DOI`, then a DOI in `URL`, then a
`DOI: …` line in `note` (Zotero's convention for item types with no DOI field);
`PMID`, a `PMID: …` note line, or a PubMed URL. The abstract is never taken as
the record's identifier; a DOI found only there is shown, marked as not checked.
Three records had a DOI only in `URL` or `note`, and all three match the
record's title at doi.org.

Honest limits: the corpus is one family of exporter (Manubot). Zotero's own CSL
JSON uses the same field names, but it is not in the measurement. **EndNote XML
is not read yet**, for a reason worth saying: Zenodo gave me two real EndNote
libraries, 700 records, and *none* of them carries a DOI field. That is not a
corpus to build a reader on.

Along the way, two old bugs: the page's "your file lists N references in all"
left out the PMIDs PubMed holds no DOI for (the command line counted them), and
every plain command-line run ended with *"Watching 2 reference(s) from now on:
None"* although nothing was being watched. Both fixed, both with a test that
fails on the old code.

## My own extractor was inventing DOIs that do not exist

A reference this tool cannot find is reported as *"not found in Crossref —
these were not checked, which is not the same as clean"*. That sentence is
carefully worded and it was, in a number of cases, describing a problem I had
created two steps earlier.

Bibliography text does not arrive clean. It arrives with HTML and JATS still in
it, because that is how publishers deposit it and how it survives a copy-paste
out of a web page. The DOI pattern has to allow angle brackets, since a whole
family of real Wiley DOIs contains them —

```
10.1002/(sici)1097-0258(19970515)16:9<1041::aid-sim521>3.0.co;2-f
```

— and that same permission let the extractor run straight through a closing tag
and keep going. These are real captures:

```
10.1007/978-981-19-6561-6</ext-link>
10.32471/umj.1680-3051.153.237930.</a></li>
10.21248/contrib.entomol.68.1.1-29<br>riedel     ← it kept the next word, too
10.21083/surg.v11i0.4389>                        ← from <https://doi.org/…>
10.3389/fpubh.2020.00383/full                    ← from the publisher's URL
```

Crossref holds no record under any of those strings, so the tool answered "not
found — not checked" about papers that exist, are indexed, and may well be
retracted. **In a tool whose silence reads as "clean", that is the expensive
kind of wrong**, and it is the exact failure this project exists to catch in
other people's data.

**Measured, not guessed.** `research/measure_unresolved.py` takes DOIs the way a
person actually supplies them — pulled with refcheck's *own* extractor out of
the `unstructured` citation text authors deposit at Crossref, not out of the
clean `DOI` field a publisher's pipeline fills in — and asks
[doi.org](https://doi.org) whether each one exists.

> **Correction, 18 September 2026.** This paragraph first published "of 529 such
> DOIs, 145 did not exist". **That number described a population it had not
> measured.** The filter that defines the population — keep only the lines the
> publisher could *not* match to a DOI — was added to the script after the run
> that produced the figure, and it shrinks the corpus about 25-fold. The
> reasoning behind the filter was wrong as well: Crossref does not rewrite
> `unstructured`, so a matched line is not a "normalised" one, and the unmatched
> lines are unmatched largely *because* their DOI is broken — measuring only
> those and publishing the rate as everyone's is the mistake this tool exists to
> catch. The corpus is now frozen on disk
> (`research/corpus_crudo_20260918.json`, 5,590 lines from 400 works across four
> years) so that any two runs are comparable at all, and it keeps every line
> with a flag for which stratum it came from.

Re-measured on that frozen corpus, with the extractor fixed:

| of 705 DOIs written by authors | |
|---|---:|
| the Crossref batch returns it | 94.5% |
| is Crossref's, but the batch did not give it | 1.1% |
| registered at another agency (DataCite ×11, mEDRA ×1) | 1.7% |
| **the DOI does not exist** | **2.7%** |

**Except that most of that last row is not a broken citation at all.** Measured
19 September with `research/measure_pmid_glued.py`, on the same frozen corpus:
of those 19 nonexistent DOIs, **15 are a real DOI with a PubMed id welded onto
the end**, with no separator —

    10.1002/cncr.24840  +  20087961  →  10.1002/cncr.2484020087961

— which is a style of deposit at some journals, not a mistake by whoever wrote
the bibliography. refcheck now checks those as the real article (see [A DOI with
a PMID stuck on the end](#a-doi-with-a-pmid-stuck-on-the-end) below), so the
"does not exist" row falls from 19 to **5 of 705, 0.7%**, and the 705th figure
that matters most — how many references got checked — rises by 14.

> An earlier note in this file said 8 of the 19 were this shape. It was a count
> done by eye off a screen of output; counting them with code gives 15. The one
> that is not rescued of the 15 is `10.1634/theoncologist.4-1-45` + PMID
> 10337370, a 1999 paper for which PubMed lists no DOI at all — so the check
> cannot be closed, and refcheck says nothing rather than guess.

Run over the *same lines* with the extractor as it stood before 17 September,
that last figure is **4.9%**; before today's fix, **3.5%**. So of the DOIs this
tool used to declare nonexistent, **nearly half were broken by refcheck itself**
rather than by the person who wrote the bibliography. The bias that remains is
stated rather than hidden: these lines survived a publisher's pipeline, so they
are cleaner than a bibliography typed out of a PDF, and the "does not exist" rate
here is a floor for hand-typed ones, not an estimate of them.

The control matters more than the rescue, because a DOI is not something to be
clever with. `research/measure_extraction.py` compares the old cleaner against
the new one and looks both up, so "damage" means *resolved before and does not
resolve now* rather than merely "changed":

| | DOIs | the new cleaner differs | broken |
|---|---:|---:|---:|
| real Wiley SICI DOIs, sampled live | 84 | 0 | **0** |
| real DOIs in a 1,000-record PubMed export | 2,141 | 0 | **0** |

It only touches what was already broken. Two details worth stating because both
nearly went the other way:

- **It matches the *shape* of a tag, not the first `<`.** Of the SICI DOIs
  sampled, several have no digit after the bracket —
  `…4:1<ii::aid-sd36>3.3.co;2-e`, and three with an empty `<>`. The obvious
  shortcut would have corrupted real references.
- **Brackets are removed only when unbalanced.** A trailing `>` with no `<`
  before it closed a `<https://doi.org/…>`; a SICI's come as a pair and stay.
  I sampled 1,200 real DOIs and none ended in `]`, `:` or `)` — but absence of
  evidence is a poor thing to build on when the balanced test costs the same.

And the CLI and the page now clean a DOI with the same rule, which until today
they did not: the page stripped a trailing `:` and `]` and the CLI did not. Same
input, same tool, two verdicts, decided by whether you own a terminal. A test
extracts the page's JavaScript and runs it under node against the Python on the
same inputs, so the two cannot drift apart again in silence.

### The bracket the full stop was hiding (18 September 2026)

Yesterday's balanced-bracket rule had a hole in it, and the corpus above is what
found it. The rule only looks at the **last** character, so a citation written
in the very common `(doi: 10.1609/aimag.v20i2.1456).` style slipped past it: the
string ends in a full stop, so the bracket test saw nothing to do — and the
punctuation strip that ran afterwards took the stop away and left the unbalanced
`)` exposed, with nobody left to look at it.

Six DOIs in the corpus, all of them resolving perfectly well at Crossref, were
being reported to the reader as not found. The fix peels punctuation and
brackets **in alternation until nothing changes**, and the control is the same
one as before — resolved before and does not resolve now:

| | DOIs produced | damage | repaired |
|---|---:|---:|---:|
| against the extractor as it stood before 17 Sep | 705 | **0** | — |
| against the version published yesterday | 705 | 0 | **6** |

There is also a test asserting that cleaning a DOI twice gives the same answer
as cleaning it once. That property is exactly what yesterday's rule lacked: it
stopped while it still had work to do, and said it was finished.

## An unfound reference now says *which kind* of unfound

Three very different facts used to print one sentence — "not found in Crossref,
not checked":

- **the DOI does not exist**, at any agency. A typo, a line broken across a PDF
  column, a DOI copied with the sentence around it. Of everything in this
  report, it is the one thing you can fix this afternoon.
- **it is registered somewhere else** — DataCite holds every arXiv preprint,
  plus datasets and theses; mEDRA, JaLC and KISTI cover other regions. Crossref
  will never hold it, so silence here means nothing at all.
- **it is Crossref's and the index did not return it.** A genuine gap, and the
  only one of the three worth a second lookup.

[doi.org](https://www.doi.org/) answers this for free, with no key, in batches,
and with CORS open so the page can use it too. Only DOIs Crossref already failed
on are sent there — never your whole bibliography — and if doi.org cannot be
reached the tool does exactly what it did before, because telling someone their
citation is fabricated on the strength of a timeout would be the worst thing
here. `--no-ra` skips it entirely.

It also pays for itself in time. A second chance costs a second at Crossref's
1/s, and spending it on a DataCite DOI was always doomed; one request per ~150
DOIs now replaces all of those.

## A DOI with a PMID stuck on the end

    10.1002/cncr.24840  +  20087961  →  10.1002/cncr.2484020087961

Some journals deposit their reference lists with the DOI and the PubMed id run
together, no separator. The article is fine, the citation in your document is
fine — the *string* is broken, and until 19 September refcheck told you your DOI
did not exist. It is the biggest single bucket of that verdict: **14 of the 19
in the frozen corpus**, and one of those 14 turned out to carry an erratum from
2022 that was simply being lost.

**It is a check, not a repair.** Three things have to agree before one character
is changed:

1. doi.org has already said the string as written does not exist — a DOI that
   resolves is never touched, so a working reference cannot be broken by this;
2. the tail reads as a PubMed id (no leading zero) and the head still reads as
   a DOI;
3. **PubMed, asked about that id, returns that exact DOI.**

The third is the whole argument. Chopping digits off until something resolves
would sooner or later land on a *different real paper*, and reporting a
stranger's retraction against your reference is the worst thing this tool can
do. If two different splits both come back confirmed, neither is used: an
ambiguous rescue is a guess wearing a check's clothing.

Nothing is corrected silently. Both strings are printed — the DOI that was
checked, and the one your file actually spells — because the broken one is what
you have to search for to find the line, and the citation still needs fixing.

| measured 19 Sep on the frozen corpus | |
|---|---:|
| DOIs doi.org says do not exist | 19 |
| of those, a real DOI with a PMID glued on | 15 |
| **rescued — PubMed confirms id and DOI are one paper** | **14** |
| ambiguous (two confirmed splits → neither used) | 0 |
| **control: resolving DOIs that would be rewritten** | **0 of 600** |

The control is the row that matters. The rule only ever runs after doi.org has
said a string does not exist, so damage should be impossible by construction —
but "by construction" is an argument and that row is a measurement, and I have
had the argument be wrong before.

The one of the 15 that is not rescued is `10.1634/theoncologist.4-1-45` + PMID
10337370, from 1999: PubMed lists no DOI for that record, so the check cannot be
closed and refcheck says nothing instead of guessing. That is the rule working,
not a gap in it — 27.5% of PubMed records carry no DOI, and it is worst before
1990.

Cost: one batched request to PubMed per run, and only ever about DOIs that
already failed everywhere else.

## Watch mode: the notice that arrives after you filed the paper away

Checking a bibliography is a snapshot, and the thing that actually bites is the
retraction published eighteen months after you wrote the paper. So:

    python3 refcheck.py refs.nbib --watch watch.json

The first run saves what every reference says today and tells you it is
watching. Every later run compares, and puts what changed at the top:

    ==============================================================================
      WHAT CHANGED
    ==============================================================================

      NEW SINCE 2026-09-20 — 1 reference(s)
      -------------------------------------

      RETRACTED — do not cite this as evidence
        Phosphorylation of PDE4A5 by MAPKAPK2 attenuates fibrin degradation via p7
        10.1093/jb/mvz016 (PMID 30859186)
          → Retraction (2022-10-14): https://doi.org/10.1093/jb/mvac074

Add `--only-new` and it prints *nothing at all* when nothing changed, which is
what makes it runnable from cron without writing any glue:

    0 7 * * 1  cd ~/review && python3 refcheck.py refs.nbib --watch watch.json --only-new

(The exit code still means what it always meant — 1 if any reference carries a
notice, 2 if something could not be checked. What means "there is news" is that
there is output. Cron mails you on output, which is the behaviour you want.)

A reference you *added* since last time, which arrives already carrying a notice,
gets its own heading — `NEW TO THIS FILE, AND ALREADY FLAGGED` — rather than
being filed under "new since". The retraction may be from 2019; what is new is
the reference, and calling that this month's news would devalue the words. It is
its own block because leaving it out was a real bug in the first version of this:
adding an already-retracted paper to a growing review produced, under
`--only-new`, complete silence.

### Why this is not a second copy of Zotero's feature

Zotero, EndNote, LibKey and Papers all flag retracted items in your library, and
all four read one source: the Retraction Watch database. That is the right source
for retractions and it is not the whole problem, so before writing any of this I
measured the hole.

Take the 1,600 papers Crossref marks with a change notice in the corpus frozen on
2026-09-12 — 400 each of retraction, expression of concern, correction and
erratum — and ask whether Retraction Watch holds that paper at all
(`research/measure_rw_coverage.py`, 2026-09-20, against a copy of the RW CSV
downloaded the same day):

| Crossref says | n | in Retraction Watch | invisible to an RW-only checker |
|---|---:|---:|---:|
| retraction | 400 | 87.0% | 13.0% |
| expression of concern | 400 | 42.5% | 57.5% |
| erratum | 400 | 3.2% | **96.8%** |
| correction | 400 | 1.2% | **98.8%** |

Retractions are the control, not the headline: retractions are Retraction Watch's
entire subject, so if the crosswalk claimed it held few of them, the crosswalk
would be broken and not the database. It holds 87%. A positive control samples
500 DOIs out of the CSV itself and finds 500 through the same normaliser.

And the absences were second-guessed rather than assumed. RW has 5,946 rows
(of 72,621) with no usable original DOI, so a DOI-only crosswalk could in
principle be missing papers that are in there under no identifier. I asked
Crossref for the titles of 40 absent papers per population and looked each title
up in the CSV: **1 of 160** turned up that way. The absences are real.

None of that makes RW worse at its job — a routine erratum is not misconduct and
is not what RW is for. It does mean that watching a bibliography through RW alone
leaves roughly ninety-eight corrections in a hundred invisible, and for someone
screening a systematic review an erratum that changes a table is not a footnote.

### The three rules it will not break

1. **A failed lookup is never reported as good news.** If a reference carried a
   retraction last time and today's lookup times out — or Crossref has no record
   — it goes under `COULD NOT CHECK TODAY` with `last known: RETRACTED`, and the
   state file keeps the retraction. "It is fine now" on the strength of a
   timeout is the most expensive sentence this tool could produce.

   **And "a failed lookup" is per register, which it was not until 2026-09-21.**
   The rule was enforced on the reference's `estado`, and a run where Crossref
   answered and NCBI timed out keeps `estado` `ok`. So every notice the state
   held *from PubMed* looked absent, and was announced under `NO LONGER
   REPORTED` — beneath a sentence that read "Both registers answered", which the
   code had never checked. That is not a corner case: PubMed-only notices are
   the entire reason the second register is asked, one corrected paper in five.
   The most valuable thing this tool holds was the thing a timeout could lift.
   Now a notice can only be declared gone by the register that reported it, and
   only when that register actually answered; the rest goes under `COULD NOT
   CHECK TODAY` naming which register was silent. The state carries the silent
   register's notices forward untouched too — dropping them would make the next
   run that *does* reach NCBI announce a 2019 retraction as `NEW SINCE`.
2. **A watch run does not read the local cache.** The cache keeps an answer for
   7 days; a weekly watch would otherwise compare a stored answer against itself
   and report "nothing new" without having asked anybody. It still *writes* the
   cache, which helps the next ordinary run and misleads no one.
3. **References that leave your file are kept, not pruned.** Point `--watch` at
   the wrong file once and you would otherwise destroy the only baseline you
   have. Stale entries cost a few hundred bytes. `--forget` prunes them when you
   ask for it — see below, including the one case where it refuses.

### When the watch file and the bibliography are strangers

Rule 3 has a price, and on 2026-09-22 I measured it instead of arguing about it.
Take a real 1,000-reference PubMed export, one `--json` run so every verdict is a
real answer, and replay six ways a watch file can meet a bibliography
(`research/measure_watch_mixup.py`):

| scenario | of the watched references, still in the file | new refs reported | state after |
|---|---:|---:|---:|
| same file again | 100% | 0 | 1,000 |
| review grew by a quarter | 100% | 200 | 1,000 |
| a fifth of it dropped | 80% | 0 | 1,000 |
| half of it rewritten | 50% | 300 | 900 |
| almost entirely rewritten | 10% | 500 | 1,000 |
| **watch file from a different bibliography** | **0%** | 500 | 1,000 |

The last two rows are the finding: a mix-up produced *exactly* what a heavily
rewritten review produces — a wall of "new to this file", eleven of them already
carrying a notice, and a state that silently doubled. Nothing on screen told them
apart.

**How bad is it, measured and not assumed.** After the mix-up, the next correct
run over the right file gives the same four drawers as a clean state, number for
number. No verdict becomes wrong. What it costs is noise now, and 500 references
fused into a file nobody can take apart again. So this **warns and does not
refuse** — a tool that refused to run here would be unusable the day it guessed
wrong:

      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
      THIS WATCH FILE AND THIS BIBLIOGRAPHY HAVE NOTHING IN COMMON
      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

It prints under `--only-new` too. A cron job whose watch has quietly stopped
looking at your bibliography is the one silence that would last for ever.

**Zero is the only number anything is refused on**, and the table is why. The
figure is asymmetric on purpose — *how much of what I am watching is still in
this file* stays at 100% when a bibliography grows, which is the common
legitimate change a symmetric measure would flag. Everything between 1% and 99%
is somebody's ordinary Tuesday, so it is reported as a plain count on every run
and nothing more:

    Watch file: 40 reference(s) followed, 30 of them in this file.
      10 not in this text are kept anyway, in case the wrong file
      was checked. --forget drops them.

`--forget` does the pruning, and declines exactly once: when the file and the
watch file share nothing at all. That is not a bibliography that shrank, it is
the mistaken run itself, and pruning there would not tidy the file, it would
empty it. On the page the same thing is a checkbox on the save bar, offered only
when there is something to drop and dropping it is safe — the same shared rule,
asserted by the parity test.

That guard was wrong for an hour on the day it was written, and only running it
found it: the prune happened *after* the state had been updated with this run's
references, so the question "do these two have anything in common?" was being put
to a state that already contained the answer. It said yes by construction and
deleted the real baseline. A guard that cannot fail is not a guard; there is a
regression test named after it.

A notice really disappearing *is* reported, under `NO LONGER REPORTED`, and it is
deliberately not phrased as good news: neither register has a vocabulary for a
reinstatement (see below — 31 of 155 reinstated papers are still served as
retracted), so refcheck cannot tell a reversal from an edited record and sends
you to retractiondatabase.org instead of guessing.

The state file is written `600` and never leaves your machine. It holds DOIs,
notice DOIs and dates — the same reasoning as the cache: it is a list of what
somebody has been reading, and it stays with them.

### The same thing in the browser, without the page remembering you

Since 2026-09-21 the [web page](https://kaizenshogun.github.io/refcheck/) does
this too, which matters because the person this project is aimed at — someone
screening a review, at a library desk — is the one who does not have a terminal.

It could not be done with `localStorage`. On a shared computer the list of what
you have been reading must not outlive your session; that is why the page's
cache is `sessionStorage` and why it says so. So the state is not kept by the
browser at all: you get a small file, you keep it, and you hand it back next
time. Nothing is left behind, and you choose where it lives.

It is **the same file**, not a parallel format. You can start a bibliography in
the browser and carry it on with `--watch` in a terminal, or the other way
round. That is not a promise, it is a test: `test_refcheck.py` pulls the page's
`<watch-state>` block out of the HTML, runs it under node against `refcheck.py`
on the same fixtures, and asserts the two produce the same four drawers and the
same state file — then writes a state with one and reads it with the other, both
ways round, and asserts the result is silence. This is the third rule that lives
in two codebases at once here, and both of the earlier ones (the DOI cleaner,
the glued-PMID rescue) turned out to have been quietly disagreeing for months
before anybody extracted them and compared.

The three rules above hold on the page too, including the sharp edge of rule 1:
a register that did not answer never lifts its own retraction, and a watch run
does not read the tab's memory.

One limitation, said rather than hidden: `--watch --json` keeps the state file up
to date but prints the ordinary result list, with no machine-readable diff. The
JSON shape is what pipelines already parse and I am not going to change it for a
feature nobody has asked for yet; if you want the diff from a script today, read
the two state files, which are plain JSON.

### What it costs

Because rule 2 turns the cache off, a watch run always costs a cold run. Measured
on 2026-09-20 with the 1,000-record PubMed export (7.3 MB), minutes apart:

| | |
|---|---:|
| watch run, nothing changed | **71 s**, and *zero bytes* of output |
| ordinary run, warm cache, for comparison | 6 s (987 answers from disk) |

That 71 s is the price every time, not a first-run cost — there is no second run
that gets cheaper, by design. The state file for those 1,000 references is 259 kB.

Run it weekly or monthly, not hourly. The registers are free and public, and this
is a bibliography that does not change.

## What else is out there

This space is crowded, and I would rather send you to a better tool than keep you
here. I checked before building, missed something, corrected it, and checked
again on 2026-09-08. The honest landscape:

- **[Zotero](https://www.zotero.org/) + [Retraction Watch](https://retractionwatch.com/)** —
  excellent, free, already inside the tool most researchers use, and it watches
  your library continuously, which for retractions is more than this does. Its
  source is the RW database: measured on 2026-09-20 that holds 87.0% of the
  retractions Crossref marks and 1.2% of the corrections (table above). **EndNote,
  LibKey and Papers** flag retractions from the same database, so the same ceiling
  applies to all four.
- **[CiteGuard](https://github.com/lonexreb/cite-guard)** (`pip install retractguard`) —
  OpenAlex-native, and it *does* cover corrections and expressions of concern.
  If you want an institution-scale watchdog with a package behind it, look there
  first. It has a watch of its own, `watch_institution`, but from its README that
  one watches an institution by ROR id rather than a file of yours — a different
  question for a different reader. I found CiteGuard after publishing this, which
  says more about my search than about their work.
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
- **[`retraction`](https://cran.r-project.org/package=retraction)** (R, on CRAN
  since 2026-07-10, GPL-3) — **if you work in R, use this instead.** It reads
  BibTeX, RIS, EndNote XML, Word and PDF, matches by DOI, PMID and then fuzzy
  title, can ask Retraction Watch, Crossref, PubMed, Europe PMC, OpenAlex and
  DataCite at once and flag when they disagree, reports reinstated works as
  reinstated (which this tool cannot; see the 31 below), and has a watch mode, a
  Zotero-library scan and a CI gate. Its default source is Retraction Watch.
  On retractions it beats this tool; on corrections it sees almost nothing that
  Retraction Watch does not list, whichever sources you ask, and asking for all
  of them loses retractions it had found. Measured, not read off its changelog
  (which is what this line said on 2026-10-11): see
  [the head-to-head](#head-to-head-with-the-r-package-retraction) below. I
  found it on 2026-10-11, after this section had claimed a gap it was already
  filling.
- **scite.ai**, **Proofig RefGuard** — commercial, and they do far more than this.

**The gap this fills, stated narrowly enough to be checkable** (corrected
2026-10-11; the old wording said no free tool checked a whole bibliography for
every kind of notice, and `retraction` does): a **web page** that takes a whole
bibliography and reports corrections, errata and expressions of concern as well
as retractions, with **nothing to install**, no account, and no server that sees
your reading list. That is for the person at a library desk without R or a
terminal. If you have R, the package above does more, with the exceptions
measured next.

## Head-to-head with the R package `retraction`

Measured 2026-10-12, both tools on the same DOIs on the same day: `retraction`
0.1.0 in a `rocker/r-ver:4.5` container, refcheck from `main`. Each tool has a
home field, and scoring a tool on its own source tells you the plumbing works,
not that the coverage is good. So there are two ground truths and each table
says whose home it is.

**A. Retraction Watch's home.** The 1,904 rows of the four gold-standard files
described further down, replayed. `retraction` reads RW by default, so this is
close to RW checking itself.

| RW says | n | refcheck | `retraction` (default) | `retraction` `sources = "all"` |
|---|---|---|---|---|
| Retraction | 1,000 | 98.5% | **99.9%** | 67.7% |
| Expression of concern | 400 | 99.0% | 99.0% | 89.5% |
| Correction | 349 | **100%** | 99.7% | 84.8% |
| Reinstatement (silence is right) | 155 | 80.0%, 31 shown as RETRACTED | **100%** | **100%** |

refcheck's column reproduces to the row what it scored in September, which is
the control: nothing moved under it in four weeks. `retraction` wins here, and
the reinstatements are a real advantage it has and this tool cannot have.

The last column was run on 2026-10-13 and scored by the same `compare` that
produced the others, which still gives the default column to the row. Turning
on every source costs it **322 of the 1,000 retractions**, plus 42 expressions
of concern and 53 corrections, all of which the default had found. That is the
same mechanism as point 2 below, at scale: I asked Crossref about each of the
416 on 2026-10-14, and **395 carry an `update-to` pointing at their own DOI**.
Ten point at another DOI (the paper is itself a notice for something else) and
eleven no longer carry any `update-to` today, so those 21 I can't explain.

**B. PubMed's home.** A fresh draw (seed 20261012, written whole to
`research/pubmed_vs_20261012.json`): articles PubMed types as `retracted
publication`, plus the articles behind `published erratum` and `expression of
concern` notices. 870 with a DOI. **refcheck asks PubMed, so its 100% here is
circular and I do not count it as a result.** What the table measures is the
other column: how much of what PubMed knows reaches someone using `retraction`.

| PubMed says | n | `retraction` default | `retraction` `sources = "all"` |
|---|---|---|---|
| Retracted | 286 | 85.0% | 83.2% |
| Erratum / correction | 286 | **0.3%** | **0.3%** |
| Expression of concern | 298 | 39.3% | 97.7% |

Two things come out of that, and I went to its code to see why rather than guess:

1. **Corrections outside Retraction Watch are invisible to it.** Its Crossref
   source reads `update-to`, which is the field on the *notice* pointing at what
   it amends, not `updated-by` on the article you cited; and its PubMed source
   only recognises the `retracted publication` type. So a correction surfaces
   only if Retraction Watch happens to list it, and of the PubMed errata in
   this draw (PubMed held 263,249 that day) one in 286 did. Asking for every
   source does not help.
2. **Asking for every source loses 35 retractions out of 286** (12%) that the
   default had found, and gains 29 others. Re-run on those 65 DOIs: the same 35,
   so it is not the network. The mechanism, on `10.1038/mt.2016.104`: the
   publisher deposited the retraction *in place*, so Crossref serves an
   `update-to` of type `retraction` that points at the article's own DOI, under
   the title "RETRACTED: …". `retraction` treats any `update-to` as "this DOI is
   a notice, do not flag it", returns `none` before it looks at the title, and
   that verdict outranks the four sources (RW, PubMed, Europe PMC, OpenAlex)
   that all say retracted. The disagreement column does flag it, which is to
   its credit; the headline still says the paper is fine.

**So, the honest advice:** for retractions, and above all for reinstated works,
`retraction` with its default source is the better tool. If you also need the
corrections and errata on your reading list, which are the majority of change
notices, it will not show them, and this one will. Don't switch it to
`sources = "all"` hoping for more coverage: on Retraction Watch's own sample it
drops a third of the retractions the default finds (table A), for the reason in
point 2.

Reproduce: `research/measure_vs_retraction.py` (draw, refcheck, compare) and
`research/run_retraction.R`. The per-DOI joins are in
`research/vs_retraction_rw_20261012.json`,
`research/vs_retraction_rw_all_20261013.json` (table A with the `"all"` column)
and `research/vs_retraction_pubmed_20261012.json`.

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

### Against a reference standard, not against the other register

Both measurements above compare the two registers to each other, which tells you
they disagree but not who is right. The question a reader actually has is
different: **given a paper that really was retracted, does this tool say so?**

The Retraction Watch database answers it. It is maintained by people whose whole
job is finding these notices, it is CC BY, and Crossref republishes it, so it can
be used as ground truth rather than as a third opinion. `research/measure_rw_gap.py`
draws 200 retracted papers from each of five eras — stratified by the *original*
paper's year, because deposit practice has improved enormously and a uniform draw
would be dominated by recent papers and would flatter the answer — and runs them
through refcheck itself rather than a reimplementation.

Every nature in that database is measured, not just the gravest. All figures are
from 16 September 2026 except the retraction row, which is the 14 September draw
re-run that day with **zero verdicts moved** (`--sample` replays the exact draw,
so a change in the score cannot be the sample moving):

| ground truth says | n | refcheck warns at that severity | a notice of that **exact** nature appears |
|---|---:|---:|---:|
| retraction | 1,000 | **98.5%** | 98.5% |
| expression of concern | 400 | **99.0%** | 95.2% |
| correction | 349 | **100%** | 99.7% |

**Two columns, because one of them flatters the tool.** The left asks what a
reader cares about: am I warned, at least as loudly as the facts deserve. The
right asks whether the notice that actually exists is the one shown. They come
apart for expressions of concern — 396 papers are warned about but only 381 are
warned about *as* an expression of concern, because for the other 15 the paper
was later retracted outright and the retraction alone clears the bar. That is not
a miss for a reader, and it would be dishonest to report it as a hit for the
register.

**Corrections scoring 100% is not a contradiction of the 21% gap measured on
11 September.** Two things differ. That figure was Crossref *alone*, before the
second register existed in this tool — closing it is precisely what PubMed was
added for, and this is the controlled measurement of whether that worked. And the
populations are not the same: Retraction Watch catalogues the corrections that
reach its radar, which skew towards questioned conduct, not the routine erratum
that makes up most of PubMed's 260,790.

**The retraction row, in full — 1,000 draws, 999 distinct papers, seed 20260914:**

| the paper was published | n | refcheck says RETRACTED | says something milder | silent |
|---|---:|---:|---:|---:|
| pre-2000 | 200 | 99.5% | 0% | 0.5% |
| 2000–09 | 200 | 99.0% | 0% | 1.0% |
| 2010–14 | 200 | **100%** | 0% | 0% |
| 2015–19 | 200 | 94.0% | 0% | **6.0%** |
| 2020+ | 200 | **100%** | 0% | 0% |
| all | 1,000 | **98.5%** | 0% | 1.5% |

Nothing is reported as *milder* than it is, which is the failure that would
matter most: being told to check a number when you should be throwing the
citation out. The 15 misses are silence: ten of those papers are not in Crossref
at all — and **eight of the ten are the same journal**, `10.4314/jfas`, which is
an indexing gap rather than a scattering of bad luck — while the other five are
in Crossref with no notice attached to them, so neither register knew.

**The measurement paid for itself immediately, which is the point of running
one.** The first run scored 981. Four of its nineteen misses turned out not to be
missing: their publisher had redirected the DOI to the very notice that retracted
them, and Crossref's `filter=doi:` — the batch query this tool is built on —
cannot see a DOI that has been superseded, while `/works/<doi>` follows the alias
and answers fine. Those four papers were retracted and the report said *not found
in Crossref*. So every DOI the batch misses is now asked about again by name, and
the same 999 papers re-run on 2026-09-15 score **985, with zero regressions and
no other verdict moved**.

Re-running the identical sample is what makes that a controlled before/after
rather than two numbers: the CSV grows, so the same seed over a longer list draws
different papers. `--sample research/rw_gap_20260914.json` replays the exact draw,
which also means the figure can be reproduced from the JSON in this repo instead
of the 66 MB CSV.

**What the second look costs, measured rather than guessed:** one extra request
per DOI the batch did not find, paced at Crossref's 1/s. On the 1,000-reference
run that was 14 requests, so about 14 seconds. It is capped at 100 — a
bibliography of arXiv preprints is *all* misses, and none of them would be found
the second time either — and whatever the cap leaves out keeps the answer it had,
`not found, not checked`, with the number of skipped ones printed. `REFCHECK_SECOND_CHANCES`
raises the cap.

**What comes back is never passed off as the reference's own record.** The notice
is a different work with a different title; handing it over whole would print
"Retraction: …" as your paper's title with no notice attached, which is a
retracted paper reported clean — worse than the silence it replaced. Only the
entries that name your DOI are kept: FASEB's *Withdrawn abstracts* notice lists
42 of them, and 41 belong to somebody else. And if the record it moved to does
not say why, you are told it moved and nothing more, because "it now points
somewhere else" is not a verdict.

Two of those four, live, where yesterday both read `not found in Crossref`:

```
  3 reference(s) checked · 2 carry a change notice
  1 registered at DataCite, not Crossref — nothing is wrong
  with it, this tool just cannot speak for it

  RETRACTED — do not cite this as evidence
    Withdrawn abstracts, The FASEB Journal, issue 36:S1
    10.1096/fasebj.2022.36.s1.0i128
      → Retraction (2022-05-27): https://doi.org/10.1096/fsb2.22386
      This DOI no longer has a record of its own: Crossref sends it
      to 10.1096/fsb2.22386, which states it is the notice above.
      The title shown is that notice's.
```

### The one it gets wrong, and it cannot be fixed from here

Retraction Watch records a fourth nature: **`Reinstatement`** — a retraction that
was *reversed*. The paper stands. Measuring it needs the scoring turned round,
because here the right answer is silence and anything refcheck says is a false
alarm. There are only 155 such papers with a usable DOI, so this is the census,
not a sample.

| | n | |
|---|---:|---|
| quiet, as it should be | 105 | 67.7% |
| warns, milder notice only | 19 | often a real notice published *after* the paper was restored |
| **still says RETRACTED** | **31** | **20.0% — and this is the expensive way to be wrong** |

Thirty-one papers that stand today, and this tool tells you to throw the citation
out. Their own notes in the database are not ambiguous: *"Retracted in error and
reinstated"*, *"This article was incorrectly retracted"*, *"article reinstated on
unknown date with no explanation"*. Eleven of the 31 are `Retract and Replace`,
where a retracted version really was superseded by a corrected one; the rest were
simply restored.

**This is not a bug in refcheck, and saying so is not an excuse — it is the
finding.** Crossref has no `reinstatement` in its vocabulary of update types —
checked against the schema, not from memory: `cm_update_type` in
[`common5.3.1.xsd`](https://data.crossref.org/schemas/common5.3.1.xsd)
enumerates exactly twelve values, all twelve of which this tool handles, and none
of them undoes another. Publishers therefore cannot deposit the reversal as a
relation even if they want to. Take
`10.1080/21655979.2021.2005742`, retracted in error by Taylor & Francis and
reinstated. Crossref still serves one `updated-by`, a `retraction`, deposited by
the publisher. The notice restoring the paper exists — `10.1080/21655979.2024.2326361`
— and it is filed as a plain `journal-article` titled *"Publisher's Note"*, with
`update-to: null`. Nothing links it to the paper it rescues. **A checker built on
these two registers cannot see it, however well written.**

One case shows the shape of it from the other side.
`10.1007/s00404-012-2548-3` carries a 2024 correction stating the article is *not*
retracted — and Crossref has already dropped the retraction from its record.
PubMed has not. refcheck asks both and the graver answer wins, so the stale
register decides. That rule is still right: going quiet because one register
stopped talking is the more dangerous error, and it is the one fixed on
9 September. Here it costs.

**What was deliberately not done about it.** Not a warning on every `RETRACTED` —
31 papers against ~67,000 retractions is roughly one in two thousand, and a
caveat printed on all of them teaches people to skip the caveat, which is worse
than the problem. Not shipping the Retraction Watch CSV either: 66 MB to resolve
155 papers is not a trade worth making, and that was already decided on the 9th
for the same reason. What is here instead is the measured number, and the advice
that follows from it: **a `RETRACTED` verdict on a paper whose retraction you have
reason to doubt should be checked at
[retractiondatabase.org](https://retractiondatabase.org), which is the only one of
the three that records reversals.**

### And when only one of them answers, you are told that too

Asking two registers is worth nothing if a silent register can pass for a clean
one. Until 14 September 2026 it could, in both versions: when NCBI was
unreachable the code recorded the failure in a field, and then **nothing ever
printed it**. The run said `Nothing found`, exited `0`, and looked exactly like a
run where PubMed had answered and had nothing to report.

Three things changed, all of them measured by tests that fail against the
previous day's code:

- A reference only one register answered about is **named as half-checked**, in
  the report, in the copyable version of it, and on the page — not filed with the
  clean ones. The command-line version exits `2` for it.
- **One dead batch costs its own batch.** PubMed is asked 50 DOIs at a time, so a
  1,000-reference file is 20 batches and 40 requests; one transient `connection
  reset` used to reject the whole chain and throw away the second opinion on all
  1,000. On a home connection roughly one run in three loses a request somewhere.
- **A half answer is never cached**, in either version. See above.

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
- **Not a service that watches for you.** `--watch` compares this run against the
  last one; it is not a daemon, it has no server, and it will never email you.
  Nothing happens unless you run it — put the cron line above in your crontab and
  the scheduling is yours, on your machine, with your reading list.

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
python3 test_refcheck.py                  # 294 offline, 10 network cases skipped
REFCHECK_RED=1 python3 test_refcheck.py   # all 304, adding the live-API cases
```

"Offline" is checked rather than promised:

```
REFCHECK_SIN_RED=1 python3 test_refcheck.py   # urlopen raises; all 294 must pass
```

That caught two tests on 2026-09-15. A mocked batch that finds nothing now sends
every miss off to be asked about by name, so one of them was firing **285 real
requests** at `api.crossref.org` — invented misses, from the battery of a project
whose README asks people to be kind to that service — and reporting green while
it did. The tell was the clock: the offline run takes 0.2 s once it stops
secretly using the network, and it had been taking 29.

One of those live tests asserts that `10.1148/85.3.474` still arrives
contradictory. If Crossref fixes CR-2746 the test goes red — which is exactly
how I want to find out. Another asks NCBI for three real records — one with a
DOI, one from 1979 without, one that does not exist — so a change in the shape of
their answer surfaces as a failure rather than as a wrong report to a reader. A
third asserts that `10.1093/jnci/djr419` still reaches PubMed with two notices
and Crossref with none — if Crossref ever deposits them, that goes red too.

The browser version has its own battery — 193 checks driving the real page in
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

The MEDLINE checks in there do not read the report. They record **every request
the page makes** and then assert that a stranger's DOI was never asked about at
all — a report that looks right while quietly checking the wrong papers is the
failure that started this, so the test is written one level below the words.

The cache checks are written the same way: the claim is not that the second run
*looks* right, it is that it made **zero requests** and that the warm report is
line-for-line the cold one plus the line admitting where the answer came from.
And the one that matters most goes the other way — with NCBI down, PubMed must be
asked **again** on the next run, and the retraction that a cached half answer was
hiding must come out.

And one the battery was getting wrong until 2026-09-21, which is worth writing
down because the shape of the mistake is general. Several bars on the page are
shown and hidden with the `hidden` attribute, and the checks asked the DOM
whether `hidden` was set — the property the code itself sets. That check cannot
fail. Meanwhile `.loaded { display: flex }` is an author rule and the browser's
`[hidden] { display: none }` is a UA rule, so the author rule won: measured
against the deployed page, a 57-pixel grey bar with a button reading "Remove
this file" had been sitting there with no file loaded since 13 September, and a
screen reader had been announcing that button. The accessibility audit missed it
for the same reason. The checks now read the **computed style and the measured
height**, which is a question the code cannot answer by assertion.

## Licence

MIT. Use it, fork it, put it in your pipeline, no attribution needed.

Data from the [Crossref REST API](https://api.crossref.org). Please be kind to
it: it is a public good funded by nobody in particular.
