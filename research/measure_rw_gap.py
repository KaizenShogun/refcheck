#!/usr/bin/env python3
"""The third blind spot: what does Retraction Watch know that refcheck misses?

The two earlier scripts measured the two registers against each other — Crossref
against PubMed, then PubMed against Crossref. Both are indirect. Neither asks the
question a reader actually cares about, which is not "do these two agree" but:

    given a paper the reference standard says carries a notice, does refcheck
    say so?

The Retraction Watch database is that reference standard. It is maintained by
people whose whole job is finding these notices, it is CC-BY, and Crossref
republishes it as a CSV. So it can be used as ground truth instead of as a third
opinion, and the number that comes out is the one that belongs in the README:
the share of known notices this tool surfaces.

WHY THE NATURE IS A PARAMETER, AND NOT A CONSTANT ANY MORE
==========================================================
Until 2026-09-16 this script only ever measured `Retraction`, because that is
the nature where a miss is unambiguous. That left the milder natures unmeasured
against ground truth — and those are exactly the ones the two registers handle
worst (21% and 15.3% mutual blind spots, measured on the 11th and 12th).

Generalising is not a matter of changing one string, because the natures do not
all score the same way:

  Retraction / Expression of concern / Correction — ground truth says a notice
      exists, so a hit is refcheck saying something at least that grave, and the
      failure is silence.

  Reinstatement — ground truth says a retraction was REVERSED. The paper stands.
      Here a hit is refcheck KEEPING QUIET, and shouting is the failure. It is
      the same direction of error as the bug found on 2026-09-09: telling a
      reader to throw away a citation that was never withdrawn. Scoring it like
      the others would grade the tool on doing precisely the wrong thing.

TWO FIGURES, NOT ONE
====================
`surfaced` asks whether the reader is warned at the expected severity. That is
the number that matters to a reader, but it flatters the tool: a paper with both
a retraction and a correction counts the correction as caught, because the
retraction alone clears the bar.

`exact` asks whether a notice of that actual nature appears. It is the stricter
question and the honest one for the mild natures — for an expression of concern,
`surfaced` counts a retraction as a hit, and those are not the same fact.

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
Small natures are better measured whole: `--all` takes the census instead, which
is what Reinstatement (160 rows) gets — there is nothing to sample.

Standard library only, no key. Runs through refcheck's own functions rather than
a reimplementation — the point is to measure the tool, not something that
resembles it. Crossref allows 1 request/second without a mailto and NCBI 3;
refcheck's own pacing is what governs here. Set REFCHECK_MAILTO to be polite.

    python3 measure_rw_gap.py --csv retraction_watch.csv
    python3 measure_rw_gap.py --csv retraction_watch.csv --nature "Correction"
    python3 measure_rw_gap.py --csv retraction_watch.csv --nature Reinstatement --all
    python3 measure_rw_gap.py --sample rw_gap_20260914.json

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

# The severity refcheck has to reach for the notice to count as surfaced, and
# the notice types that are that nature said in refcheck's own vocabulary.
#
# `esperado: None` marks the natures where ground truth says there is nothing to
# warn about, so the scoring reads the other way round. Keeping it in the same
# table rather than in a branch elsewhere is deliberate: the day someone adds a
# nature, the question "which direction does this one score in?" is unavoidable.
NATURALEZAS = {
    "Retraction": {
        "esperado": 3,
        "tipos": {"retraction", "partial_retraction", "removal", "withdrawal"},
    },
    "Expression of concern": {
        "esperado": 2,
        "tipos": {"expression_of_concern"},
    },
    "Correction": {
        "esperado": 1,
        "tipos": {"correction", "erratum", "corrigendum"},
    },
    "Reinstatement": {
        # The retraction was withdrawn; the paper stands. Nothing to say is the
        # right answer, and anything refcheck says here is a false alarm.
        "esperado": None,
        "tipos": set(),
    },
}

# Eras by the ORIGINAL paper's year, not the notice's. A 1994 paper retracted
# last week is a 1994 deposit problem: the record that has to carry the notice
# is the old one.
ERAS = [("pre-2000", 0, 1999), ("2000-09", 2000, 2009), ("2010-14", 2010, 2014),
        ("2015-19", 2015, 2019), ("2020+", 2020, 9999)]

# What the old runs wrote before the nature became a parameter. Kept so that
# --sample can re-run a 2026-09-14/15 file and still say whether a verdict moved
# — a before/after that cannot compare the labels is not a control.
VIEJOS = {"retractado": "avisado"}

ORDEN = ["avisado", "mas suave", "silencio",
         "silencio, y ni siquiera tiene el DOI", "no comprobado"]


def anno(bruto):
    """Year out of the CSV's `M/D/YYYY 0:00` dates. Empty if it is not there."""
    for trozo in (bruto or "").replace("/", " ").replace("-", " ").split():
        if len(trozo) == 4 and trozo.isdigit():
            return int(trozo)
    return 0


