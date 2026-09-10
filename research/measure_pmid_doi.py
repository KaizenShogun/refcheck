#!/usr/bin/env python3
"""How many PubMed records actually carry a DOI? Measured, not assumed.

refcheck answers one question — "does this reference carry a published change
notice?" — and it can only answer it through Crossref, which is indexed by DOI.
Biomedical bibliographies are full of PMIDs and often carry no DOI at all, so
refcheck has to translate PMID → DOI before it can look anything up.

That translation is not free of holes, and the size of the hole decides how the
tool must behave. If a PubMed record has no DOI, refcheck cannot check it, and
the only honest thing to print is "not checked" — never silence, which a reader
reads as "clean".

Method: sample random PMIDs from four ranges that stand in for four eras, ask
NCBI's esummary for each batch, and count (a) how many of the sampled ids exist
at all, (b) how many of the existing ones list a DOI in `articleids`.

    python3 measure_pmid_doi.py            # 400 ids per era
    python3 measure_pmid_doi.py --n 100    # quicker

No API key needed. NCBI allows 3 requests/second without one; this stays under.
MIT, same as the rest of the repository.
"""
import argparse
import json
import random
import sys
import time
import urllib.parse
import urllib.request

ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
LOTE = 100          # ids per request; keeps the GET URL under ~1 kB
PAUSA = 0.4         # 2.5 req/s, under NCBI's stated 3/s for anonymous callers
UA = "refcheck-research/1.0 (https://github.com/KaizenShogun/refcheck)"

# PMIDs are assigned roughly in order, so the id range is a usable proxy for the
# era of the record. The labels are approximate on purpose.
ERAS = [
    ("1–5M        (roughly pre-1990)", 1, 5_000_000),
    ("5–15M       (roughly 1990–2005)", 5_000_000, 15_000_000),
    ("15–28M      (roughly 2005–2017)", 15_000_000, 28_000_000),
    ("28–40M      (roughly 2017–today)", 28_000_000, 40_000_000),
]


def esummary(pmids, reintentos=3):
    """Return {pmid: record} for the ids PubMed actually holds."""
    url = ESUMMARY + "?" + urllib.parse.urlencode(
        {"db": "pubmed", "retmode": "json", "id": ",".join(str(p) for p in pmids)})
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                datos = json.load(r).get("result", {})
            salida = {}
            for uid in datos.get("uids", []):
                rec = datos.get(uid) or {}
                # A requested id that does not exist comes back with an `error`.
                if not rec.get("error"):
                    salida[str(uid)] = rec
            return salida
        except Exception as e:
            if intento == reintentos - 1:
                raise
            time.sleep(2 ** intento)
    return {}


def doi_de(rec):
    for a in rec.get("articleids", []):
        if a.get("idtype") == "doi" and a.get("value"):
            return a["value"]
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--n", type=int, default=400, help="ids sampled per era")
    p.add_argument("--seed", type=int, default=20260909, help="for reproducibility")
    a = p.parse_args()

    rnd = random.Random(a.seed)
    print(f"Sampling {a.n} random PMIDs per era, seed {a.seed}\n")
    print(f"{'range':34s} {'exist':>7s} {'with DOI':>9s} {'share':>7s}")
    print("-" * 60)

    tot_exist = tot_doi = 0
    sin_doi_ejemplos = []
    for etiqueta, lo, hi in ERAS:
        muestra = rnd.sample(range(lo, hi), a.n)
        existen = con_doi = 0
        for i in range(0, len(muestra), LOTE):
            trozo = muestra[i:i + LOTE]
            recs = esummary(trozo)
            existen += len(recs)
            for pmid, rec in recs.items():
                if doi_de(rec):
                    con_doi += 1
                elif len(sin_doi_ejemplos) < 5:
                    sin_doi_ejemplos.append((pmid, rec.get("pubdate", "?"),
                                             (rec.get("title") or "")[:50]))
            time.sleep(PAUSA)
        cuota = f"{100 * con_doi / existen:.1f}%" if existen else "—"
        print(f"{etiqueta:34s} {existen:7d} {con_doi:9d} {cuota:>7s}")
        tot_exist += existen
        tot_doi += con_doi

    print("-" * 60)
    cuota = f"{100 * tot_doi / tot_exist:.1f}%" if tot_exist else "—"
    print(f"{'all four':34s} {tot_exist:7d} {tot_doi:9d} {cuota:>7s}")
    print(f"\n{tot_exist - tot_doi} of the sampled records carry no DOI at all.")
    print("For those, refcheck has nothing to ask Crossref about, and must say so.")
    if sin_doi_ejemplos:
        print("\nExamples with no DOI:")
        for pmid, fecha, titulo in sin_doi_ejemplos:
            print(f"  PMID {pmid:>9s}  {fecha:12s}  {titulo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
