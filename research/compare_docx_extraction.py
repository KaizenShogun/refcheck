#!/usr/bin/env python3
"""Every DOI and PMID two versions of refcheck pull out of the same .docx files.

The control for a change to the Word reader: what it adds, what it drops,
document by document, on frozen corpora. Old version from git:

    git show HEAD:refcheck.py > /tmp/rc_old/refcheck.py
    python3 -I research/compare_docx_extraction.py /tmp/rc_old/refcheck.py DIR...

MIT. No network.
"""
import importlib.util
import json
import os
import sys

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carga(ruta, nombre):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    viejo = carga(sys.argv[1], "rc_viejo")
    nuevo = carga(os.path.join(AQUI, "refcheck.py"), "rc_nuevo")
    tot = dict(docs=0, ilegibles=0, dois_antes=0, dois_ahora=0, pmids_antes=0, pmids_ahora=0)
    cambios = []
    for d in sys.argv[2:]:
        for f in sorted(os.listdir(d)):
            if not f.endswith(".docx"):
                continue
            with open(os.path.join(d, f), "rb") as fh:
                b = fh.read()
            try:
                tv, tn = viejo.texto_de_docx(b), nuevo.texto_de_docx(b)
            except ValueError:
                tot["ilegibles"] += 1
                continue
            tot["docs"] += 1
            dv = {x.lower() for x in viejo.dois_de(tv)}
            dn = {x.lower() for x in nuevo.dois_de(tn)}
            pv, pn = set(viejo.pmids_de(tv)), set(nuevo.pmids_de(tn))
            tot["dois_antes"] += len(dv)
            tot["dois_ahora"] += len(dn)
            tot["pmids_antes"] += len(pv)
            tot["pmids_ahora"] += len(pn)
            if dv != dn or pv != pn:
                c = dict(fichero=f, doi_mas=sorted(dn - dv), doi_menos=sorted(dv - dn),
                         pmid_mas=sorted(pn - pv), pmid_menos=sorted(pv - pn))
                cambios.append(c)
                print(json.dumps(c))
    print(json.dumps(tot))


if __name__ == "__main__":
    main()
