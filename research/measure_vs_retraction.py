#!/usr/bin/env python3
"""refcheck against the R package `retraction`, on the same DOIs, the same day.

On 2026-10-11 I found that `retraction` (CRAN, Ahmad Sofi-Mahmudi) does most of
what refcheck does and more, and the README was corrected. What it still did not
have was a number: which of the two warns a reader about more of the notices
that exist? This script produces the refcheck half of that table and joins it
with the half that `run_retraction.R` writes.

TWO GROUND TRUTHS, BECAUSE EACH TOOL HAS A HOME FIELD
=====================================================
`retraction` reads Retraction Watch by default (through the Xera API). Scoring it
against a Retraction Watch sample is asking RW whether RW is right: it says
whether the ingestion works, not whether the coverage is good.

refcheck reads Crossref and PubMed. Scoring it against a PubMed sample is the
same thing in the other direction.

So both are measured on both, and each table says whose home it is:

  A. Retraction Watch — the 1,904 DOIs of the four gold-standard files
     (rw_gap_20260914 + rw_eoc/correction/reinstatement_20260916), replayed.
  B. PubMed — a fresh draw of articles PubMed marks as retracted, corrected or
     under an expression of concern, `--draw` with a fixed seed, written whole
     to `--out` so the run can be audited and repeated.

    python3 measure_vs_retraction.py draw --n 300 --out pubmed_vs_20261012.json
    python3 measure_vs_retraction.py refcheck --sample X.json --out rc_X.json
    python3 measure_vs_retraction.py compare --sample X.json --refcheck rc_X.json \\
        --retraction xera=out_xera.csv --retraction all=out_all.csv

MIT.
"""
import argparse
import collections
import csv
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
import refcheck  # noqa: E402

# What each ground-truth label expects, on refcheck's severity scale.
# None = reinstatement: the paper stands, so silence is the right answer.
ESPERADO = {"retraction": 3, "concern": 2, "erratum": 1,
            "Retraction": 3, "Expression of concern": 2, "Correction": 1,
            "Reinstatement": None}

# `retraction`'s status column, on the same scale. Read off its own output on
# the four probe DOIs of 2026-10-12, not guessed from the docs.
GRAVEDAD_R = {"retracted": 3, "expression_of_concern": 2, "correction": 1, "none": -1,
              "reinstated": -1, "not_found": -1, "clean": -1, "": -1}

RW_FICHEROS = ["rw_gap_20260914.json", "rw_eoc_20260916.json",
               "rw_correction_20260916.json", "rw_reinstatement_20260916.json"]


def dibuja(n, semilla):
    import measure_pubmed_gap as pg
    filas = []
    for clave in ("retraction", "erratum", "concern"):
        pob = pg.POBLACIONES[clave]
        total, pmids, regs = pg.muestra(pob["term"], n, semilla)
        print(f"{clave}: {len(pmids)} of {total:,}", file=sys.stderr)
        if pob["sigue"] is None:
            arts = [(p, regs[p]) for p in pmids if p in regs]
        else:
            dest = {}
            for p in pmids:
                d = [q for t, q in regs.get(p, {}).get("enlaces", [])
                     if t == pob["sigue"] and q]
                if d:
                    dest[p] = d[0]
            obj = sorted(set(dest.values()))
            got = {}
            for i in range(0, len(obj), 100):
                got.update(pg.trae_registros(obj[i:i + 100]))
            arts = [(q, got[q]) for q in dest.values() if q in got]
        vistos = set()
        for pmid, r in arts:
            if r["doi"] and r["doi"] not in vistos:
                vistos.add(r["doi"])
                filas.append({"poblacion": clave, "pmid": pmid,
                              "doi": r["doi"], "anno": r["anno"]})
    return filas


