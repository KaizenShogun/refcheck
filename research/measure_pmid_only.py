#!/usr/bin/env python3
"""Does asking PubMed by PMID matter, for references that have no DOI?

Until 2026-10-18 refcheck reported a reference cited by a PMID that PubMed
knows no DOI for as "no DOI, not checked". The reasoning was that Crossref is
indexed by DOI. True, and beside the point: PubMed's CommentsCorrectionsList is
built by NLM indexers and needs no DOI at all.

Before building anything, the question was whether this is a handful of papers
or hundreds. Ground truth is the Retraction Watch CSV: every row whose original
paper has a PMID and no DOI. Each one is then run through the code refcheck
ships — resuelve_pmids, then comprueba_sin_doi — and scored:

  * "PubMed has a DOI": refcheck already checked these by DOI. Not counted as
    a gain, because nothing changes for them.
  * "flagged, same nature": PubMed's record carries the notice RW lists
    (RetractionIn/PartialRetractionIn for a retraction, and so on).
  * "flagged, other notice": PubMed lists a different verdict notice.
  * "silent": PubMed answered and lists nothing — still a miss.
  * "not checked": the lookup failed. Reported, never folded into the others.

Before this change every row in the last four drawers was "not checked".

    python3 measure_pmid_only.py --csv /tmp/rw.csv --json pmid_only.json

MIT.
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import refcheck  # noqa: E402

NATURALEZA = {
    "Retraction": {"retraction", "partial_retraction"},
    "Expression of concern": {"expression_of_concern"},
    "Correction": {"erratum", "correction"},
}


def filas(ruta):
    csv.field_size_limit(10 ** 7)
    vistos = set()
    with open(ruta, encoding="utf-8", errors="replace") as fh:
        for f in csv.DictReader(fh):
            nat = (f.get("RetractionNature") or "").strip()
            if nat not in NATURALEZA:
                continue
            doi = (f.get("OriginalPaperDOI") or "").strip().lower()
            pmid = (f.get("OriginalPaperPubMedID") or "").strip()
            if doi.startswith("10.") or not pmid.isdigit() or int(pmid) == 0:
                continue
            if (nat, pmid) in vistos:
                continue
            vistos.add((nat, pmid))
            m = re.search(r"\b(1[89]|20)\d\d\b", f.get("OriginalPaperDate") or "")
            yield {"nat": nat, "pmid": pmid, "anno": m.group(0) if m else ""}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--json")
    a = p.parse_args()
    casos = list(filas(a.csv))
    pmids = sorted({c["pmid"] for c in casos})
    print("RW rows with a PMID and no DOI: %d (%d distinct PMIDs)" % (len(casos), len(pmids)))
    resueltos = refcheck.resuelve_pmids(pmids)
    sueltos = []
    for pmid, r in resueltos.items():
        if r["estado"] == "sin_doi":
            sueltos.append({"doi": "", "pmid": pmid, "estado": "pmid_sin_doi",
                            "titulo": r.get("titulo", ""), "fecha": "", "avisos": []})
    refcheck.comprueba_sin_doi(sueltos)
    por_pmid = {s["pmid"]: s for s in sueltos}

    tabla = collections.Counter()
    filas_salida = []
    for c in casos:
        r = resueltos.get(c["pmid"], {"estado": "?"})
        if r["estado"] == "ok":
            cajon = "PubMed has a DOI (already checked by DOI)"
        elif r["estado"] == "desconocido":
            cajon = "PMID not in PubMed"
        elif r["estado"] != "sin_doi":
            cajon = "not checked (esummary failed)"
        else:
            s = por_pmid[c["pmid"]]
            if s["estado"] != "ok":
                cajon = "not checked (efetch failed)"
            else:
                tipos = {x["tipo"] for x in s["avisos"]}
                if tipos & NATURALEZA[c["nat"]]:
                    cajon = "flagged, same nature"
                elif tipos:
                    cajon = "flagged, other notice"
                else:
                    cajon = "silent"
        tabla[(c["nat"], cajon)] += 1
        filas_salida.append(dict(c, cajon=cajon))

    for nat in NATURALEZA:
        tot = sum(v for (n, _), v in tabla.items() if n == nat)
        print("\n%s (%d)" % (nat, tot))
        for (n, cajon), v in sorted(tabla.items()):
            if n == nat:
                print("  %-45s %4d" % (cajon, v))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"csv": os.path.basename(a.csv), "filas": filas_salida,
                       "tabla": {"%s|%s" % k: v for k, v in tabla.items()}},
                      f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
