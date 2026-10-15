#!/usr/bin/env python3
"""Does refcheck's .docx reader find the DOIs a person would see in the file?

The oracle is LibreOffice, not me: `soffice --convert-to txt` on each file of a
frozen corpus of real manuscripts from Zenodo (research/fetch_ris_corpus.py
--ext docx). Both texts go through the same dois_de(), so the only thing being
compared is the reading of the Word file.

LibreOffice's text export drops field-code instructions, which refcheck keeps
on purpose (HYPERLINK targets, Zotero/EndNote item data). So the comparison is
made twice: with the instructions stripped — that one must agree exactly — and
as shipped, where anything extra must come from a field code and is listed.

    python3 research/measure_docx.py CORPUS_DIR LIBREOFFICE_TXT_DIR [--json OUT]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import refcheck  # noqa: E402

SIN_CAMPOS = re.compile(r"<w:instrText(?:\s[^>]*)?>[^<]*</w:instrText>")


def texto_sin_campos(datos):
    import io
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(datos))
    nombres = set(z.namelist())
    return "\n".join(
        refcheck.texto_de_docx_xml(SIN_CAMPOS.sub("", z.read(n).decode("utf-8", "replace")))
        for n in refcheck.DOCX_PARTES if n in nombres)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("corpus")
    p.add_argument("lo")
    p.add_argument("--json")
    a = p.parse_args()

    filas = []
    for nombre in sorted(f for f in os.listdir(a.corpus) if f.endswith(".docx")):
        datos = open(os.path.join(a.corpus, nombre), "rb").read()
        lo_txt = open(os.path.join(a.lo, nombre[:-5] + ".txt"),
                      encoding="utf-8", errors="replace").read()
        oraculo = set(refcheck.dois_de(lo_txt))
        estricto = set(refcheck.dois_de(texto_sin_campos(datos)))
        entero = set(refcheck.dois_de(refcheck.texto_de_docx(datos)))
        filas.append({
            "fichero": nombre,
            "oraculo": len(oraculo),
            "solo_oraculo": sorted(oraculo - estricto),
            "solo_refcheck_estricto": sorted(estricto - oraculo),
            "extra_por_campos": sorted(entero - estricto),
            "perdidos_con_campos": sorted(estricto - entero),
        })

    tot = sum(f["oraculo"] for f in filas)
    con = sum(1 for f in filas if f["oraculo"])
    falt = sum(len(f["solo_oraculo"]) for f in filas)
    sobr = sum(len(f["solo_refcheck_estricto"]) for f in filas)
    extra = sum(len(f["extra_por_campos"]) for f in filas)
    perd = sum(len(f["perdidos_con_campos"]) for f in filas)
    print(f"{len(filas)} files, {con} with DOIs, {tot} distinct DOIs per LibreOffice")
    print(f"strict reader vs oracle: {falt} missed, {sobr} extra")
    print(f"as shipped: {extra} more from field codes, {perd} lost by keeping them")
    for f in filas:
        for k in ("solo_oraculo", "solo_refcheck_estricto", "extra_por_campos",
                  "perdidos_con_campos"):
            for d in f[k]:
                print(f"  {f['fichero']}  {k}: {d}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"resumen": {"ficheros": len(filas), "con_doi": con,
                                   "dois_oraculo": tot, "perdidos": falt,
                                   "sobrantes": sobr, "extra_campos": extra,
                                   "perdidos_por_campos": perd},
                       "filas": filas}, fh, indent=1)


if __name__ == "__main__":
    main()
