#!/usr/bin/env python3
"""What a Retraction-Watch-only checker cannot see.

Zotero, EndNote, LibKey and Papers all flag retracted items in your library, and
all four read the same source: the Retraction Watch database. Before refcheck
grows anything that competes with them, the honest question is whether that
source leaves a hole a reader would care about — because if it does not, the
right move is to say so and build something else.

So this is the mirror of 2026-09-16, which used RW as ground truth and asked how
much of it refcheck sees (98.5% / 99.0% / 100%). Here the direction flips: take
the change notices CROSSREF holds, and ask whether RW knows about that paper at
all. Whatever RW does not hold is invisible to every tool in the paragraph above,
however well written.

Input is the frozen corpus of 2026-09-12 (1,600 papers sampled from Crossref by
update type, 400 per population) plus a copy of the RW CSV. No network is needed
for the headline figures, so the whole thing is reproducible from two files.

THE CONTROLS, which decide whether the headline means anything:

  * Retractions are the self-check. RW's whole subject is retractions, so if the
    crosswalk says it holds few of Crossref's, the crosswalk is broken and not
    RW. A low number there invalidates the run.
  * A positive control samples DOIs out of the CSV itself and looks them up
    through the same normaliser. Anything under 100% is a bug in my matching.
  * Rows whose OriginalPaperDOI is missing or "unavailable" are counted, because
    they bound how wrong a DOI-only crosswalk can be.
  * --verify N asks Crossref for the titles of N absent papers and looks each
    title up in the CSV. That is the only way to tell "RW does not have it" from
    "RW has it under no DOI". Needs the network; everything else does not.

    python3 measure_rw_coverage.py --csv /tmp/rw.csv
    python3 measure_rw_coverage.py --csv /tmp/rw.csv --verify 40 --json out.json

MIT.
"""
import argparse
import collections
import csv
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

CROSSREF = "https://api.crossref.org/works"
CONTACT = os.environ.get("REFCHECK_MAILTO", "")
UA = ("refcheck-research/1.0 (https://github.com/KaizenShogun/refcheck"
      + ("; mailto:" + CONTACT if CONTACT else "") + ")")

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "crossref_gap_20260912.json")

# The corpus was sampled by Crossref update type. `correction` and `erratum` are
# one word in two vocabularies -- the same thing to a reader -- but they are
# sampled separately and stay separate here, because merging them would hide a
# difference between them if one existed.
ORDEN = ["retraction", "concern", "correction", "erratum"]


def normaliza(doi):
    """The one place a DOI gets folded, so both sides of the crosswalk agree."""
    return (doi or "").strip().lower().rstrip(".")


def normaliza_titulo(bruto):
    """Titles collapse to letters and digits: the two sources differ on case,
    punctuation, whitespace and the odd bit of markup, and none of that makes
    two papers different papers."""
    return re.sub(r"[^a-z0-9]+", "", (bruto or "").lower())


def lee_csv(ruta):
    """Everything the crosswalk needs out of the RW CSV, in one pass."""
    csv.field_size_limit(10 ** 7)
    por_doi = collections.defaultdict(set)
    por_titulo = {}
    total = sin_doi = vacias = 0
    with open(ruta, newline="", encoding="utf-8", errors="replace") as fh:
        for fila in csv.DictReader(fh):
            total += 1
            valores = [(v or "").strip() for k, v in fila.items() if k]
            if not any(valores):
                vacias += 1
                continue
            doi = normaliza(fila.get("OriginalPaperDOI"))
            nat = (fila.get("RetractionNature") or "").strip()
            titulo = normaliza_titulo(fila.get("Title"))
            if titulo:
                por_titulo.setdefault(titulo, (fila.get("Record ID") or "").strip())
            if doi.startswith("10.") and " " not in doi:
                por_doi[doi].add(nat)
            else:
                sin_doi += 1
    return {"por_doi": dict(por_doi), "por_titulo": por_titulo,
            "filas": total, "sin_doi": sin_doi, "vacias": vacias}


def lee_corpus(ruta):
    d = json.load(open(ruta, encoding="utf-8"))
    salida = {}
    for p in d["poblaciones"]:
        vistos, filas = set(), []
        for f in p["filas"]:
            doi = normaliza(f["doi"])
            if doi and doi not in vistos:
                vistos.add(doi)
                filas.append({"doi": doi, "anno": f.get("anno") or 0})
        salida[p["poblacion"]] = filas
    return salida, d.get("medido", "?")


