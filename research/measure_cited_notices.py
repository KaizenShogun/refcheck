"""How many references in real bibliographies are themselves change notices?

Reads every DOI from the frozen RIS and CSL corpora (the same files every other
extractor measurement uses), asks Crossref in batches with the select the tool
now sends, and counts the records whose `update-to` names another DOI. Then asks
about those targets, as the tool does, and tabulates what the target carries.

    python3 -I research/measure_cited_notices.py ../ris_corpus ../csl_corpus OUT.json
"""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import refcheck as rc

ris, csl, salida = sys.argv[1], sys.argv[2], sys.argv[3]
dois, de = [], {}
for f in sorted(glob.glob(os.path.join(ris, "*.ris"))) + sorted(glob.glob(os.path.join(csl, "*.json"))):
    texto = open(f, encoding="utf-8", errors="replace").read()
    regs = rc.registros_ris(texto) if f.endswith(".ris") else rc.registros_csl(texto)
    for r in regs:
        d = (r.get("doi") or "").lower()
        if d and d not in de:
            de[d] = os.path.basename(f); dois.append(d)
print("DOI distintos:", len(dois), file=sys.stderr)
res, fallos = [], 0
for i in range(0, len(dois), rc.LOTE):
    trozo = dois[i:i + rc.LOTE]
    try:
        obras = rc.consulta_lote(trozo)
    except ConnectionError:
        fallos += len(trozo); continue
    for d in trozo:
        if d in obras:
            res.append(rc.ficha(d, obras[d]))
    if i // rc.LOTE % 20 == 0:
        print(i, len(dois), file=sys.stderr)
rc.estado_de_objetivos(res)
avisos = [r for r in res if r.get("es_aviso")]
filas = []
for r in avisos:
    for e in r["es_aviso"]:
        peor = (e.get("avisos_objetivo") or [{}])[0]
        filas.append({"doi": r["doi"], "fichero": de[r["doi"]], "tipo": e["tipo"],
                      "objetivo": e["doi"], "peor_del_objetivo": peor.get("tipo"),
                      # The tool's own rule, per reference, not a re-implementation.
                      "referencia_peor": rc.peor_que_el_aviso(r),
                      "error": e.get("objetivo_error"), "desconocido": e.get("objetivo_desconocido", False)})
json.dump({"dois": len(dois), "en_crossref": len(res), "fallos_consulta": fallos,
           "referencias_aviso": len(avisos), "filas": filas}, open(salida, "w"), indent=1)
print(json.dumps({"dois": len(dois), "en_crossref": len(res), "fallos": fallos,
                  "referencias_aviso": len(avisos),
                  "referencias_peor": sum(rc.peor_que_el_aviso(r) for r in avisos)}))
