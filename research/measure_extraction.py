#!/usr/bin/env python3
"""Does refcheck's DOI extractor invent DOIs that do not exist?

Measured 2026-09-17 on 529 DOIs pulled from authors' `unstructured` citation
text: 145 (27.4%) do not exist at doi.org. 62 of those carry a `<` or a `>`.
That is not the authors' doing — it is mine. `DOI_RE` accepts `<>` because a
real family of Wiley DOIs contains them:

    10.1002/(sici)1097-0258(19970515)16:9<1041::aid-sim521>3.0.co;2-f

but the same permission makes the extractor swallow the delimiters of
`<https://doi.org/10.x/y>`, which is how several citation styles print a URL.
The DOI comes out as `10.x/y>`, Crossref has no such record, and refcheck tells
the reader "not found in Crossref — not checked" about a paper that exists, is
indexed, and may well be retracted. Silence reads as clean. That is the exact
failure this tool exists to catch in other people's data.

This script measures two things, and the second one matters more:

  1. RESCUE — how many non-existent DOIs become existent ones after sanitising.
  2. DAMAGE — whether sanitising breaks DOIs that work today. A rule that
     rescues 62 and corrupts one real SICI DOI is not a good trade, because the
     corrupted one turns a correct answer into a wrong one.

Truth comes from doi.org's registration-agency endpoint: free, no key, batched.

MIT.

Usage:
    python3 research/measure_extraction.py research/unresolved_crudo_20260917.json
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import os

RA_API = "https://doi.org/ra/"
RA_URL_MAX = 3000
RA_PAUSA = 0.5
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import refcheck  # noqa: E402

UA = refcheck.UA

def limpia_viejo(bruto):
    """refcheck's DOI cleaner as it stood before 2026-09-17, kept verbatim.

    The control needs a baseline that actually shipped, not the raw captured
    string: stripping a trailing full stop is not a new behaviour and crediting
    the new rule with it — or blaming it — would both be wrong.
    """
    return bruto.rstrip(".,;)}\"'").rstrip("}").lower()


def sanea(doi):
    """The rule under measurement — which is refcheck's own, not a copy.

    It started life as a candidate written here, and calling the shipped
    function instead is the point: a private copy would let the published
    numbers keep describing a version of the rule that no longer exists.
    """
    return refcheck._limpia_doi(doi)


def _get(url, intentos=3):
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            ultimo = e
            if i < intentos - 1:
                time.sleep(2 ** i)
    raise ConnectionError(f"{url[:70]}… failed: {ultimo}")


def lotes(dois, tope=RA_URL_MAX):
    lote, largo = [], len(RA_API)
    for d in dois:
        cod = urllib.parse.quote(d, safe="")
        extra = len(cod) + (1 if lote else 0)
        if lote and largo + extra > tope:
            yield lote
            lote, largo = [], len(RA_API)
            extra = len(cod)
        lote.append(d)
        largo += extra
    if lote:
        yield lote


def existe(dois):
    """{doi: RA or None}. None means doi.org says it does not exist."""
    fuera = {}
    for lote in lotes(sorted(set(dois))):
        datos = _get(RA_API + ",".join(urllib.parse.quote(d, safe="") for d in lote))
        for fila in datos:
            fuera[str(fila.get("DOI", "")).lower()] = fila.get("RA")
        time.sleep(RA_PAUSA)
    return fuera


def sici_reales(n=100):
    """Real Wiley SICI DOIs, sampled live — never typed from memory.

    The first version of this control used four SICI DOIs I wrote out myself.
    doi.org said all four did not exist: I had invented them, so the control
    proved nothing. Sampling them is the only honest way to hold the rule to
    account, because these are exactly the DOIs it could corrupt.
    """
    url = ("https://api.crossref.org/works?sample=100&select=DOI"
           "&filter=prefix:10.1002,from-pub-date:1996-01-01,"
           "until-pub-date:1998-12-31")
    fuera = []
    for _ in range(max(1, n // 50)):
        datos = _get(url)
        fuera += [w["DOI"] for w in datos["message"]["items"] if "<" in w["DOI"]]
        time.sleep(1)
    return sorted(set(fuera))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    datos = json.load(open(sys.argv[1], encoding="utf-8"))
    inex = [x for x in datos["detalle"] if x["clase"] == "no_existe"]
    print(f"{len(inex)} DOIs que doi.org dice que no existen\n")

    # --- 1. RESCUE ---------------------------------------------------------
    cambiados = [(x["doi"], sanea(x["doi"])) for x in inex]
    cambiados = [(a, b) for a, b in cambiados if a != b]
    print(f"La regla cambia {len(cambiados)} de {len(inex)}.")
    if not cambiados:
        print("Nada que comprobar.")
        return
    res = existe([b for _, b in cambiados])
    salvados = [(a, b, res.get(b.lower())) for a, b in cambiados if res.get(b.lower())]
    print(f"De esos, EXISTEN tras sanear: {len(salvados)}"
          f"  ({100.0 * len(salvados) / len(inex):.1f}% del total de inexistentes)\n")
    for a, b, ra in salvados[:12]:
        print(f"  {a}\n    -> {b}   [{ra}]")

    # --- 2. DAMAGE ---------------------------------------------------------
    # A rule can only break a DOI it changes, so the cheap half of this control
    # is offline and can therefore be large: thousands of real DOIs, and the
    # count of how many the rule touches at all. Only the ones it touches cost
    # a request.
    print("\n" + "=" * 62)
    print("CONTROL: ¿la regla rompe DOIs que hoy funcionan?")
    print("=" * 62)

    corpus = {}
    sici = sici_reales()
    corpus["SICI reales de Wiley (muestreados hoy)"] = sici
    if len(sys.argv) > 2:
        with open(sys.argv[2], encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
        nbib = sorted(set(re.findall(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", texto)))
        corpus[f"DOIs reales de {sys.argv[2].split('/')[-1]}"] = nbib

    total_roto = 0
    for nombre, dois in corpus.items():
        # Damage is not "the new rule produces something that does not exist" —
        # plenty of captured strings never existed under the old rule either
        # (a /suppl_file/….pdf, a 10.13039 funder id). Damage is a DOI that
        # RESOLVED BEFORE and stops resolving now, so the comparison has to be
        # old-cleaner vs new-cleaner, with both looked up.
        tocados = [(limpia_viejo(d), sanea(d)) for d in dois]
        tocados = [(a, b) for a, b in tocados if a != b]
        print(f"\n  {nombre}: {len(dois)} DOIs, el limpiador nuevo difiere del "
              f"viejo en {len(tocados)}")
        if tocados:
            res2 = existe([x for par in tocados for x in par if x])
            for a, b in tocados:
                vivo_antes = bool(a) and bool(res2.get(a.lower()))
                vivo_ahora = bool(b) and bool(res2.get(b.lower()))
                if vivo_antes and not vivo_ahora:
                    total_roto += 1
                    marca = "ROTO"
                elif vivo_ahora and not vivo_antes:
                    marca = "RESCATADO"
                else:
                    marca = "igual" if vivo_ahora else "ninguno existe"
                if marca != "ninguno existe":
                    print(f"    {marca:10s}  {a}  ->  {b}")
    print(f"\n  DOIs reales dañados por la regla: {total_roto}")

    hoy = time.strftime("%Y-%m-%d")
    print(f"\n({hoy})")


if __name__ == "__main__":
    main()
