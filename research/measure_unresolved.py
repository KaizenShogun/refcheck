#!/usr/bin/env python3
"""What is actually inside refcheck's "not found in Crossref" bucket?

refcheck asks Crossref for a batch of DOIs with `filter=doi:`. Whatever does not
come back is reported as "not found in Crossref — not checked". That one bucket
holds at least three very different facts, and a reader cannot tell them apart:

  · the DOI is registered somewhere else — DataCite, mEDRA, JaLC, KISTI… A
    preprint on arXiv is a normal thing to cite and Crossref will NEVER hold it.
    Nothing is wrong; this tool simply cannot speak for it.
  · the DOI is registered at Crossref but the batch filter did not return it —
    an indexing hole, or a superseded DOI (measured 2026-09-15: 4 of 1.000).
  · **the DOI does not exist at all.** Mistyped, mangled by a PDF copy-paste, or
    fabricated. For the person reading the bibliography this is the single most
    actionable thing on the page, and today it is the one we whisper.

The DOI Foundation answers this for free, with no key, in batches:
`https://doi.org/ra/<doi>[,<doi>…]` returns the registration agency of each DOI,
or `{"status": "DOI does not exist"}`. Measured 2026-09-17: the limit is URI
length, not count — 200 DOIs (5.7 kB of URL) answer in 7.6 s, 400 (11.5 kB) get
a 414. CORS is open to any origin, so the web page can use it too.

POPULATION, and its bias stated up front. Reference lists deposited at Crossref
by publishers: real bibliographies, sampled across years. They are the best
corpus I have and they are BIASED CLEAN — a publisher's pipeline emits DOIs it
got from a machine, so a human typo never reaches them. The "does not exist"
rate here is therefore a FLOOR for hand-typed bibliographies, not an estimate of
them. Said out loud because quoting it as the general rate would be a lie.

MIT. No key needed. Polite by default: it uses refcheck's own rate limiter for
Crossref and paces doi.org conservatively.

Usage:
    python3 research/measure_unresolved.py --works 300
    python3 research/measure_unresolved.py --dois-from file.txt
    python3 research/measure_unresolved.py --json out.json
"""
import argparse
import collections
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import refcheck  # noqa: E402  (uses its rate limiter, so this stays polite)

RA_API = "https://doi.org/ra/"
# Well under the 11.5 kB that got a 414 and under the 5.7 kB that worked, because
# a long DOI is not rare and the failure mode of guessing high is a hard error.
RA_URL_MAX = 3000
RA_PAUSA = 0.5  # doi.org declares no rate limit; going slower than it allows.

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>,;]+", re.I)


def _get(url, intentos=3, timeout=60):
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": refcheck.UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 - measurement script, report and retry
            ultimo = e
            if i < intentos - 1:
                time.sleep(2 ** i)
    raise ConnectionError(f"{url[:80]}… failed: {ultimo}")