def filas(ruta, naturaleza):
    """Rows with a usable original DOI and the nature we are measuring."""
    csv.field_size_limit(10 ** 7)
    salida = []
    with open(ruta, newline="", encoding="utf-8", errors="replace") as fh:
        for fila in csv.DictReader(fh):
            doi = (fila.get("OriginalPaperDOI") or "").strip().lower()
            nat = (fila.get("RetractionNature") or "").strip()
            # "unavailable" is what the CSV writes when there is no DOI to give.
            # Those rows are real notices but they are outside what a DOI
            # checker can be asked about at all, so they are excluded and
            # counted rather than scored as misses.
            if nat != naturaleza or not doi.startswith("10.") or " " in doi:
                continue
            salida.append({"doi": doi, "record": (fila.get("Record ID") or "").strip(),
                           "anno": anno(fila.get("OriginalPaperDate")),
                           "titulo": (fila.get("Title") or "").strip()[:120],
                           "fecha_retractacion": (fila.get("RetractionDate") or "").strip()})
    # One paper can hold several rows of the same nature. Asking about the same
    # DOI twice would weight it double in the score for no reason.
    vistos, unicas = set(), []
    for f in salida:
        if f["doi"] not in vistos:
            vistos.add(f["doi"])
            unicas.append(f)
    return unicas


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


def veredicto(r, esperado):
    """What refcheck ends up telling the reader about this DOI.

    The labels are the same whichever nature is being measured; what changes is
    which one counts as right. For a reinstatement there is no severity to
    reach, so every notice is a false alarm and only the silences are hits.
    """
    if r is None or r["estado"] == "sin_comprobar":
        return "no comprobado"          # lookup failed; not an answer either way
    if not r["avisos"]:
        return ("silencio, y ni siquiera tiene el DOI" if r["estado"] == "desconocido"
                else "silencio")
    peor = max(a["gravedad"] for a in r["avisos"])
    if esperado is None:
        return "avisado"                # said something where ground truth says nothing
    return "avisado" if peor >= esperado else "mas suave"


def exacto(r, tipos):
    """Does a notice of that actual nature appear, not merely one as grave?"""
    return bool(r and r["avisos"] and any(a["tipo"] in tipos for a in r["avisos"]))


