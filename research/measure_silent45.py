"""The retractions PubMed is silent on, looked at one by one.

Takes the rows `measure_pmid_only.py` filed as "Retraction | silent" (RW says
retracted, PubMed's record for that PMID lists no RetractionIn) and asks PubMed
for each full record, to answer two questions:

  · does the record carry `Retracted Publication` in PublicationTypeList
    without the RetractionIn link? (then the type could be read)
  · is the PMID RW gives as the "original paper" the retraction NOTICE itself?
    (RetractionOf in CommentsCorrections, or a title that announces it)

    python3 -I research/measure_silent45.py research/pmid_only_20261018.json OUT.json
"""
import json, re, sys, urllib.request
import xml.etree.ElementTree as ET

entrada, salida = sys.argv[1], sys.argv[2]
d = json.load(open(entrada))
pmids = [f["pmid"] for f in d["filas"] if f["nat"] == "Retraction" and f["cajon"] == "silent"]
url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml"
       "&tool=refcheck&id=" + ",".join(pmids))
xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "refcheck-measure"}),
                             timeout=60).read()
# A title that announces a notice. Anchored and with punctuation, because
# "[Retraction, hyperextensibility and weakness in cerebral palsy]" is in this
# very set and is about muscles.
ANUNCIA = re.compile(r"^\W*(retraction\s*[:.]|retracted\b|article retraction|notice of retraction)", re.I)
filas = []
for a in ET.fromstring(xml):
    pmid = a.findtext(".//PMID")
    titulo = a.findtext(".//ArticleTitle") or a.findtext(".//BookTitle") or ""
    tipos = [p.text for p in a.iter("PublicationType")]
    refs = [x.get("RefType") for x in a.iter("CommentsCorrections")]
    filas.append({"pmid": pmid, "titulo": titulo[:120],
                  "tipo_retracted": "Retracted Publication" in tipos,
                  "retraction_of": "RetractionOf" in refs,
                  "titulo_anuncia": bool(ANUNCIA.match(titulo))})
t = {"pedidos": len(pmids), "devueltos": len(filas),
     "con_tipo_retracted": sum(f["tipo_retracted"] for f in filas),
     "es_el_aviso_por_RetractionOf": sum(f["retraction_of"] for f in filas),
     "es_el_aviso_solo_por_titulo": sum(f["titulo_anuncia"] and not f["retraction_of"] for f in filas),
     "nada": sum(not (f["retraction_of"] or f["titulo_anuncia"] or f["tipo_retracted"]) for f in filas)}
json.dump({"tabla": t, "filas": filas}, open(salida, "w"), indent=1, ensure_ascii=False)
print(json.dumps(t))
