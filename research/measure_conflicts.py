#!/usr/bin/env python3
"""How many Crossref works carry two contradictory Retraction Watch assertions?

Background. On 2026-05-19 a user reported in the Crossref community forum that
10.1148/85.3.474 shows as *retracted* in the API while the Retraction Watch
database records only an expression of concern:

    https://community.crossref.org/t/15831

Crossref confirmed the cause: when a Retraction Watch record changes its
RetractionNature (here retraction -> expression of concern, on 2026-03-26), the
API *appends* a second update assertion with the same `record-id`, same source
and the same timestamp, instead of overwriting the first one. Tracked as
CR-2746, medium priority.

Consequence for anyone reading the API: a work can carry both a `retraction` and
an `expression_of_concern` assertion from the same record, with identical dates,
and nothing in the response says which one is current. A downstream tool that
takes the worst one — as refcheck did until this was measured — tells a reader to
throw away a citation that was never retracted.

This script measures how many works are in that state. Scope, stated plainly:
every work carrying a retraction assertion and every work carrying an
expression-of-concern assertion. That covers every conflict where one side is a
retraction (the loudest false alarm) and every conflict between the two rarest
types. It does NOT scan the 213k correction notices, so the number below is a
floor, not a total.

Method: page the public REST API with a cursor, `select=DOI,update-to`, group
each work's assertions by (source, record-id), and flag any group holding more
than one distinct `type`.

    python3 measure_conflicts.py                  # the two scans above
    python3 measure_conflicts.py --filter update-type:correction
    python3 measure_conflicts.py --out conflicts.json
    python3 measure_conflicts.py --csv retraction_watch.csv   # say which half is stale

`--csv` settles each conflict against the upstream source. Crossref publishes the
Retraction Watch database at
https://gitlab.com/crossref/retraction-watch-data (one row per record, and the
`RetractionNature` column holds the current verdict), so for any record-id in
conflict you can read off which of the API's two types is the live one and which
is the leftover. Measured 2026-09-09: the file holds exactly five distinct
natures — Retraction, Expression of concern, Correction, Reinstatement, and
blank — so anything else the API reports as a `type` did not come from there.

Standard library only. MIT.
"""
import argparse
import collections
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.crossref.org/works"
CONTACT = os.environ.get("REFCHECK_MAILTO", "")
UA = f"refcheck-research/1.0 (https://github.com/KaizenShogun/refcheck{'; mailto:' + CONTACT if CONTACT else ''})"


def pagina(filtro, cursor, filas, reintentos=4):
    q = urllib.parse.urlencode({
        "filter": filtro,
        "select": "DOI,update-to",
        "rows": filas,
        "cursor": cursor,
    })
    ultimo = None
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)["message"]
        except Exception as e:                      # noqa: BLE001 — retry anything
            ultimo = e
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
    raise ConnectionError(f"Crossref page failed after {reintentos} tries: {ultimo}")


def conflictos_de(obra):
    """Groups of assertions sharing (source, record-id) but disagreeing on type.

    Only assertions that actually carry a record-id are grouped: without one
    there is no evidence that two entries came from the same upstream record,
    and a work legitimately can be both corrected and later retracted.
    """
    grupos = collections.defaultdict(set)
    for u in (obra.get("update-to") or []):
        rid = u.get("record-id")
        if rid is None:
            continue
        grupos[(u.get("source", ""), str(rid))].add((u.get("type") or "unknown").lower())
    return {k: sorted(v) for k, v in grupos.items() if len(v) > 1}


