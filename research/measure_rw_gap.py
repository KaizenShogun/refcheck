#!/usr/bin/env python3
"""The third blind spot: what does Retraction Watch know that refcheck misses?

The two earlier scripts measured the two registers against each other — Crossref
against PubMed, then PubMed against Crossref. Both are indirect. Neither asks the
question a reader actually cares about, which is not "do these two agree" but:

    given a paper the reference standard says was RETRACTED, does refcheck
    say so?

The Retraction Watch database is that reference standard. It is maintained by
people whose whole job is finding these notices, it is CC-BY, and Crossref
republishes it as a CSV. So it can be used as ground truth instead of as a third
opinion, and the number that comes out is the one that belongs in the README:
the share of known retractions this tool surfaces.

The distinction that decides how to read the result. A retraction reported as
`CORRECTED` is not the same failure as a retraction reported as nothing at all.
The first is a reader who is told to check a number when they should be throwing
the citation out; the second is a reader told the citation is clean. Both are
counted, separately.

Why this is not circular. Crossref ingests the RW feed, so in principle Crossref
should already carry every row — which is exactly why it is worth measuring
rather than assuming. Where it holds, the result is a positive claim nobody has
published; where it does not, it is a bug in what refcheck tells people.

Sampling. Stratified by the ORIGINAL paper's year, because deposit practice has
improved a lot and a uniform draw would be dominated by recent papers and would
flatter the answer. Each era is drawn at random with a seed, so a run repeats.

Standard library only, no key. Runs through refcheck's own functions rather than
a reimplementation — the point is to measure the tool, not something that
resembles it. Crossref allows 1 request/second without a mailto and NCBI 3;
refcheck's own pacing is what governs here. Set REFCHECK_MAILTO to be polite.

    python3 measure_rw_gap.py --csv retraction_watch.csv
    python3 measure_rw_gap.py --csv retraction_watch.csv --n 60 --json out.json

The CSV is the one Crossref publishes, ~66 MB:
https://gitlab.com/crossref/retraction-watch-data

MIT.
"""
import argparse
import collections
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import refcheck  # noqa: E402

# Only the gravest rows. "Retraction" is the one nature where a miss is
# unambiguous: the paper is gone and a reader citing it is citing nothing. The
# milder natures are worth a separate run, but mixing them in would let a good
# score on corrections hide a bad one on retractions.
NATURALEZA = "Retraction"

# Eras by the ORIGINAL paper's year, not the notice's. A 1994 paper retracted
# last week is a 1994 deposit problem: the record that has to carry the notice
# is the old one.
ERAS = [("pre-2000", 0, 1999), ("2000-09", 2000, 2009), ("2010-14", 2010, 2014),
        ("2015-19", 2015, 2019), ("2020+", 2020, 9999)]


def anno(bruto):
    """Year out of the CSV's `M/D/YYYY 0:00` dates. Empty if it is not there."""
    for trozo in (bruto or "").replace("/", " ").replace("-", " ").split():
        if len(trozo) == 4 and trozo.isdigit():
            return int(trozo)
    return 0


def filas(ruta):
    """Rows with a usable original DOI and the nature we are measuring."""
    csv.field_size_limit(10 ** 7)
    salida = []
    with open(ruta, newline="", encoding="utf-8", errors="replace") as fh:
        for fila in csv.DictReader(fh):
            doi = (fila.get("OriginalPaperDOI") or "").strip().lower()
            nat = (fila.get("RetractionNature") or "").strip()
            # "unavailable" is what the CSV writes when there is no DOI to give.
            # Those rows are real retractions but they are outside what a DOI
            # checker can be asked about at all, so they are excluded and
            # counted rather than scored as misses.
            if nat != NATURALEZA or not doi.startswith("10.") or " " in doi:
                continue
            salida.append({"doi": doi, "record": (fila.get("Record ID") or "").strip(),
                           "anno": anno(fila.get("OriginalPaperDate")),
                           "titulo": (fila.get("Title") or "").strip()[:120],
                           "fecha_retractacion": (fila.get("RetractionDate") or "").strip()})
    return salida


def muestra(todas, n, semilla):
    rng = random.Random(semilla)
    por_era = collections.defaultdict(list)
    for f in todas:
        for nombre, lo, hi in ERAS:
            if lo <= f["anno"] <= hi:
                por_era[nombre].append(f)
                break
    elegidas = []
    for nombre, _, _ in ERAS:
        grupo = por_era.get(nombre, [])
        if grupo:
            elegidas += rng.sample(grupo, min(n, len(grupo)))
    return elegidas


