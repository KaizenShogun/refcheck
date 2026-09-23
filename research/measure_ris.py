#!/usr/bin/env python3
"""What a .ris file costs a reader, measured on .ris files real people deposited.

refcheck read `.ris` down the loose-text path until 2026-09-23, under a comment
claiming its DOIs "are found perfectly well". This measures that claim, and then
measures the damage of the reader that replaced it — because a fix that quietly
drops references that used to be checked is not a fix.

Corpus: .ris files deposited on Zenodo beside real systematic reviews, exported
by Scopus, Web of Science, Embase, Rayyan, Zotero and Publish or Perish.
Frozen by research/fetch_ris_corpus.py with a manifest, so a change in these
numbers is a change in the code and not in the sample — the lesson of
2026-09-18, when I published a comparison between two different samples.

    python3 research/fetch_ris_corpus.py --out ris_corpus/
    python3 research/measure_ris.py ris_corpus/

`--confirma` additionally asks Crossref for the title of every DOI that ONLY the
old loose reader found, and compares it with the record's own title, which is
what separates "the abstract quotes this paper's own DOI" from "the abstract
cites somebody else's". Network, one batch per 40 DOIs, polite by default.

MIT. No key, no third-party dependency.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The real code, imported and not copied.
import refcheck

AGENTE = "refcheck-research/1.0 (https://github.com/KaizenShogun/refcheck)"


def registros_crudos(texto):
    """Split into records the way the file itself does, for counting only."""
    trozos = re.split(r"(?m)^ER\s{1,2}-.*$", texto)
    return [t for t in trozos if re.search(r"(?m)^TY\s{1,2}-", t)]


def normaliza(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def titulo_de(registro):
    m = re.search(r"(?m)^T[I1]\s{1,2}-\s*(.*)$", registro)
    return m.group(1).strip() if m else ""


def titulos_crossref(dois, pausa=1.0):
    """Crossref's title for each DOI, in batches. {} on any failure."""
    fuera = {}
    for i in range(0, len(dois), 40):
        lote = dois[i:i + 40]
        filtro = ",".join("doi:" + d for d in lote)
        url = ("https://api.crossref.org/works?rows=40&select=DOI,title&filter="
               + urllib.parse.quote(filtro, safe=":,/"))
        try:
            time.sleep(pausa)
            req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=60) as r:
                datos = json.load(r)
            for it in datos["message"]["items"]:
                fuera[it["DOI"].lower()] = " ".join(it.get("title") or [])
        except Exception as e:
            print(f"  ! Crossref batch failed: {e}", file=sys.stderr)
    return fuera


