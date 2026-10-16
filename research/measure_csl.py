"""CSL-JSON: loose-text path vs. the record reader, on real reference lists.

Ground truth per record is the record's own `DOI` / `PMID` fields (or, for a
record with neither, nothing to check). Both readers are scored against it:

  · lost_doi       — a record DOI the reader did not return
  · lost_pmid_only — a record known only by PMID whose PMID the reader dropped
  · invented       — a DOI returned that is no record's own DOI field
  · invisible      — a record with no identifier the report never mentions

Usage: python3 -I research/measure_csl.py CORPUS_DIR [--out JSON]
No network unless --verify: the PMID → DOI round trip is not exercised, only
extraction.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import refcheck  # noqa: E402


def mide(ruta):
    texto = open(ruta, encoding="utf-8").read()
    items = json.loads(texto)
    propios = {x["DOI"].strip().lower() for x in items if isinstance(x.get("DOI"), str) and x["DOI"].strip()}
    solo_pmid = {str(int(x["PMID"])) for x in items
                 if not x.get("DOI") and str(x.get("PMID", "")).strip().isdigit()}
    sin_id = sum(1 for x in items if not x.get("DOI") and not x.get("PMID"))

    # loose text: what referencias_de did before this reader existed
    t_dois = {d.lower() for d in refcheck.dois_de(texto)}
    t_pmids = set(refcheck.pmids_de(texto))
    texto_r = {
        "lost_doi": len(propios - t_dois),
        "lost_pmid_only": len(solo_pmid - t_pmids),
        "invisible": sin_id,
    }

    regs = refcheck.registros_csl(texto)
    assert len(regs) == len(items), ruta
    r_dois = {r["doi"].lower() for r in regs if r["doi"]}
    # A DOI the reader took from URL or a `DOI:` note line of a record whose
    # DOI field is empty. Not counted as right or wrong here: --verify asks
    # Crossref for its title and compares it with the record's own.
    rescatados = [(r["doi"], x.get("title", "")) for r, x in zip(regs, items)
                  if r["doi"] and not x.get("DOI")]
    r_pmids = {r["pmid"] for r in regs if r["pmid"] and not r["doi"]}
    sin_nada = sum(1 for r in regs if not r["doi"] and not r["pmid"])
    # Same yardstick for both sides: a DOI from a record with no DOI field is
    # not "invented" by either reader (on 2026-10-16 all of them matched by title).
    rescate = {d.lower() for d, _ in rescatados}
    texto_r["invented"] = sorted(t_dois - propios - rescate)
    lector = {
        "lost_doi": len(propios - r_dois),
        "lost_pmid_only": len(solo_pmid - r_pmids),
        "invented": sorted(r_dois - propios - {d.lower() for d, _ in rescatados}),
        "rescued": [{"doi": d, "title": t} for d, t in rescatados],
        # every record comes back as a row; the ones with no id are reported
        # as "no identifier", so none is invisible
        "invisible": 0,
        "reported_without_id": sin_nada,
    }
    return {"file": os.path.basename(ruta),
            "sha256": hashlib.sha256(texto.encode()).hexdigest(),
            "records": len(items), "with_doi": len(propios),
            "pmid_only": len(solo_pmid), "no_id": sin_id,
            "loose_text": texto_r, "reader": lector}


def _norma(t):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())


def verifica(filas):
    """Title of each rescued DOI per its registration agency, vs. the record."""
    out = []
    for f in filas:
        for r in f["reader"]["rescued"]:
            req = urllib.request.Request("https://doi.org/" + r["doi"], headers={
                "Accept": "application/vnd.citationstyles.csl+json",
                "User-Agent": "refcheck-measure (https://github.com/KaizenShogun/refcheck)"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    titulo = json.load(resp).get("title", "")
            except Exception as e:  # noqa: BLE001 - reported, not hidden
                titulo = "ERROR " + str(e)
            if isinstance(titulo, list):
                titulo = titulo[0] if titulo else ""
            a, b = _norma(titulo), _norma(r["title"])
            out.append({"doi": r["doi"], "record_title": r["title"], "doi_title": titulo,
                        "same": bool(a) and bool(b) and (a in b or b in a)})
            time.sleep(1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--out")
    ap.add_argument("--verify", action="store_true",
                    help="ask Crossref the title of each rescued DOI")
    a = ap.parse_args()
    filas = [mide(f) for f in sorted(glob.glob(os.path.join(a.corpus, "*.json")))]
    tot = {k: sum(f[k] for f in filas) for k in ("records", "with_doi", "pmid_only", "no_id")}
    for lado in ("loose_text", "reader"):
        tot[lado] = {
            "lost_doi": sum(f[lado]["lost_doi"] for f in filas),
            "lost_pmid_only": sum(f[lado]["lost_pmid_only"] for f in filas),
            "invented": sum(len(f[lado]["invented"]) for f in filas),
            "rescued": sum(len(f[lado].get("rescued", [])) for f in filas),
            "invisible": sum(f[lado]["invisible"] for f in filas),
        }
    print(json.dumps(tot, indent=1))
    for f in filas:
        for lado in ("loose_text", "reader"):
            if f[lado]["invented"]:
                print(f["file"], lado, "invented:", f[lado]["invented"])
    if a.verify:
        tot["reader"]["rescued_verified"] = verifica(filas)
    if a.out:
        json.dump({"totals": tot, "files": filas}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
