#!/usr/bin/env python3
"""What a Word manuscript's citation fields hold that refcheck does not read.

A .docx written with Zotero, Mendeley or EndNote carries each cited work twice:
once as the printed bibliography, shaped by whatever citation style the author
chose, and once inside the field codes, as the reference manager's own record.
Many styles (Vancouver, APA before 7th, most journal house styles) print no
DOI, so the printed list can be useless to refcheck while the record behind it
holds the DOI and the PMID.

refcheck already reads field instructions (w:instrText) as loose text. This
script measures, on real deposited manuscripts, how much of each record that
loose reading recovers:

  - records: distinct cited works per document, read from the fields
      Zotero / Mendeley:  ADDIN ZOTERO_ITEM CSL_CITATION {json}
                          ADDIN CSL_CITATION {json}
                          -> citationItems[].itemData  (DOI, PMID)
      EndNote:            ADDIN EN.CITE <EndNote>...</EndNote>, inline or as
                          base64 in w:fldData (ADDIN EN.CITE.DATA)
                          -> <electronic-resource-num> (DOI), <accession-num>
  - for each record, whether refcheck's current text (texto_de_docx) yields
    its DOI, and, for a record with a PMID but no DOI, its PMID.

    python3 -I research/measure_docx_fields.py DIR [DIR ...] --json OUT

MIT. No network.
"""
import argparse
import base64
import html
import json
import os
import re
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import refcheck as r  # noqa: E402

PARTES = ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml")
TOKEN = re.compile(
    r"<w:fldChar\b[^>]*w:fldCharType=\"(begin|separate|end)\"[^>]*?(?:/>|>(.*?)</w:fldChar>)"
    r"|<w:instrText(?:\s[^>]*)?>([^<]*)</w:instrText>", re.S)
FLDDATA = re.compile(r"<w:fldData(?:\s[^>]*)?>([^<]*)</w:fldData>", re.S)


def campos(xml):
    """Each field's full instruction, plus its fldData decoded, in order.

    Nested fields are flattened into their outer field, which is enough here:
    citation fields do not nest inside each other.
    """
    salida, prof, actual, datos = [], 0, [], []
    for m in TOKEN.finditer(xml):
        tipo, interior, instr = m.group(1), m.group(2), m.group(3)
        if tipo == "begin":
            if prof == 0:
                actual, datos = [], []
            prof += 1
            for d in FLDDATA.findall(interior or ""):
                datos.append(d)
        elif tipo in ("separate", "end"):
            if tipo == "end":
                prof = max(0, prof - 1)
                if prof == 0 and (actual or datos):
                    salida.append((html.unescape("".join(actual)), datos))
                    actual, datos = [], []
        elif instr is not None and prof:
            actual.append(instr)
    return salida


def _b64(s):
    crudo = base64.b64decode(re.sub(r"\s+", "", s) + "===", validate=False)
    for cod in ("utf-8", "utf-16-le"):
        try:
            t = crudo.decode(cod)
            if "<" in t:
                return t
        except UnicodeDecodeError:
            pass
    return crudo.decode("latin-1")


def _json_tras(instr, clave):
    i = instr.find(clave)
    if i < 0:
        return None
    j = instr.find("{", i)
    if j < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(instr[j:])[0]
    except ValueError:
        return None


def _limpia(doi):
    d = r.dois_de(doi or "")
    return d[0] if d else None


