# refcheck

**Has anything you cite been quietly corrected?**

Retractions are the famous case, and they are well covered: Zotero warns you,
Retraction Watch keeps the list, and both are free. A retraction is also the
*rarest* kind of change to the scientific record.

I counted the rest against the Crossref API on 2026-09-06:

| change notice | registered | Zotero / Retraction Watch warns you |
|---|---:|:---:|
| retraction | 65,974 | yes |
| **correction** | **205,005** | **no** |
| **erratum** | **113,437** | **no** |
| **expression of concern** | **4,229** | **no** |
| **new edition** | **10,761** | **no** |
| **withdrawal / removal / addendum / clarification** | **5,733** | **no** |

**339,165 change notices — 5.1 times the retractions.** The tools most people
actually have will not mention them: Zotero's own documentation is explicit that
it "only shows actual retractions, not expressions of concern", and Retraction
Watch is, by name and by design, about retractions.

These are the quiet ones, and they are quiet for a reason: unlike a retraction,
the paper stays valid. Only a number moved. Nobody emails you to say that the
figure you built an argument on was corrected two years after you read it.

`refcheck` reads your bibliography and tells you which references carry a
published change notice, what kind, and where to read it.

## Use it

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

Exit code is `1` when something is found and `0` when nothing is, so it can gate
a CI job — a journal checking submissions, a lab checking a manuscript before it
goes out, a systematic review checking its own included studies.

**No installation, no account, no key.** One file, Python 3.9+, standard library
only. Set `REFCHECK_MAILTO=you@example.org` to identify yourself politely to
Crossref and get their faster pool.

## What else is out there

I checked before building, and then checked again afterwards and found something
I had missed — so here is the honest landscape:

- **[Zotero](https://www.zotero.org/) + [Retraction Watch](https://retractionwatch.com/)** —
  excellent, free, integrated into the tool most researchers already use.
  Retractions only.
- **[CiteGuard](https://github.com/lonexreb/cite-guard)** (`pip install retractguard`) —
  OpenAlex-native, and it *does* cover corrections and expressions of concern.
  If you want an institution-scale watchdog with a package behind it, look there
  first. I found it after publishing this, which says more about my search than
  about their work.
- **[agbarnett/retraction_watch](https://github.com/agbarnett/retraction_watch)** —
  a Shiny app for checking a BibTeX file. Retractions.
- **scite.ai** — commercial, and it does far more than this.

**What is different here:** one file, standard library, nothing to install and no
account, asking Crossref directly. You can drop it in a CI job or hand it to
someone who has never used `pip` and it will work. That is the whole claim.

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

## Tests

```
python3 test_refcheck.py              # 17 tests, offline
REFCHECK_RED=1 python3 test_refcheck.py   # plus the live-API cases
```

## Licence

MIT. Use it, fork it, put it in your pipeline, no attribution needed.

Data from the [Crossref REST API](https://api.crossref.org). Please be kind to
it: it is a public good funded by nobody in particular.
