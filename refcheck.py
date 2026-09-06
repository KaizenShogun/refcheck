#!/usr/bin/env python3
"""refcheck — has anything you cite been quietly corrected?

Retractions are the famous case, and free tools already cover them: Zotero warns
you, Retraction Watch keeps the list. But a retraction is the rarest kind of
change to the scientific record. Measured against the Crossref API on 2026-09-06:

    retractions (covered by free tools) ....  65,976
    corrections ........................... 205,005
    errata ................................ 113,437
    expressions of concern .................  4,229
    withdrawals, removals, addenda, ... ....  16,494
    -------------------------------------------------
    NOT covered by any free tool ........... 339,165   (5.1x the retractions)

Those are the quiet ones. Nobody emails you when the paper you are citing had
its numbers corrected two years after you read it — and unlike a retraction, the
paper is still perfectly valid, which is exactly why nobody looks.

This reads a list of DOIs (or a .bib file) and tells you which of your references
carry a published change notice, what kind, and where to read it.

Usage:
    refcheck.py refs.bib
    refcheck.py dois.txt
    echo 10.1371/journal.pone.0161231 | refcheck.py -
    refcheck.py refs.bib --json          machine-readable, for pipelines

Exit codes: 0 nothing found · 1 something found · 2 usage/network error.
So it can gate a CI job in a journal or a lab.

Standard library only. No account, no key, no tracking. MIT.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.crossref.org/works/"
# Crossref asks callers to identify themselves; being polite gets you the fast pool.
CONTACT = os.environ.get("REFCHECK_MAILTO", "")
UA = f"refcheck/1.0 (https://github.com/KaizenShogun/refcheck{'; mailto:' + CONTACT if CONTACT else ''})"

# How loudly to shout. A retraction means "do not use this". A correction means
# "check that the bit you are citing is still the bit that is written there".
GRAVEDAD = {
    "retraction": 3, "partial_retraction": 3, "removal": 3, "withdrawal": 3,
    "expression_of_concern": 2,
    "correction": 1, "erratum": 1, "corrigendum": 1,
    "addendum": 0, "clarification": 0, "new_edition": 0, "new_version": 0,
}
ETIQUETA = {
    3: "RETRACTED — do not cite this as evidence",
    2: "EXPRESSION OF CONCERN — the journal itself is unsure",
    1: "CORRECTED — check the number you are quoting is still there",
    0: "UPDATED — additional material published",
}

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9<>\[\]]+")


def dois_de(texto):
    """Pull DOIs out of anything: a plain list, a .bib, a pasted bibliography.

    Deliberately forgiving — the person running this has a messy file, not a
    clean dataset, and a tool that demands a clean dataset does not get used.
    """
    vistos, salida = set(), []
    for bruto in DOI_RE.findall(texto):
        d = bruto.rstrip(".,;)}\"'").lower()
        # .bib entries often wrap the DOI: doi = {10.xxxx/yyy},
        d = d.rstrip("}")
        if d not in vistos:
            vistos.add(d)
            salida.append(d)
    return salida


def consulta(doi, reintentos=3):
    url = API + urllib.parse.quote(doi)
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)["message"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None          # DOI not in Crossref: not an error, just unknown
            if e.code in (429, 500, 502, 503) and intento < reintentos - 1:
                time.sleep(2 ** intento)
                continue
            return None
        except Exception:
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
                continue
            return None
    return None


def revisa(doi):
    """Return the change notices attached to one DOI, worst first."""
    obra = consulta(doi)
    if obra is None:
        return {"doi": doi, "estado": "desconocido", "avisos": []}
    avisos = []
    for u in (obra.get("updated-by") or []):
        tipo = (u.get("type") or "unknown").lower()
        partes = (u.get("updated") or {}).get("date-parts", [[None]])[0]
        fecha = "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(partes) if p) if partes and partes[0] else ""
        avisos.append({
            "tipo": tipo,
            "gravedad": GRAVEDAD.get(tipo, 1),
            "fecha": fecha,
            "doi_aviso": u.get("DOI", ""),
            "etiqueta": u.get("label") or tipo.replace("_", " ").title(),
        })
    avisos.sort(key=lambda a: (-a["gravedad"], a["fecha"]))
    titulo = (obra.get("title") or [""])[0]
    return {"doi": doi, "estado": "ok", "titulo": titulo,
            "revista": (obra.get("container-title") or [""])[0], "avisos": avisos}


def informe(resultados, ancho=78):
    con = [r for r in resultados if r["avisos"]]
    desc = [r for r in resultados if r["estado"] == "desconocido"]
    lineas = []
    for r in sorted(con, key=lambda r: -r["avisos"][0]["gravedad"]):
        peor = r["avisos"][0]
        lineas.append("")
        lineas.append(f"  {ETIQUETA[peor['gravedad']]}")
        t = r.get("titulo", "")
        lineas.append(f"    {t[:ancho - 4]}" if t else "")
        lineas.append(f"    {r['doi']}")
        for a in r["avisos"]:
            fecha = f" ({a['fecha']})" if a["fecha"] else ""
            lineas.append(f"      → {a['etiqueta']}{fecha}: https://doi.org/{a['doi_aviso']}")
    cab = [f"  {len(resultados)} reference(s) checked · {len(con)} carry a change notice"]
    if desc:
        cab.append(f"  {len(desc)} not found in Crossref (preprints, books, bad DOI) — not checked")
    if not con:
        cab.append("  Nothing found. That is the expected result most of the time;")
        cab.append("  it is the 1-in-N that this exists for.")
    return "\n".join(cab + lineas)


def main():
    p = argparse.ArgumentParser(
        description="Check whether the papers you cite carry a published correction, "
                    "erratum, expression of concern or retraction.")
    p.add_argument("fichero", help="file with DOIs or a .bib file; use - for stdin")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--pausa", type=float, default=0.12, help="seconds between API calls")
    a = p.parse_args()

    texto = sys.stdin.read() if a.fichero == "-" else open(a.fichero, encoding="utf-8", errors="replace").read()
    dois = dois_de(texto)
    if not dois:
        print("No DOIs found in that file.", file=sys.stderr)
        return 2

    resultados = []
    for i, d in enumerate(dois):
        resultados.append(revisa(d))
        if not a.json and len(dois) > 8:
            print(f"\r  checking {i + 1}/{len(dois)}…", end="", file=sys.stderr, flush=True)
        time.sleep(a.pausa)
    if not a.json and len(dois) > 8:
        print("\r" + " " * 30 + "\r", end="", file=sys.stderr)

    if a.json:
        json.dump(resultados, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(informe(resultados))
    return 1 if any(r["avisos"] for r in resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