def escanea(filtro, filas=1000, pausa=0.2, verboso=True):
    cursor, vistos, afectados = "*", 0, []
    pares = collections.Counter()
    total = None
    while True:
        msg = pagina(filtro, cursor, filas)
        if total is None:
            total = msg["total-results"]
        items = msg.get("items") or []
        if not items:
            break
        for w in items:
            vistos += 1
            c = conflictos_de(w)
            if c:
                afectados.append({"doi": w.get("DOI", ""),
                                  "grupos": [{"source": s, "record_id": r, "types": t}
                                             for (s, r), t in c.items()]})
                for tipos in c.values():
                    pares[" + ".join(tipos)] += 1
        cursor = msg.get("next-cursor")
        if verboso:
            print(f"\r  {filtro}: {vistos}/{total} scanned, {len(afectados)} conflicting…",
                  end="", file=sys.stderr, flush=True)
        if not cursor or vistos >= total:
            break
        time.sleep(pausa)
    if verboso:
        print(file=sys.stderr)
    return {"filtro": filtro, "escaneados": vistos, "total_declarado": total,
            "afectados": afectados, "pares": dict(pares)}


# The API spells these the Crossref way; the CSV spells them the English way.
NATURALEZA = {
    "retraction": "retraction",
    "expression of concern": "expression_of_concern",
    "correction": "correction",
    "reinstatement": "reinstatement",
}


def upstream(ruta):
    """{record-id: current type} straight from the Retraction Watch CSV."""
    import csv
    csv.field_size_limit(10 ** 7)
    vivos = {}
    with open(ruta, encoding="utf-8", errors="replace", newline="") as fh:
        for fila in csv.DictReader(fh):
            rid = (fila.get("Record ID") or "").strip()
            if not rid:
                continue
            crudo = (fila.get("RetractionNature") or "").strip()
            vivos[rid] = NATURALEZA.get(crudo.lower(), crudo.lower() or "unknown")
    return vivos


def arbitra(union, vivos):
    """For each conflict, say which type the upstream still holds — and which not."""
    filas = []
    for doi, w in sorted(union.items()):
        for g in w["grupos"]:
            actual = vivos.get(g["record_id"])
            filas.append({
                "doi": doi,
                "record_id": g["record_id"],
                "api_dice": g["types"],
                "origen_dice": actual,
                "sobra": [t for t in g["types"] if t != actual] if actual else None,
            })
    return filas


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--filter", action="append", dest="filtros",
                   help="Crossref filter to scan (repeatable); default: the two scans")
    p.add_argument("--rows", type=int, default=1000)
    p.add_argument("--pausa", type=float, default=0.2)
    p.add_argument("--out", help="write the full findings as JSON")
    p.add_argument("--csv", help="Retraction Watch CSV, to settle which half is stale")
    a = p.parse_args()

    filtros = a.filtros or ["update-type:retraction", "update-type:expression_of_concern"]
    salidas, union = [], {}
    for f in filtros:
        s = escanea(f, filas=a.rows, pausa=a.pausa)
        salidas.append(s)
        for w in s["afectados"]:
            union[w["doi"]] = w

    print()
    for s in salidas:
        n = len(s["afectados"])
        pct = 100.0 * n / s["escaneados"] if s["escaneados"] else 0
        print(f"  {s['filtro']}")
        print(f"    scanned  : {s['escaneados']} works")
        print(f"    conflicts: {n}  ({pct:.2f}%)")
        for par, c in sorted(s["pares"].items(), key=lambda kv: -kv[1]):
            print(f"      {c:6d}  {par}")
    print(f"\n  distinct works affected across all scans: {len(union)}")

    arbitraje = None
    if a.csv:
        arbitraje = arbitra(union, upstream(a.csv))
        print("\n  settled against the Retraction Watch CSV:")
        for f in arbitraje:
            if f["origen_dice"] is None:
                print(f"    {f['doi']}  #{f['record_id']}: not in the CSV at all")
                continue
            sobra = ", ".join(f["sobra"]) or "(nothing — both match?)"
            print(f"    {f['doi']}  #{f['record_id']}: upstream says "
                  f"{f['origen_dice']}; the API also serves {sobra}")

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"scans": salidas, "distinct": sorted(union),
                       "arbitraje": arbitraje}, fh, indent=1)
        print(f"  written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