def registros(datos_docx):
    """[(origen, clave, doi, pmid)] for every cited record, one per work."""
    z = zipfile.ZipFile(datos_docx)
    vistos, salida, gestores = set(), [], set()
    for parte in PARTES:
        if parte not in z.namelist():
            continue
        xml = z.read(parte).decode("utf-8", "replace")
        for instr, fld in campos(xml):
            cuerpo = instr.strip()
            if "CSL_CITATION" in cuerpo:
                gestores.add("zotero" if "ZOTERO" in cuerpo else "mendeley/csl")
                # A field can swallow others (a TOC around the whole text, or a
                # missing end): every CSL_CITATION inside it counts.
                items = []
                for trozo in cuerpo.split("CSL_CITATION")[1:]:
                    obj = _json_tras(trozo, "") or {}
                    items.extend(obj.get("citationItems") or [])
                for it in items:
                    d = it.get("itemData") or {}
                    doi = _limpia(str(d.get("DOI") or ""))
                    pmid = str(d.get("PMID") or "").strip() or None
                    clave = doi or (pmid and "pmid:" + pmid) or json.dumps(
                        [d.get("title"), d.get("issued")], sort_keys=True)
                    if clave not in vistos:
                        vistos.add(clave)
                        salida.append(("csl", clave, doi, pmid))
            elif "EN.CITE" in cuerpo:
                gestores.add("endnote")
                texto = cuerpo + "".join(_b64(x) for x in fld)
                for rec in re.findall(r"<record>(.*?)</record>", texto, re.S):
                    m = re.search(r"<electronic-resource-num>(.*?)</electronic-resource-num>", rec, re.S)
                    doi = _limpia(re.sub(r"<[^>]+>", "", m.group(1))) if m else None
                    a = re.search(r"<accession-num>(.*?)</accession-num>", rec, re.S)
                    acc = re.sub(r"<[^>]+>", "", a.group(1)).strip() if a else ""
                    pmid = acc if acc.isdigit() else None
                    n = re.search(r"<rec-number>(\d+)</rec-number>", rec)
                    clave = doi or (pmid and "pmid:" + pmid) or ("en:" + (n.group(1) if n else rec[:80]))
                    if clave not in vistos:
                        vistos.add(clave)
                        salida.append(("endnote", clave, doi, pmid))
    return salida, sorted(gestores)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dirs", nargs="+")
    p.add_argument("--json")
    a = p.parse_args()
    filas, tot = [], dict(docs=0, docs_con_campos=0, registros=0, con_doi=0,
                          doi_leido=0, solo_pmid=0, solo_pmid_leido=0, sin_id=0)
    for dd in a.dirs:
        for nombre in sorted(os.listdir(dd)):
            if not nombre.endswith(".docx"):
                continue
            ruta = os.path.join(dd, nombre)
            tot["docs"] += 1
            try:
                with open(ruta, "rb") as f:
                    crudo = f.read()
                texto = r.texto_de_docx(crudo)
                import io
                regs, gest = registros(io.BytesIO(crudo))
            except Exception as e:
                print(f"  ! {nombre}: {e}")
                continue
            if not regs:
                continue
            tot["docs_con_campos"] += 1
            leidos = {d.lower() for d in r.dois_de(texto)}
            pm_leidos = set(r.pmids_de(texto))
            fila = dict(fichero=nombre, gestores=gest, registros=len(regs),
                        con_doi=0, doi_leido=0, solo_pmid=0, solo_pmid_leido=0, sin_id=0,
                        perdidos=[])
            for origen, clave, doi, pmid in regs:
                if doi:
                    fila["con_doi"] += 1
                    if doi.lower() in leidos:
                        fila["doi_leido"] += 1
                    else:
                        fila["perdidos"].append(doi)
                elif pmid:
                    fila["solo_pmid"] += 1
                    if str(int(pmid)) in pm_leidos:
                        fila["solo_pmid_leido"] += 1
                    else:
                        fila["perdidos"].append("pmid:" + pmid)
                else:
                    fila["sin_id"] += 1
            for k in ("con_doi", "doi_leido", "solo_pmid", "solo_pmid_leido", "sin_id"):
                tot[k] += fila[k]
            tot["registros"] += len(regs)
            filas.append(fila)
            print(f"{nombre:28} {','.join(gest):14} reg={len(regs):4} doi={fila['con_doi']:4}"
                  f" leídos={fila['doi_leido']:4} soloPMID={fila['solo_pmid']:3}"
                  f" leídos={fila['solo_pmid_leido']:3} sinID={fila['sin_id']:3}")
    print(json.dumps(tot))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(total=tot, docs=filas), f, indent=1)


if __name__ == "__main__":
    main()