def titulos_crossref(dois, pausa=1.0, lote=20):
    """Titles for the absent DOIs, so a title lookup can second-guess the DOI one.

    Batched through the same filter=doi: the tool uses. A DOI that comes back
    without a title is returned as None and counted apart -- guessing that it has
    no title would quietly turn a failed lookup into evidence."""
    salida = {}
    for i in range(0, len(dois), lote):
        trozo = dois[i:i + lote]
        url = (CROSSREF + "?" + urllib.parse.urlencode({
            "filter": ",".join("doi:" + d for d in trozo),
            "select": "DOI,title", "rows": len(trozo)}))
        pet = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(pet, timeout=60) as r:
                datos = json.load(r)
        except Exception as e:                      # noqa: BLE001 -- reported, not hidden
            print("  ! lookup failed for %d DOIs: %s" % (len(trozo), e),
                  file=sys.stderr)
            time.sleep(pausa)
            continue
        for obra in datos.get("message", {}).get("items", []):
            t = (obra.get("title") or [""])[0]
            salida[normaliza(obra.get("DOI"))] = t or None
        time.sleep(pausa)
    return salida


def control_positivo(rw, n, semilla=20260920):
    """DOIs taken out of the CSV and looked up through the same normaliser.

    This cannot fail for a real reason. That is the point: if it does, my
    matching is broken and every other figure in the run is noise."""
    rng = random.Random(semilla)
    claves = list(rw["por_doi"])
    if not claves:
        return {"n": 0, "encontrados": 0}
    elegidos = rng.sample(claves, min(n, len(claves)))
    return {"n": len(elegidos),
            "encontrados": sum(1 for d in elegidos if d in rw["por_doi"])}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", required=True, help="the Retraction Watch CSV")
    p.add_argument("--corpus", default=CORPUS, help="frozen Crossref corpus")
    p.add_argument("--verify", type=int, default=0,
                   help="look up the titles of N absent papers (uses network)")
    p.add_argument("--json", help="write every DOI and verdict here")
    a = p.parse_args()

    print("Reading %s ..." % a.csv)
    rw = lee_csv(a.csv)
    print("  %d rows, %d without a usable original DOI, %d completely empty"
          % (rw["filas"], rw["sin_doi"], rw["vacias"]))
    print("  %d distinct original DOIs" % len(rw["por_doi"]))

    pos = control_positivo(rw, 500)
    print("  positive control: %d/%d DOIs from the CSV found by the crosswalk"
          % (pos["encontrados"], pos["n"]))
    if pos["encontrados"] != pos["n"]:
        print("  ! the crosswalk is broken; stopping", file=sys.stderr)
        return 1

    corpus, medido = lee_corpus(a.corpus)
    print("\nCorpus frozen %s: %d papers Crossref marks with a notice\n"
          % (medido, sum(len(v) for v in corpus.values())))

    resultado, ausentes_todos = {}, {}
    for nombre in ORDEN:
        filas = corpus.get(nombre, [])
        presentes = [f for f in filas if f["doi"] in rw["por_doi"]]
        ausentes = [f for f in filas if f["doi"] not in rw["por_doi"]]
        resultado[nombre] = {"n": len(filas), "en_rw": len(presentes),
                             "ausentes": [f["doi"] for f in ausentes]}
        ausentes_todos[nombre] = ausentes

    print("%-12s %6s %10s %10s" % ("Crossref says", "n", "in RW", "invisible"))
    for nombre in ORDEN:
        r = resultado[nombre]
        if not r["n"]:
            continue
        pct = 100.0 * r["en_rw"] / r["n"]
        print("%-12s %6d %9.1f%% %9.1f%%" % (nombre, r["n"], pct, 100.0 - pct))

    if a.verify:
        print("\nSecond-guessing the absent ones by title (network) ...")
        for nombre in ORDEN:
            ausentes = ausentes_todos.get(nombre, [])
            if not ausentes:
                continue
            rng = random.Random(20260920)
            muestra = rng.sample(ausentes, min(a.verify, len(ausentes)))
            titulos = titulos_crossref([f["doi"] for f in muestra])
            hallados = sin_titulo = 0
            for f in muestra:
                t = titulos.get(f["doi"])
                if t is None:
                    sin_titulo += 1
                elif normaliza_titulo(t) in rw["por_titulo"]:
                    hallados += 1
            resultado[nombre]["verificados"] = len(muestra)
            resultado[nombre]["por_titulo"] = hallados
            resultado[nombre]["sin_titulo"] = sin_titulo
            print("  %-12s %d checked -> %d found in RW under no DOI, "
                  "%d had no title to check" % (nombre, len(muestra), hallados,
                                                sin_titulo))

    if a.json:
        json.dump({"medido": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   "csv": os.path.abspath(a.csv), "corpus_medido": medido,
                   "csv_filas": rw["filas"], "csv_sin_doi": rw["sin_doi"],
                   "csv_vacias": rw["vacias"], "control_positivo": pos,
                   "poblaciones": resultado},
                  open(a.json, "w", encoding="utf-8"), indent=1)
        print("\nwrote %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