def main():
    p = argparse.ArgumentParser()
    p.add_argument("corpus")
    p.add_argument("--confirma", action="store_true",
                   help="ask Crossref whether a free-text DOI is the record's own")
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument("--json", dest="salida", default="")
    a = p.parse_args()

    ficheros = sorted(f for f in os.listdir(a.corpus) if f.lower().endswith(".ris"))
    total = reconocidos = registros = 0
    sin_id = con_doi = con_pmid = 0
    perdidos = []          # (fichero, titulo, doi) the loose reader found and the RIS one does not
    ganados = 0            # records that were invisible and are now named
    no_ris = []

    for f in ficheros:
        ruta = os.path.join(a.corpus, f)
        texto = open(ruta, encoding="utf-8", errors="replace").read()
        total += 1
        if not refcheck.es_ris(texto):
            no_ris.append(f)
            continue
        reconocidos += 1
        crudos = registros_crudos(texto)
        regs = refcheck.registros_ris(texto)
        registros += len(regs)
        for reg, crudo in zip(regs, crudos + [""] * (len(regs) - len(crudos))):
            if reg["doi"]:
                con_doi += 1
            elif reg["pmid"]:
                con_pmid += 1
            else:
                sin_id += 1
                # Did the loose reader have anything here that the RIS reader
                # does not? That is the damage, and it is the only definition
                # that counts: it used to be checked and now it is not.
                sueltos = [refcheck._limpia_doi(d)
                           for d in refcheck.DOI_RE.findall(crudo)]
                if sueltos:
                    perdidos.append((f, titulo_de(crudo), sueltos[0]))
                else:
                    ganados += 1

    print(f"files in corpus              {total}")
    print(f"  recognised as RIS          {reconocidos}")
    if no_ris:
        print(f"  NOT RIS (correctly)        {len(no_ris)}: {', '.join(no_ris)}")
    print(f"\nrecords read                 {registros:,}")
    print(f"  with a DOI of their own    {con_doi:,}  ({100*con_doi/registros:.1f}%)")
    print(f"  with a PMID and no DOI     {con_pmid:,}  ({100*con_pmid/registros:.1f}%)")
    print(f"  with NO checkable id       {sin_id:,}  ({100*sin_id/registros:.1f}%)")
    print(f"\nof those with no id:")
    print(f"  invisible before, named now          {ganados:,}")
    print(f"  the loose reader did find a DOI here {len(perdidos):,}  <- the damage")

    # The other side of the ledger, and the one the damage column alone hides:
    # DOIs the loose reader pulled out of the file that belong to NO record in
    # it — an abstract citing the study it replicates, a dataset DOI in a note.
    # Those were reported to the reader as their own references.
    extra_total = 0
    for f in ficheros:
        texto = open(os.path.join(a.corpus, f), encoding="utf-8",
                     errors="replace").read()
        if not refcheck.es_ris(texto):
            continue
        sueltos = {d.lower() for d in refcheck.dois_de(texto)}
        propios = {r["doi"].lower() for r in refcheck.registros_ris(texto)
                   if r["doi"]}
        extra_total += len(sueltos - propios)
    print(f"\nDOIs the loose reader reported that belong to no record: {extra_total:,}")
    print(f"  (those were shown to the reader as references of their own)")
    resultado_extra = extra_total

    resultado = {
        "ficheros": total, "ris": reconocidos, "no_ris": no_ris,
        "registros": registros, "con_doi": con_doi, "con_pmid": con_pmid,
        "sin_id": sin_id, "ganados": ganados, "dois_de_nadie": resultado_extra,
        "perdidos": [{"fichero": f, "titulo": t, "doi": d} for f, t, d in perdidos],
    }

    if a.confirma and perdidos:
        print(f"\nasking Crossref whose paper those {len(perdidos)} DOIs are…")
        titulos = titulos_crossref([d for _, _, d in perdidos], a.pausa)
        propio = ajeno = desconocido = 0
        for f, ti, d in perdidos:
            cr = titulos.get(d.lower())
            if cr is None:
                desconocido += 1
                estado = "not in Crossref"
            else:
                n_cr, n_ris = normaliza(cr), normaliza(ti)
                mismo = bool(n_cr) and bool(n_ris) and (
                    n_cr[:40] in n_ris or n_ris[:40] in n_cr)
                if mismo:
                    propio += 1
                    estado = "the record's OWN doi"
                else:
                    ajeno += 1
                    estado = "A STRANGER'S"
            print(f"  {estado:22} {d}")
            print(f"     file : {ti[:72]}")
            if titulos.get(d.lower()) is not None:
                print(f"     doi  : {titulos[d.lower()][:72]}")
        print(f"\n  the record's own     {propio}")
        print(f"  a stranger's         {ajeno}   <- would have been reported as"
              " the reader's reference")
        print(f"  not in Crossref      {desconocido}")
        resultado["confirmacion"] = {"propio": propio, "ajeno": ajeno,
                                     "desconocido": desconocido}

    if a.salida:
        with open(a.salida, "w") as fh:
            json.dump(resultado, fh, indent=1)
        print(f"\n-> {a.salida}")


if __name__ == "__main__":
    main()
