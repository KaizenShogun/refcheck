#!/usr/bin/env python3
"""refcheck — has anything you cite been quietly corrected?

Retractions are the famous case, and free tools already cover them: Zotero warns
you, Retraction Watch keeps the list. But a retraction is the rarest kind of
change to the scientific record. Measured against the Crossref API on 2026-09-08:

    retractions (what the familiar tools cover) ....  75,265
    corrections ................................... 213,113
    errata ........................................ 116,091
    expressions of concern .........................   4,233
    new editions ..................................  10,874
    withdrawals, removals, addenda, clarifications .   6,328
    ------------------------------------------------------
    the quiet ones ................................ 350,639   (4.7x the retractions)

Those are the quiet ones. Nobody emails you when the paper you are citing had
its numbers corrected two years after you read it — and unlike a retraction, the
paper is still perfectly valid, which is exactly why nobody looks.

This reads a list of DOIs (or a .bib file) and tells you which of your references
carry a published change notice, what kind, and where to read it.

No terminal? The same check runs in a browser, with nothing to install:
https://kaizenshogun.github.io/refcheck/

Usage:
    refcheck.py refs.bib
    refcheck.py dois.txt
    echo 10.1371/journal.pone.0161231 | refcheck.py -
    refcheck.py refs.bib --json          machine-readable, for pipelines

Exit codes: 0 nothing found · 1 something found · 2 bad usage, or a reference
that could not be looked up. A failed lookup is not a clean reference, so it
does not let a CI gate go green.

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
LOTE = 40   # DOIs per request. Measured safe against the API on 2026-09-08 (75 also
            # worked); 40 keeps the URL short and the public service unbothered.
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
# Said in the loudest place because it is the one answer this tool cannot give you.
CONFLICTO = ("CONTRADICTORY NOTICES — check this one by hand, Crossref disagrees "
             "with itself")

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


def marca_contradicciones(avisos):
    """Flag assertions that come from one upstream record but disagree on type.

    Crossref does not overwrite a Retraction Watch assertion when the upstream
    record changes its nature: it appends a second one carrying the same
    `record-id`, the same source and the same timestamp, with a different type.
    So 10.1148/85.3.474 is served as both `retraction` and
    `expression_of_concern` — and the retraction is the stale half, downgraded
    upstream on 2026-03-26. Reported by a user in 2026-05, acknowledged by
    Crossref (CR-2746), still live. https://community.crossref.org/t/15831

    Nothing in the response says which half is current, so this tool must not
    pick one. Taking the worst — what it did until this was measured — is the
    expensive mistake: it tells a reader to bin a citation that was never
    retracted. Both halves get flagged and the reader is sent upstream.
    """
    grupos = {}
    for a in avisos:
        if a.get("registro") is None:
            continue        # no record-id: no evidence these share an origin
        grupos.setdefault((a["fuente"], a["registro"]), []).append(a)
    for miembros in grupos.values():
        tipos = sorted({m["tipo"] for m in miembros})
        if len(tipos) > 1:
            for m in miembros:
                m["contradice"] = [t for t in tipos if t != m["tipo"]]
    return avisos


def avisos_de(obra):
    """Change notices attached to one work record, worst first."""
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
            "fuente": u.get("source", ""),
            "registro": str(u["record-id"]) if u.get("record-id") is not None else None,
            "contradice": [],
        })
    marca_contradicciones(avisos)
    avisos.sort(key=lambda a: (-a["gravedad"], a["fecha"]))
    return avisos


def ficha(doi, obra):
    avisos = avisos_de(obra)
    return {"doi": doi, "estado": "ok", "titulo": (obra.get("title") or [""])[0],
            "revista": (obra.get("container-title") or [""])[0],
            "contradictorio": any(a["contradice"] for a in avisos),
            "avisos": avisos}


def revisa(doi):
    """Return the change notices attached to one DOI, worst first."""
    obra = consulta(doi)
    if obra is None:
        return {"doi": doi, "estado": "desconocido", "avisos": []}
    return ficha(doi, obra)


def consulta_lote(dois, reintentos=3):
    """One request for up to LOTE DOIs. Returns {doi: work}, or raises.

    Crossref answers a `filter=doi:a,doi:b,…` query with only the DOIs it holds,
    so a DOI missing from the reply means "no record", not "lookup failed" —
    and those two must never be shown to the reader as the same thing.
    """
    filtro = ",".join("doi:" + urllib.parse.quote(d, safe="") for d in dois)
    url = f"{API.rstrip('/')}?rows={len(dois)}&select=DOI,title,container-title,updated-by&filter={filtro}"
    ultimo = None
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                items = json.load(r)["message"].get("items") or []
            return {str(w.get("DOI", "")).lower(): w for w in items}
        except Exception as e:
            ultimo = e
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
    raise ConnectionError(f"Crossref lookup failed: {ultimo}")


def revisa_lote(dois, pausa=0.4, avisa=None):
    """Check every DOI, in batches. Never reports a failed lookup as 'not found'."""
    resultados, hechos = [], 0
    for i in range(0, len(dois), LOTE):
        trozo = dois[i:i + LOTE]
        try:
            obras = consulta_lote(trozo)
        except ConnectionError as e:
            # This batch is lost, the rest of the bibliography is not.
            for d in trozo:
                resultados.append({"doi": d, "estado": "sin_comprobar",
                                   "error": str(e), "avisos": []})
            obras = None
        if obras is not None:
            for d in trozo:
                w = obras.get(d.lower())
                resultados.append(ficha(d, w) if w
                                  else {"doi": d, "estado": "desconocido", "avisos": []})
        hechos += len(trozo)
        if avisa:
            avisa(hechos, len(dois))
        if i + LOTE < len(dois):
            time.sleep(pausa)
    return resultados


def informe(resultados, ancho=78):
    con = [r for r in resultados if r["avisos"]]
    desc = [r for r in resultados if r["estado"] == "desconocido"]
    sinc = [r for r in resultados if r["estado"] == "sin_comprobar"]
    lineas = []
    chocan = [r for r in con if r.get("contradictorio")]
    for r in sorted(con, key=lambda r: -r["avisos"][0]["gravedad"]):
        peor = r["avisos"][0]
        lineas.append("")
        lineas.append(f"  {CONFLICTO if r.get('contradictorio') else ETIQUETA[peor['gravedad']]}")
        t = r.get("titulo", "")
        lineas.append(f"    {t[:ancho - 4]}" if t else "")
        lineas.append(f"    {r['doi']}")
        for a in r["avisos"]:
            fecha = f" ({a['fecha']})" if a["fecha"] else ""
            # .get: a report loaded from an older --json run has no such key.
            choca = a.get("contradice") or []
            choque = f"  [contradicts: {', '.join(choca)}]" if choca else ""
            lineas.append(f"      → {a['etiqueta']}{fecha}: https://doi.org/{a['doi_aviso']}{choque}")
        if r.get("contradictorio"):
            lineas.append("      Same upstream record, two different verdicts, same date — the API")
            lineas.append("      does not say which is current. Look it up: retractiondatabase.org")
    cab = [f"  {len(resultados) - len(sinc)} reference(s) checked · "
           f"{len(con)} carry a change notice"]
    if chocan:
        cab.append(f"  {len(chocan)} of them carry CONTRADICTORY notices — decide those by hand")
    if sinc:
        cab.append(f"  {len(sinc)} could NOT be checked — the lookup failed. Not clean: unknown.")
    if desc:
        cab.append(f"  {len(desc)} not found in Crossref (preprints, books, bad DOI) — not checked")
    if not con and len(resultados) > len(sinc):
        cab.append("  Nothing found. That is the expected result most of the time;")
        cab.append("  it is the 1-in-N that this exists for.")
    for r in sinc:
        lineas.append(f"      ? not checked: {r['doi']}")
    return "\n".join(cab + lineas)


def main():
    p = argparse.ArgumentParser(
        description="Check whether the papers you cite carry a published correction, "
                    "erratum, expression of concern or retraction.")
    p.add_argument("fichero", help="file with DOIs or a .bib file; use - for stdin")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--pausa", type=float, default=0.4, help="seconds between API calls")
    a = p.parse_args()

    texto = sys.stdin.read() if a.fichero == "-" else open(a.fichero, encoding="utf-8", errors="replace").read()
    dois = dois_de(texto)
    if not dois:
        print("No DOIs found in that file.", file=sys.stderr)
        return 2

    # Only draw progress on a real terminal; piped into a log it is just \r noise.
    ruidoso = not a.json and len(dois) > LOTE and sys.stderr.isatty()

    def avisa(hechos, total):
        if ruidoso:
            print(f"\r  checking {hechos}/{total}…", end="", file=sys.stderr, flush=True)

    resultados = revisa_lote(dois, pausa=a.pausa, avisa=avisa)
    if ruidoso:
        print("\r" + " " * 30 + "\r", end="", file=sys.stderr)

    if a.json:
        json.dump(resultados, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(informe(resultados))

    if any(r["avisos"] for r in resultados):
        return 1
    # A reference we could not look up must not let a CI gate go green.
    if any(r["estado"] == "sin_comprobar" for r in resultados):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
