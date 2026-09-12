#!/usr/bin/env python3
"""The other direction: what does Crossref know that PubMed does not?

On 2026-09-11 I measured Crossref against PubMed and found a hole worth fixing:
of the papers PubMed says carry an erratum, Crossref was silent for 21%. refcheck
now asks both registers. But that measurement only sized ONE of the two blind
spots, and a tool that asks two sources should know the shape of both — otherwise
"we ask PubMed too" is a claim, not a measured improvement.

So this script runs the mirror. Take the change notices Crossref holds, follow
each one back to the article it is about, and ask PubMed whether it says anything.

Sampling. Crossref's `sample=` parameter draws at random from the filtered set,
which is the only honest way in: `offset` is capped and the default order is not
random, so paging would measure whichever corner of the index sorts first. The
price is that `sample=` takes no seed, so a run is NOT reproducible bit for bit.
Every sampled DOI goes into --json so a result can still be audited afterwards.

Scope, and it decides how to read the numbers. PubMed indexes biomedicine and
nothing else. A correction on a paper about concrete or Kant is simply outside
its remit, so "not in PubMed" is not a PubMed failure, and the comparable figure
is the one restricted to articles PubMed actually holds. Both are printed.

Standard library only, no API key. NCBI allows 3 requests/second without one and
Crossref 1/s without a mailto; this obeys the lower of what each declares.
Set REFCHECK_MAILTO to be polite (and faster) with Crossref.

    python3 measure_crossref_gap.py                     # 200 per population
    python3 measure_crossref_gap.py --n 400 --json out.json
    python3 measure_crossref_gap.py --only retraction

MIT.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
CROSSREF = "https://api.crossref.org/works"
CONTACT = os.environ.get("REFCHECK_MAILTO", "")
UA = ("refcheck-research/1.0 (https://github.com/KaizenShogun/refcheck"
      + ("; mailto:" + CONTACT if CONTACT else "") + ")")

MUESTRA = 100    # Crossref's cap on `sample`
LOTE = 40        # identifiers per PubMed / Crossref request

# PubMed keeps change notices in CommentsCorrectionsList. These are the RefTypes
# that point FROM an article TO a notice about it. CommentIn is deliberately not
# here: a letter commenting on a paper is not a correction to it, and counting it
# would inflate PubMed's score with things a reader must not act on.
AVISO_PM = {
    "RetractionIn": "retraction",
    "PartialRetractionIn": "retraction",
    "ExpressionOfConcernIn": "concern",
    "ErratumIn": "correction",
    "CorrectedandRepublishedIn": "correction",
    "RepublishedIn": "correction",
    "UpdateIn": "edition",
}

# What we sample from Crossref, and which PubMed verdict counts as the same news.
POBLACIONES = {
    "retraction": {"filtro": "retraction", "equivale": {"retraction"}},
    "concern": {"filtro": "expression_of_concern", "equivale": {"concern"}},
    "correction": {"filtro": "correction", "equivale": {"correction"}},
    "erratum": {"filtro": "erratum", "equivale": {"correction"}},
}


class Ritmo:
    """One pacer per host, following the rate that host declares."""

    def __init__(self, limite=1, intervalo=1.0):
        self.limite, self.intervalo, self.ultima = limite, intervalo, 0.0

    def aprende(self, cab):
        crudo = cab.get("x-rate-limit-limit")
        por_segundo = crudo is None
        if por_segundo:
            crudo = cab.get("x-ratelimit-limit")
        try:
            limite = int(crudo or 0)
            iv = (cab.get("x-rate-limit-interval", "") or "").strip().lower()
            intervalo = 1.0 if (por_segundo and not iv) else float(iv.rstrip("s"))
        except (TypeError, ValueError):
            return
        if limite > 0 and intervalo > 0:
            self.limite, self.intervalo = limite, intervalo

    def espera(self):
        queda = self.intervalo / self.limite - (time.monotonic() - self.ultima)
        if queda > 0:
            time.sleep(queda)
        self.ultima = time.monotonic()


NCBI = Ritmo(3, 1.0)
CR = Ritmo(1, 1.0)


def pide(url, ritmo, reintentos=3, timeout=60):
    ultimo = None
    for intento in range(reintentos):
        try:
            ritmo.espera()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                ritmo.aprende(r.headers)
                return r.read()
        except Exception as e:                      # noqa: BLE001 - retried below
            ultimo = e
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
    raise ConnectionError(f"{url.split('?')[0]}: {ultimo}")


# -------------------------------------------------------------- Crossref side

def muestra_avisos(tipo, n, verboso=True):
    """Draw notice records of one update-type and follow them back to the articles.

    A notice can point at more than one article, and at the same article twice
    with two different verdicts — that second case is the contradiction bug
    (Crossref CR-2746) and it is counted once here, under the type we asked for.
    """
    equivalentes = POBLACIONES[tipo]["filtro"]
    vistos, articulos, total, mudos = set(), {}, 0, 0
    while len(articulos) < n:
        url = (f"{CROSSREF}?filter=update-type:{equivalentes}&sample={MUESTRA}"
               "&select=DOI,update-to")
        m = json.loads(pide(url, CR))["message"]
        total = m.get("total-results", 0)
        nuevos = 0
        for it in m.get("items") or []:
            aviso = str(it.get("DOI", "")).lower()
            if aviso in vistos:
                continue
            vistos.add(aviso)
            nuevos += 1
            # A notice with no update-to naming an article of the type we asked
            # for points at nothing a DOI checker can follow. Counted, because
            # it is a hole in the register that neither this script nor refcheck
            # can see past, and silence about it would flatter both.
            if not [d for d in (it.get("update-to") or [])
                    if str(d.get("type", "")) == equivalentes
                    and str(d.get("DOI", "")).lower().strip() not in ("", aviso)]:
                mudos += 1
            for destino in it.get("update-to") or []:
                if str(destino.get("type", "")) != equivalentes:
                    continue
                art = str(destino.get("DOI", "")).lower().strip()
                # A notice that points at itself is a deposit error, not an
                # article with a notice; counting it would credit both registers
                # with news that does not exist.
                if art and art != aviso and art not in articulos:
                    articulos[art] = aviso
                    if len(articulos) >= n:
                        break
            if len(articulos) >= n:
                break
        if nuevos == 0:                              # the pool is smaller than n
            break
        if verboso:
            print(f"   {len(articulos):,}/{n} articles from {len(vistos):,} "
                  f"sampled notices", file=sys.stderr)
    return total, articulos, mudos, len(vistos)


def ficha_crossref(dois):
    """{doi: year} for the articles Crossref holds, so the era table covers the
    ones PubMed never had."""
    salida = {}
    for i in range(0, len(dois), LOTE):
        trozo = dois[i:i + LOTE]
        filtro = ",".join("doi:" + urllib.parse.quote(d, safe="") for d in trozo)
        url = f"{CROSSREF}?rows={len(trozo)}&select=DOI,issued&filter={filtro}"
        for w in json.loads(pide(url, CR))["message"].get("items") or []:
            partes = ((w.get("issued") or {}).get("date-parts") or [[None]])[0]
            anno = partes[0] if partes and isinstance(partes[0], int) else 0
            salida[str(w.get("DOI", "")).lower()] = anno
    return salida


# ---------------------------------------------------------------- PubMed side

def pregunta_pubmed(dois, verboso=True):
    """{doi: [RefType…]} for the DOIs PubMed holds. Absent = not indexed there.

    Batched: one esearch per 40 DOIs joined with OR, then one efetch for the
    PMIDs it returns. The mapping back is by DOI, which every record carries,
    so nothing depends on the order PubMed answers in.
    """
    salida = {}
    for i in range(0, len(dois), LOTE):
        trozo = dois[i:i + LOTE]
        term = " OR ".join('"%s"[AID]' % d for d in trozo)
        url = (EUTILS + "esearch.fcgi?db=pubmed&retmode=json&retmax=200&term="
               + urllib.parse.quote(term))
        ids = (json.loads(pide(url, NCBI))["esearchresult"].get("idlist") or [])
        if verboso:
            print(f"   PubMed: {len(ids)} of {len(trozo)} indexed", file=sys.stderr)
        if not ids:
            continue
        xml = pide(EUTILS + "efetch.fcgi?db=pubmed&retmode=xml&id=" + ",".join(ids),
                   NCBI)
        salida.update(analiza(xml))
    return salida


def rescata(dois, verboso=True):
    """Second opinion on the DOIs that [AID] did not find.

    "Not in PubMed" is a claim about PubMed, so it should not rest on one field
    of one query. Some DOIs are ugly — `10.1002/(SICI)1097-0142(19970615)79:12<…`
    has parentheses, colons and angle brackets, all of which mean something to
    Entrez — and a query that silently fails to parse looks exactly like an
    article PubMed never indexed. So each absentee is asked again, alone and
    unfielded, and only counted absent if that fails too.

    Returns {doi: [RefType…]} for the ones this rescues, which is also the error
    rate of the fast path and worth printing rather than hiding.
    """
    salvados = {}
    for doi in dois:
        url = (EUTILS + "esearch.fcgi?db=pubmed&retmode=json&retmax=20&term="
               + urllib.parse.quote(doi))
        ids = (json.loads(pide(url, NCBI))["esearchresult"].get("idlist") or [])
        if not ids:
            continue
        xml = pide(EUTILS + "efetch.fcgi?db=pubmed&retmode=xml&id=" + ",".join(ids),
                   NCBI)
        # An unfielded search matches loosely, so keep only a record whose own
        # DOI is the one asked for. Otherwise a paper that merely cites it counts.
        hallado = analiza(xml)
        if doi in hallado:
            salvados[doi] = hallado[doi]
    if verboso and salvados:
        print(f"   rescued {len(salvados)} of {len(dois)} absentees on the second "
              "query", file=sys.stderr)
    return salvados


def analiza(xml):
    raiz = ET.fromstring(xml)
    salida = {}
    for art in raiz.iter("PubmedArticle"):
        cita = art.find("MedlineCitation")
        if cita is None or cita.find("PMID") is None:
            continue
        # Scope every lookup to the element that owns it: a bare iter() over the
        # article would return DOIs out of <ReferenceList>, i.e. other people's
        # papers, for any record without a DOI of its own.
        doi = ""
        for aid in art.findall("./PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi" and (aid.text or "").strip():
                doi = aid.text.strip().lower()
                break
        if not doi:
            for el in cita.findall("./Article/ELocationID"):
                if el.get("EIdType") == "doi" and (el.text or "").strip():
                    doi = el.text.strip().lower()
                    break
        if not doi:
            continue
        salida[doi] = [cc.get("RefType", "") for cc in
                       cita.findall("./CommentsCorrectionsList/CommentsCorrections")]
    return salida


# ------------------------------------------------------------------ the count

EPOCAS = [(0, 1999, "…1999"), (2000, 2009, "2000-09"), (2010, 2014, "2010-14"),
          (2015, 2019, "2015-19"), (2020, 2026, "2020-")]


def epoca(anno):
    if not anno:
        return "unknown"
    for a, b, nombre in EPOCAS:
        if a <= anno <= b:
            return nombre
    return "unknown"


def mide(clave, n, verboso=True):
    pob = POBLACIONES[clave]
    if verboso:
        print(f"== {clave}: sampling Crossref notices", file=sys.stderr)
    total, articulos, mudos, avisos = muestra_avisos(clave, n, verboso)
    dois = list(articulos)
    if verboso:
        print(f"   {len(dois)} articles, of {total:,} {clave} notices registered",
              file=sys.stderr)
    annos = ficha_crossref(dois)
    pm = pregunta_pubmed(dois, verboso)
    salvados = rescata([d for d in dois if d not in pm], verboso)
    pm.update(salvados)

    filas, cuenta = [], {"fuera": 0, "callado": 0, "otro": 0, "igual": 0}
    for doi in dois:
        refs = pm.get(doi)
        if refs is None:
            estado = "fuera"                        # not indexed in PubMed at all
            tipos = []
        else:
            tipos = sorted({AVISO_PM[r] for r in refs if r in AVISO_PM})
            if not tipos:
                estado = "callado"                  # indexed, says nothing
            elif set(tipos) & pob["equivale"]:
                estado = "igual"                    # says the same kind of news
            else:
                estado = "otro"                     # says something, other kind
        cuenta[estado] += 1
        filas.append({"doi": doi, "aviso": articulos[doi], "anno": annos.get(doi, 0),
                      "epoca": epoca(annos.get(doi, 0)), "estado": estado,
                      "pubmed": tipos, "reftypes": refs or []})
    return {"poblacion": clave, "registrados": total, "n": len(dois),
            "rescatados": len(salvados), "sin_destino": mudos,
            "avisos_muestreados": avisos,
            "cuenta": cuenta, "filas": filas}


def porcentaje(parte, total):
    return f"{100.0 * parte / total:.1f}%" if total else "—"


def informa(res):
    c, n = res["cuenta"], res["n"]
    dentro = n - c["fuera"]
    visto = c["igual"] + c["otro"]
    print(f"\n== {res['poblacion']}: {res['registrados']:,} notices registered in "
          f"Crossref, {n} articles sampled")
    print(f"   not indexed in PubMed at all : {c['fuera']:4d}  {porcentaje(c['fuera'], n)}"
          "   (out of PubMed's scope, not a miss)")
    print(f"   PubMed says the same kind    : {c['igual']:4d}  {porcentaje(c['igual'], dentro)} of the {dentro} it holds")
    print(f"   PubMed says a different kind : {c['otro']:4d}  {porcentaje(c['otro'], dentro)}")
    print(f"   PubMed silent                : {c['callado']:4d}  {porcentaje(c['callado'], dentro)}")
    print(f"   → asking PubMed alone would have caught {porcentaje(visto, dentro)} "
          f"of these, and {porcentaje(visto, n)} counting the ones it never indexed")
    if res.get("sin_destino"):
        print(f"   ({res['sin_destino']} of the {res.get('avisos_muestreados', 0)} "
              "sampled notices named no article of this kind at all, so nothing "
              "could follow them back)")
    if res.get("rescatados"):
        print(f"   ({res['rescatados']} of them were only found by the second, "
              "unfielded query — that is this script's own error rate)")

    por_epoca = {}
    for f in res["filas"]:
        if f["estado"] == "fuera":
            continue
        d = por_epoca.setdefault(f["epoca"], [0, 0])
        d[1] += 1
        if f["estado"] in ("igual", "otro"):
            d[0] += 1
    orden = [e[2] for e in EPOCAS] + ["unknown"]
    vivos = [(e, por_epoca[e]) for e in orden if e in por_epoca]
    if len(vivos) > 1:
        print("   by year of the article (of the ones PubMed holds):")
        for nombre, (ok, tot) in vivos:
            print(f"     {nombre:>8}  {porcentaje(ok, tot):>6}  ({ok}/{tot})")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=200, help="articles per population")
    p.add_argument("--only", choices=sorted(POBLACIONES), action="append",
                   help="measure only this population (repeatable)")
    p.add_argument("--json", metavar="FILE", help="write every sampled DOI here")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()

    claves = a.only or sorted(POBLACIONES)
    salida = []
    for clave in claves:
        try:
            res = mide(clave, a.n, not a.quiet)
        except (ConnectionError, urllib.error.URLError) as e:
            print(f"!! {clave}: {e}", file=sys.stderr)
            continue
        informa(res)
        salida.append(res)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"medido": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                       "nota": "Crossref sample= takes no seed; not reproducible "
                               "bit for bit, which is why every DOI is here",
                       "poblaciones": salida}, fh, indent=1)
        print(f"\nwritten: {a.json}")
    return 0 if salida else 1


if __name__ == "__main__":
    sys.exit(main())