def veredicto(r):
    """What refcheck ends up telling the reader about this DOI."""
    if r["estado"] == "sin_comprobar":
        return "no comprobado"          # lookup failed; not an answer either way
    if not r["avisos"]:
        return ("silencio, y ni siquiera tiene el DOI" if r["estado"] == "desconocido"
                else "silencio")
    return "retractado" if max(a["gravedad"] for a in r["avisos"]) >= 3 else "mas suave"


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", help="the Retraction Watch CSV")
    p.add_argument("--n", type=int, default=80, help="sampled per era (default 80)")
    p.add_argument("--seed", type=int, default=20260914)
    p.add_argument("--json", help="write every sampled DOI and its verdict here")
    p.add_argument("--sample", help="re-run an earlier --json instead of sampling "
                                    "afresh: same papers, same ground truth, "
                                    "today's code")
    a = p.parse_args()

    if a.sample:
        # Re-running the exact sample is what turns a number into a controlled
        # before/after. Sampling again with the same seed would not do it: the
        # CSV grows, so the same seed over a longer list draws different papers,
        # and a change in the score could then be the sample moving rather than
        # the code. It also means anyone can reproduce the published figure from
        # the 200 kB of JSON in this repo instead of the 66 MB CSV.
        with open(a.sample, encoding="utf-8") as f:
            previo = json.load(f)
        elegidas = [{k: v for k, v in fila.items()
                     if k not in ("veredicto", "registro")}
                    for fila in previo["rows"]]
        print(f"re-running the sample in {a.sample}: {len(elegidas)} papers, "
              f"drawn with seed {previo.get('seed')}\n")
    elif a.csv:
        todas = filas(a.csv)
        print(f"rows in the CSV with nature {NATURALEZA!r} and a real DOI: {len(todas)}")
        elegidas = muestra(todas, a.n, a.seed)
        print(f"sampled: {len(elegidas)} across {len(ERAS)} eras\n")
    else:
        p.error("need --csv to sample, or --sample to re-run an earlier one")

    dois = [f["doi"] for f in elegidas]
    hecho = [0]

    def avisa(n, total):
        if n != hecho[0]:
            hecho[0] = n
            print(f"\r  Crossref {n}/{total}", end="", file=sys.stderr, flush=True)

    resultados = refcheck.revisa_lote(dois, avisa=avisa)
    print("\r  Crossref done            ", file=sys.stderr)
    refcheck.fusiona_pubmed(resultados, avisa=lambda n, t: print(
        f"\r  PubMed {n}/{t}", end="", file=sys.stderr, flush=True))
    print("\r  PubMed done            ", file=sys.stderr)

    por_doi = {r["doi"].lower(): r for r in resultados}
    cuenta = collections.Counter()
    por_era = collections.defaultdict(collections.Counter)
    detalle = []
    for f in elegidas:
        r = por_doi.get(f["doi"])
        v = veredicto(r) if r else "no comprobado"
        # Which register supplied the notice, for the ones that were caught.
        quien = ""
        if r and r["avisos"]:
            fuentes = {("pubmed" if a.get("fuente") == "pubmed" else "crossref")
                       for a in r["avisos"] if a["gravedad"] >= 3} or \
                      {("pubmed" if a.get("fuente") == "pubmed" else "crossref")
                       for a in r["avisos"]}
            quien = "+".join(sorted(fuentes))
        cuenta[v] += 1
        era = next(n for n, lo, hi in ERAS if lo <= f["anno"] <= hi)
        por_era[era][v] += 1
        detalle.append({**f, "veredicto": v, "registro": quien})

    total = sum(cuenta.values())
    comprobados = total - cuenta["no comprobado"]
    print(f"\n{NATURALEZA}s the Retraction Watch database knows, "
          f"as refcheck reports them ({comprobados} looked up):\n")
    for v in ("retractado", "mas suave", "silencio",
              "silencio, y ni siquiera tiene el DOI", "no comprobado"):
        if cuenta[v]:
            pc = 100 * cuenta[v] / comprobados if comprobados and v != "no comprobado" else 0
            print(f"  {v:38s} {cuenta[v]:5d}" + (f"  {pc:5.1f}%" if pc else ""))

    print("\nby the original paper's era:")
    print(f"  {'':10s} {'n':>5s} {'says RETRACTED':>16s} {'milder':>8s} {'silent':>8s}")
    for nombre, _, _ in ERAS:
        c = por_era[nombre]
        n = sum(c.values()) - c["no comprobado"]
        if not n:
            continue
        mudo = c["silencio"] + c["silencio, y ni siquiera tiene el DOI"]
        print(f"  {nombre:10s} {n:5d} {100*c['retractado']/n:15.1f}% "
              f"{100*c['mas suave']/n:7.1f}% {100*mudo/n:7.1f}%")

    fallos = [d for d in detalle if d["veredicto"].startswith("silencio")
              or d["veredicto"] == "mas suave"]
    if fallos:
        print(f"\nthe ones refcheck does not call a retraction ({len(fallos)}):")
        for d in fallos[:40]:
            print(f"  {d['doi']:42s} {d['anno']}  {d['veredicto']}")
            print(f"    RW #{d['record']}  {d['titulo']}")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"nature": NATURALEZA, "n_per_era": a.n,
                       "seed": previo.get("seed") if a.sample else a.seed,
                       "rerun_of": a.sample or None,
                       "counts": dict(cuenta), "rows": detalle}, fh, indent=1)
        print(f"\nwritten: {a.json}")


if __name__ == "__main__":
    main()