def muestra_referencias(n_obras, anios, semilla, fuente):
    """Pull reference lists from random Crossref works, stratified by year.

    `sample=` is Crossref's own random sampling, which avoids the cursor's
    recency bias — the thing that would have turned a measurement of the register
    into a measurement of the last three years of deposit practice.

    TWO POPULATIONS, and the difference between them is the whole point:

      · `deposited` — the reference's own `DOI` field. A publisher's pipeline
        put it there, usually by matching the citation against the register, so
        it is machine-clean. Measured 2026-09-17: 99.8% sit in Crossref.
      · `crudo` — DOIs pulled out of the `unstructured` text, which is the
        author's bibliography line as typed. No pipeline normalised it. This is
        what a person actually pastes into refcheck, so it is the population
        the tool has to survive.

    The raw side is read with refcheck's OWN `dois_de`, not a friendlier regex
    written for this script: any DOI mangled by my extractor has to show up in
    my numbers, because a user pasting that same line would hit it too.
    """
    random.seed(semilla)
    por_anio = max(1, n_obras // len(anios))
    vistos, filas = set(), []
    for anio in anios:
        rest = por_anio
        while rest > 0:
            pide = min(rest, 100)  # Crossref caps sample= at 100
            filtro = (f"has-references:true,from-pub-date:{anio}-01-01,"
                      f"until-pub-date:{anio}-12-31")
            url = (f"{refcheck.API.rstrip('/')}?sample={pide}&filter={filtro}"
                   f"&select=DOI,reference")
            refcheck.RITMO.espera()
            datos = _get(url)
            for w in datos["message"].get("items") or []:
                for ref in w.get("reference") or []:
                    if fuente == "deposited":
                        hallados = [(ref.get("DOI") or "").strip().lower()]
                        crudo = None
                    else:
                        # Only lines the publisher left unmatched: if the deposit
                        # already carries a DOI field, the text was normalised
                        # and counting it would dilute the human-typed sample.
                        if ref.get("DOI"):
                            continue
                        crudo = ref.get("unstructured") or ""
                        hallados = refcheck.dois_de(crudo)
                    for d in hallados:
                        d = d.lower()
                        if d and d not in vistos:
                            vistos.add(d)
                            filas.append({"doi": d, "anio_citante": anio,
                                          "citado_por": w.get("DOI"),
                                          "crudo": crudo})
            rest -= pide
            print(f"  {anio}: {len(filas)} DOIs de referencia acumulados",
                  file=sys.stderr)
    return filas


def lee_dois(ruta):
    with open(ruta, encoding="utf-8", errors="replace") as fh:
        texto = fh.read()
    vistos, filas = set(), []
    for m in DOI_RE.finditer(texto):
        d = m.group(0).rstrip(".").lower()
        if d not in vistos:
            vistos.add(d)
            filas.append({"doi": d, "anio_citante": None, "citado_por": None})
    return filas


def lotes_por_longitud(dois, tope=RA_URL_MAX):
    """Batch by URL length, not by count: DOI lengths vary a lot."""
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


def agencias(dois):
    """{doi: 'Crossref' | 'DataCite' | … | None} — None means it does not exist."""
    fuera = {}
    for i, lote in enumerate(lotes_por_longitud(dois)):
        url = RA_API + ",".join(urllib.parse.quote(d, safe="") for d in lote)
        datos = _get(url)
        for fila in datos:
            d = str(fila.get("DOI", "")).lower()
            fuera[d] = fila.get("RA")  # absent when {"status": "DOI does not exist"}
        print(f"  RA lote {i + 1}: {len(fuera)}/{len(dois)}", file=sys.stderr)
        time.sleep(RA_PAUSA)
    return fuera


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--works", type=int, default=200,
                   help="how many citing works to sample references from")
    p.add_argument("--anios", default="2024,2020,2015,2010",
                   help="comma-separated publication years to stratify over")
    p.add_argument("--fuente", choices=("deposited", "crudo"), default="crudo",
                   help="'deposited' = the reference's clean DOI field; "
                        "'crudo' = DOIs pulled from the author's unstructured "
                        "citation text, which is what people actually paste")
    p.add_argument("--dois-from", help="measure the DOIs in this file instead")
    p.add_argument("--max-dois", type=int, default=4000,
                   help="cap on DOIs actually queried (both APIs are free and public)")
    p.add_argument("--semilla", type=int, default=20260917)
    p.add_argument("--json", help="write the full per-DOI result here")
    args = p.parse_args()

    if args.dois_from:
        filas = lee_dois(args.dois_from)
        print(f"{len(filas)} DOIs distintos en {args.dois_from}", file=sys.stderr)
    else:
        anios = [a.strip() for a in args.anios.split(",") if a.strip()]
        print(f"Muestreando referencias [{args.fuente}] de {args.works} obras "
              f"({', '.join(anios)})…", file=sys.stderr)
        filas = muestra_referencias(args.works, anios, args.semilla, args.fuente)

    if len(filas) > args.max_dois:
        random.seed(args.semilla)
        filas = random.sample(filas, args.max_dois)
    dois = [f["doi"] for f in filas]
    print(f"\n{len(dois)} DOIs a comprobar.\n", file=sys.stderr)

    # 1. Exactly what refcheck does: the batch filter.
    print("Fase 1 — el lote de Crossref, igual que refcheck…", file=sys.stderr)
    encontrados = set()
    for i in range(0, len(dois), refcheck.LOTE):
        trozo = dois[i:i + refcheck.LOTE]
        try:
            encontrados |= set(refcheck.consulta_lote(trozo))
        except ConnectionError as e:
            print(f"  lote perdido: {e}", file=sys.stderr)
        print(f"  {min(i + refcheck.LOTE, len(dois))}/{len(dois)}", file=sys.stderr)
    ausentes = [d for d in dois if d not in encontrados]
    print(f"\n{len(ausentes)} ausentes del lote "
          f"({100.0 * len(ausentes) / max(1, len(dois)):.1f}%)\n", file=sys.stderr)

    # 2. What the silence was actually hiding.
    ra = agencias(ausentes) if ausentes else {}

    cuenta = collections.Counter()
    detalle = []
    for f in filas:
        d = f["doi"]
        if d in encontrados:
            clase, agencia = "en_crossref", "Crossref"
        else:
            agencia = ra.get(d, "sin_respuesta")
            if agencia is None:
                clase = "no_existe"
            elif agencia == "sin_respuesta":
                clase = "sin_respuesta"
            elif str(agencia).lower() == "crossref":
                clase = "crossref_no_devuelto"
            else:
                clase = "otra_agencia"
        cuenta[clase] += 1
        if clase != "en_crossref":
            detalle.append({**f, "clase": clase, "agencia": agencia})

    total = sum(cuenta.values())
    print("\n" + "=" * 62)
    print(f"{total} DOIs de bibliografías reales")
    print("=" * 62)
    etiquetas = [
        ("en_crossref", "el lote de Crossref lo devuelve (refcheck responde)"),
        ("crossref_no_devuelto", "ES de Crossref pero el lote no lo dio"),
        ("otra_agencia", "registrado en OTRA agencia — Crossref nunca lo tendrá"),
        ("no_existe", "EL DOI NO EXISTE"),
        ("sin_respuesta", "doi.org no contestó por él"),
    ]
    for clave, texto in etiquetas:
        n = cuenta.get(clave, 0)
        print(f"  {n:6d}  {100.0 * n / max(1, total):5.1f}%  {texto}")

    otras = collections.Counter(x["agencia"] for x in detalle
                                if x["clase"] == "otra_agencia")
    if otras:
        print("\n  Agencias distintas de Crossref:")
        for ag, n in otras.most_common():
            print(f"    {n:5d}  {ag}")

    inexistentes = [x for x in detalle if x["clase"] == "no_existe"]
    if inexistentes:
        # The raw line goes next to each one on purpose: it is the only way to
        # tell an author's bad DOI from my own extractor biting off too much.
        print(f"\n  Ejemplos de DOI inexistentes (de {len(inexistentes)}):")
        for x in inexistentes[:12]:
            print(f"    {x['doi']}")
            if x.get("crudo"):
                print(f"        crudo: {x['crudo'][:150]}")

    hoy = time.strftime("%Y-%m-%d")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"fecha": hoy, "n": total, "fuente": args.fuente,
                       "cuenta": dict(cuenta), "otras_agencias": dict(otras),
                       "detalle": detalle}, fh, indent=1, sort_keys=True)
        print(f"\nDetalle en {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