def carga_muestra(ruta):
    """[{doi, etiqueta}] from either a draw file or the RW gold-standard set."""
    if ruta == "rw":
        filas = []
        for f in RW_FICHEROS:
            d = json.load(open(os.path.join(AQUI, f)))
            filas += [{"doi": r["doi"], "etiqueta": d["nature"]} for r in d["rows"]]
        return filas
    d = json.load(open(ruta))
    return [{"doi": r["doi"], "etiqueta": r["poblacion"]} for r in d["filas"]]


def corre_refcheck(dois):
    res = refcheck.revisa_lote(dois)
    refcheck.fusiona_pubmed(res)
    out = {}
    for r in res:
        av = r.get("avisos") or []
        out[r["doi"].lower()] = {
            "estado": r["estado"],
            "tipos": sorted({a["tipo"] for a in av}),
            "peor": max((a["gravedad"] for a in av), default=-1),
        }
    return out


def puntua(esperado, peor, comprobado):
    if not comprobado:
        return "unchecked"
    if esperado is None:                       # reinstatement
        return "hit" if peor < 3 else "false RETRACTED"
    if peor >= esperado:
        return "hit"
    return "milder" if peor >= 0 else "silent"


def compara(muestra, rc, rs):
    """{tool: {label: Counter(score)}}, plus the per-DOI join for the JSON."""
    tabla = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    detalle = []
    for f in muestra:
        doi, et = f["doi"].lower(), f["etiqueta"]
        esp = ESPERADO[et]
        fila = {"doi": doi, "etiqueta": et}
        r = rc.get(doi)
        ok = r is not None and r["estado"] != "sin_comprobar"
        s = puntua(esp, r["peor"] if r else -1, ok)
        tabla["refcheck"][et][s] += 1
        fila["refcheck"] = s
        for nombre, filas in rs.items():
            x = filas.get(doi)
            st = (x or {}).get("status", "")
            ok = x is not None and st not in ("unchecked", "error")
            s = puntua(esp, GRAVEDAD_R.get(st, -1), ok)
            tabla["retraction/" + nombre][et][s] += 1
            fila["retraction/" + nombre] = s
            fila["retraction/" + nombre + "/status"] = st
        detalle.append(fila)
    return tabla, detalle


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw"); d.add_argument("--n", type=int, default=300)
    d.add_argument("--seed", type=int, default=20261012); d.add_argument("--out", required=True)
    r = sub.add_parser("refcheck"); r.add_argument("--sample", required=True)
    r.add_argument("--out", required=True)
    c = sub.add_parser("compare"); c.add_argument("--sample", required=True)
    c.add_argument("--refcheck", required=True)
    c.add_argument("--retraction", action="append", default=[], help="name=csv")
    c.add_argument("--out")
    a = ap.parse_args()

    if a.cmd == "draw":
        filas = dibuja(a.n, a.seed)
        json.dump({"seed": a.seed, "n": a.n, "filas": filas}, open(a.out, "w"), indent=1)
        print(collections.Counter(f["poblacion"] for f in filas), file=sys.stderr)
    elif a.cmd == "refcheck":
        m = carga_muestra(a.sample)
        dois = list(dict.fromkeys(f["doi"].lower() for f in m))
        json.dump(corre_refcheck(dois), open(a.out, "w"), indent=1)
    else:
        m = carga_muestra(a.sample)
        rc = json.load(open(a.refcheck))
        rs = {}
        for spec in a.retraction:
            nombre, ruta = spec.split("=", 1)
            rs[nombre] = {row["doi"].lower(): row for row in csv.DictReader(open(ruta))}
        tabla, detalle = compara(m, rc, rs)
        orden = ["hit", "milder", "silent", "false RETRACTED", "unchecked"]
        for tool, por in tabla.items():
            print(f"\n{tool}")
            for et, cnt in por.items():
                n = sum(cnt.values())
                partes = ", ".join(f"{k} {cnt[k]}" for k in orden if cnt[k])
                print(f"  {et:24s} n={n:5d}  hit {100*cnt['hit']/n:5.1f}%   ({partes})")
        if a.out:
            json.dump({"tabla": {t: {e: dict(c) for e, c in p.items()} for t, p in tabla.items()},
                       "filas": detalle}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