def dicho(r):
    """The notice types refcheck actually printed, and the worst severity.

    Recorded per row because a bare verdict is not enough to act on. For a
    reinstatement especially: "refcheck said something" covers both a live
    correction published after the paper was restored, which is right, and
    RETRACTED on a paper that stands, which is the worst thing this tool can
    say. Those two have to be told apart in the output, not by a second run.
    """
    if not r or not r.get("avisos"):
        return [], -1
    return (sorted({a["tipo"] for a in r["avisos"]}),
            max(a["gravedad"] for a in r["avisos"]))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", help="the Retraction Watch CSV")
    p.add_argument("--nature", default="Retraction", choices=sorted(NATURALEZAS),
                   help="which RetractionNature to measure (default Retraction)")
    p.add_argument("--n", type=int, default=80, help="sampled per era (default 80)")
    p.add_argument("--all", action="store_true",
                   help="take the census instead of sampling: every row of that "
                        "nature with a usable DOI. For the small natures this is "
                        "cheaper than arguing about whether the sample is fair")
    p.add_argument("--seed", type=int, default=20260914)
    p.add_argument("--json", help="write every sampled DOI and its verdict here")
    p.add_argument("--sample", help="re-run an earlier --json instead of sampling "
                                    "afresh: same papers, same ground truth, "
                                    "today's code")
    a = p.parse_args()

    naturaleza = a.nature
    previo = None

    if a.sample:
        # Re-running the exact sample is what turns a number into a controlled
        # before/after. Sampling again with the same seed would not do it: the
        # CSV grows, so the same seed over a longer list draws different papers,
        # and a change in the score could then be the sample moving rather than
        # the code. It also means anyone can reproduce the published figure from
        # the 200 kB of JSON in this repo instead of the 66 MB CSV.
        with open(a.sample, encoding="utf-8") as f:
            previo = json.load(f)
        # The nature travels with the file. Re-running a Correction sample under
        # the default would score it against the wrong bar and the run would
        # look like a regression that never happened.
        naturaleza = previo.get("nature", naturaleza)
        elegidas = [{k: v for k, v in fila.items()
                     if k not in ("veredicto", "registro", "exacto",
                                  "dice", "peor")}
                    for fila in previo["rows"]]
        print(f"re-running the sample in {a.sample}: {len(elegidas)} papers, "
              f"nature {naturaleza!r}, drawn with seed {previo.get('seed')}\n")
    elif a.csv:
        todas = filas(a.csv, naturaleza)
        print(f"rows in the CSV with nature {naturaleza!r} and a real DOI: {len(todas)}")
        elegidas = todas if a.all else muestra(todas, a.n, a.seed)
        print(f"{'census' if a.all else 'sampled'}: {len(elegidas)}"
              f"{'' if a.all else f' across {len(ERAS)} eras'}\n")
    else:
        p.error("need --csv to sample, or --sample to re-run an earlier one")

    esperado = NATURALEZAS[naturaleza]["esperado"]
    tipos = NATURALEZAS[naturaleza]["tipos"]
    invertido = esperado is None

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
    n_exacto = 0
    detalle = []
    for f in elegidas:
        r = por_doi.get(f["doi"])
        v = veredicto(r, esperado)
        ex = exacto(r, tipos)
        n_exacto += ex
        # Which register supplied the notice, for the ones that were caught.
        quien = ""
        if r and r["avisos"]:
            umbral = esperado if esperado is not None else 0
            fuentes = {("pubmed" if av.get("fuente") == "pubmed" else "crossref")
                       for av in r["avisos"] if av["gravedad"] >= umbral} or \
                      {("pubmed" if av.get("fuente") == "pubmed" else "crossref")
                       for av in r["avisos"]}
            quien = "+".join(sorted(fuentes))
        tipos_dichos, peor = dicho(r)
        cuenta[v] += 1
        era = next(n for n, lo, hi in ERAS if lo <= f["anno"] <= hi)
        por_era[era][v] += 1
        detalle.append({**f, "veredicto": v, "registro": quien, "exacto": ex,
                        "dice": tipos_dichos, "peor": peor})

    total = sum(cuenta.values())
    comprobados = total - cuenta["no comprobado"]

    if invertido:
        print(f"\n{naturaleza}s — papers whose retraction was REVERSED. Ground "
              f"truth says the paper stands, so silence is the right answer and "
              f"anything refcheck says here is a false alarm "
              f"({comprobados} looked up):\n")
    else:
        print(f"\n{naturaleza}s the Retraction Watch database knows, "
              f"as refcheck reports them ({comprobados} looked up):\n")

    for v in ORDEN:
        if cuenta[v]:
            pc = 100 * cuenta[v] / comprobados if comprobados and v != "no comprobado" else 0
            marca = ""
            if comprobados:
                acierto = (v.startswith("silencio")) if invertido else (v == "avisado")
                marca = "  <- right" if acierto else ""
            print(f"  {v:38s} {cuenta[v]:5d}" + (f"  {pc:5.1f}%" if pc else "") + marca)

    if invertido:
        callados = cuenta["silencio"] + cuenta["silencio, y ni siquiera tiene el DOI"]
        print(f"\n  quiet, as it should be: {callados}/{comprobados}"
              + (f"  ({100*callados/comprobados:.1f}%)" if comprobados else ""))
        # "Said something" lumps together two very different things, so it is
        # split here rather than left for the reader to assume. A correction
        # published after the paper was restored is a real, live notice and
        # printing it is right. RETRACTED on a paper whose retraction was
        # reversed is the one answer this tool must never give.
        grave = [d for d in detalle if d["peor"] >= 3]
        suave = [d for d in detalle if 0 <= d["peor"] < 3]
        print(f"    of the {len(grave) + len(suave)} it does warn about:")
        print(f"      still called RETRACTED: {len(grave)}"
              + ("   <- wrong, and the expensive way round" if grave else ""))
        print(f"      milder notice only:     {len(suave)}"
              "   (may be a real notice published after the reinstatement)")
        tipos_vistos = collections.Counter(t for d in detalle for t in d["dice"])
        if tipos_vistos:
            print("      notice types seen: "
                  + ", ".join(f"{t}×{n}" for t, n in tipos_vistos.most_common()))
    else:
        # The strict figure. For Retraction the two coincide by construction, so
        # printing it there is a self-check rather than news; for the mild ones
        # it is the whole point.
        print(f"\n  a notice of that exact nature appears: {n_exacto}/{comprobados}"
              + (f"  ({100*n_exacto/comprobados:.1f}%)" if comprobados else "")
              + f"   [vs {cuenta['avisado']} at severity >= {esperado}]")

    print("\nby the original paper's era:")
    cabecera = "says nothing" if invertido else f"warns (>= {esperado})"
    print(f"  {'':10s} {'n':>5s} {cabecera:>16s} {'milder':>8s} {'silent':>8s}")
    for nombre, _, _ in ERAS:
        c = por_era[nombre]
        n = sum(c.values()) - c["no comprobado"]
        if not n:
            continue
        mudo = c["silencio"] + c["silencio, y ni siquiera tiene el DOI"]
        acierto = mudo if invertido else c["avisado"]
        print(f"  {nombre:10s} {n:5d} {100*acierto/n:15.1f}% "
              f"{100*c['mas suave']/n:7.1f}% {100*mudo/n:7.1f}%")

    if invertido:
        # Worst first: if any of these is a RETRACTED it has to be the first
        # thing on screen, not buried forty rows down among mild ones.
        fallos = sorted([d for d in detalle if d["veredicto"] == "avisado"],
                        key=lambda d: -d["peor"])
        titulo_fallos = f"reinstated papers refcheck still warns about ({len(fallos)})"
    else:
        fallos = [d for d in detalle if d["veredicto"].startswith("silencio")
                  or d["veredicto"] == "mas suave"]
        titulo_fallos = f"the ones refcheck does not warn about at that level ({len(fallos)})"
    if fallos:
        print(f"\n{titulo_fallos}:")
        for d in fallos[:40]:
            dice = ("/".join(d["dice"]) or "-") if "dice" in d else "?"
            print(f"  {d['doi']:42s} {d['anno']}  {d['veredicto']:10s} says: {dice}")
            print(f"    RW #{d['record']}  {d['titulo']}")

    # The control. Without this the before/after is a pair of totals and a
    # promise; with it, a verdict that moved has to be named.
    if previo:
        antes = {f["doi"]: VIEJOS.get(f.get("veredicto"), f.get("veredicto"))
                 for f in previo["rows"]}
        movidos = [d for d in detalle if antes.get(d["doi"]) != d["veredicto"]]
        print(f"\nagainst {a.sample}: {len(movidos)} verdicts moved")
        for d in movidos[:40]:
            print(f"  {d['doi']:42s} {antes.get(d['doi'])} -> {d['veredicto']}")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"nature": naturaleza, "n_per_era": None if a.all else a.n,
                       "census": bool(a.all),
                       "seed": previo.get("seed") if previo else a.seed,
                       "rerun_of": a.sample or None,
                       "counts": dict(cuenta), "exact": n_exacto,
                       "rows": detalle}, fh, indent=1)
        print(f"\nwritten: {a.json}")


if __name__ == "__main__":
    main()
