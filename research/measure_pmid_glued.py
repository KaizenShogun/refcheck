#!/usr/bin/env python3
"""How many "nonexistent" DOIs are really a DOI with a PMID welded onto it?

    10.1002/cncr.24840  +  20087961  →  10.1002/cncr.2484020087961

Measured on the corpus frozen on 2026-09-18 (`corpus_crudo_20260918.json`):
the same 5.590 bibliography lines, so that any before/after is about the code
and not about a new sample. That file exists because on 2026-09-17 I compared
two different random samples and called the difference an improvement.

What it answers, in this order, because the third only matters if the second
holds:

  1. How many of the DOIs doi.org says do not exist produce a candidate split.
  2. How many of those PubMed CONFIRMS — it returns that exact DOI for that
     exact id. That is the only thing that authorises a rescue.
  3. THE CONTROL: how many DOIs that ALREADY RESOLVE would produce a confirmed
     rescue if the rule were let loose on them. This has to be 0. refcheck only
     ever applies the rule after doi.org has said the string does not exist, so
     the damage is nil by construction — but "by construction" is an argument,
     and this is a measurement, and I have had arguments be wrong before.

Also reported, because it is the failure mode that would matter: how many
broken DOIs have MORE THAN ONE confirmed split. refcheck reports neither when
that happens; the count tells me whether that branch is theory or traffic.

MIT. No API key. Talks to doi.org and to NCBI, both public and free, in bulk
and at a polite pace.

Usage:
    python3 research/measure_pmid_glued.py --corpus research/corpus_crudo_20260918.json
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import refcheck  # noqa: E402  — the tool itself, never a copy of its rules


def dois_del_corpus(ruta):
    """Every DOI in the frozen corpus, read with refcheck's own extractor.

    Deliberately not a fresh regex written for this script: a private copy
    would let the published figures describe a rule that no longer exists.
    """
    with open(ruta, encoding="utf-8") as f:
        crudo = json.load(f)
    lineas = crudo["crudos"] if isinstance(crudo, dict) else crudo
    vistos, fuera = set(), []
    for fila in lineas:
        texto = fila.get("crudo") if isinstance(fila, dict) else str(fila)
        for d in refcheck.dois_de(texto or ""):
            if d not in vistos:
                vistos.add(d)
                fuera.append(d)
    return fuera


def clasifica(dois, pausa=0.5):
    """{doi: 'existe' | 'no_existe' | 'desconocido'} via doi.org's RA endpoint."""
    agencia = refcheck.agencias_de(dois)
    fuera = {}
    for d in dois:
        k = d.lower()
        if k not in agencia:
            fuera[d] = "desconocido"
        elif agencia[k] is None:
            fuera[d] = "no_existe"
        else:
            fuera[d] = "existe"
    return fuera


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", default="research/corpus_crudo_20260918.json")
    p.add_argument("--extra", action="append", default=[],
                   help="more files of bibliography text to pull DOIs from")
    p.add_argument("--min", type=int, default=1,
                   help="shortest digit tail to try (default 1: measure it, "
                        "then let the evidence pick refcheck's floor)")
    p.add_argument("--max", type=int, default=8)
    p.add_argument("--tope-control", type=int, default=600,
                   help="cap on resolving DOIs put through the control, to "
                        "stay polite to NCBI")
    p.add_argument("--json", help="write the full per-DOI result here")
    args = p.parse_args()

    dois = dois_del_corpus(args.corpus)
    for ruta in args.extra:
        with open(ruta, encoding="utf-8", errors="replace") as f:
            texto = f.read()
        for d in refcheck.dois_de(texto):
            if d not in dois:
                dois.append(d)
    print(f"DOIs in corpus: {len(dois)}")

    t0 = time.time()
    clase = clasifica(dois)
    rotos = [d for d in dois if clase[d] == "no_existe"]
    buenos = [d for d in dois if clase[d] == "existe"]
    print(f"  exist: {len(buenos)}   do not exist: {len(rotos)}   "
          f"unknown: {len(dois) - len(buenos) - len(rotos)}"
          f"   ({time.time() - t0:.0f} s)")

    def candidatos(d):
        return refcheck.candidatos_pmid_pegado(d, args.min, args.max)

    # ---- 1 & 2: the rescue -------------------------------------------------
    con_candidato = [d for d in rotos if candidatos(d)]
    print(f"\nof the {len(rotos)} that do not exist, {len(con_candidato)} "
          f"produce at least one candidate split")

    pares = {d: candidatos(d) for d in con_candidato}
    pmids = sorted({cola for v in pares.values() for _, cola in v})
    print(f"  {len(pmids)} distinct ids to ask PubMed about")
    sabido = refcheck.resuelve_pmids(pmids) if pmids else {}

    detalle, ambiguos = [], []
    for d, opciones in pares.items():
        casan = [(c, p_) for c, p_ in opciones
                 if (sabido.get(p_) or {}).get("doi") == c]
        if len(casan) > 1:
            ambiguos.append({"roto": d, "casan": casan})
        if casan:
            detalle.append({"roto": d, "doi": casan[0][0], "pmid": casan[0][1],
                            "n_confirmados": len(casan),
                            "digitos": len(casan[0][1])})

    confirmados = [e for e in detalle if e["n_confirmados"] == 1]
    print(f"  PubMed confirms a split for {len(confirmados)} of them")
    print(f"  ambiguous (two confirmed splits, so refcheck reports neither): "
          f"{len(ambiguos)}")
    if confirmados:
        anchos = {}
        for e in confirmados:
            anchos[e["digitos"]] = anchos.get(e["digitos"], 0) + 1
        print("  tail length of the confirmed splits: "
              + ", ".join(f"{k} digits ×{v}" for k, v in sorted(anchos.items())))
    for e in confirmados:
        print(f"    {e['roto']}  →  {e['doi']}  + PMID {e['pmid']}")

    # ---- 3: the control ----------------------------------------------------
    # Damage is "resolved before and does not now". The rule never runs on a
    # DOI that resolves, so this should be empty; measuring it is how I find
    # out whether that reasoning survives contact with real strings.
    control = [d for d in buenos if candidatos(d)][:args.tope_control]
    print(f"\ncontrol: {len(control)} of the {len(buenos)} RESOLVING DOIs even "
          f"produce a candidate split")
    pares_c = {d: candidatos(d) for d in control}
    pmids_c = sorted({cola for v in pares_c.values() for _, cola in v})
    print(f"  {len(pmids_c)} distinct ids to ask PubMed about")
    sabido_c = refcheck.resuelve_pmids(pmids_c) if pmids_c else {}
    danio = []
    for d, opciones in pares_c.items():
        casan = [(c, p_) for c, p_ in opciones
                 if (sabido_c.get(p_) or {}).get("doi") == c]
        if len(casan) == 1:
            danio.append({"doi": d, "seria_reescrito_a": casan[0][0],
                          "pmid": casan[0][1]})
    print(f"  would be rewritten if the rule ran on them anyway: {len(danio)}")
    for e in danio:
        print(f"    !! {e['doi']}  →  {e['seria_reescrito_a']}")

    salida = {
        "fecha": time.strftime("%Y-%m-%d"),
        "corpus": args.corpus,
        "rango": [args.min, args.max],
        "n_dois": len(dois),
        "n_no_existe": len(rotos),
        "con_candidato": len(con_candidato),
        "confirmados": len(confirmados),
        "ambiguos": len(ambiguos),
        "control_con_candidato": len(control),
        "control_danio": len(danio),
        "detalle": confirmados,
        "detalle_ambiguos": ambiguos,
        "detalle_danio": danio,
        "no_rescatados": [d for d in rotos
                          if d not in {e["roto"] for e in confirmados}],
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(salida, f, indent=1, sort_keys=True, ensure_ascii=False)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
