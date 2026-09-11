#!/usr/bin/env python3
"""How much does Crossref alone miss? Measured against PubMed.

refcheck asks Crossref: "does this DOI carry an `updated-by` assertion?" That is
the right field, but it only holds what somebody deposited. PubMed keeps the same
information independently, in `CommentsCorrectionsList`, built by NLM indexers
rather than by the publisher's deposit pipeline. If the two disagree, the gap is
the size of refcheck's blind spot — and a blind spot in this tool reads to the
user as "your citation is clean".

So: take articles that PubMed says carry a notice, and ask Crossref about them.

Sampling. Three PubMed publication types give three populations:

    "retracted publication"[pt]   the retracted ARTICLE itself
    "published erratum"[pt]       the erratum NOTICE (followed back via
                                  RefType=ErratumFor to the article it corrects)
    "expression of concern"[pt]   the EoC NOTICE (followed back the same way)

Sampling is stratified, not one contiguous slice: N random blocks spread across
the whole result set, because PubMed returns newest-first and a single slice
would measure one month of deposit practice rather than the record as a whole.

Standard library only, no API key. NCBI allows 3 requests/second without a key
and Crossref 1/s without a mailto; this obeys the lower of what each declares.
Set REFCHECK_MAILTO to be polite (and faster) with Crossref.

    python3 measure_pubmed_gap.py                      # 200 per population
    python3 measure_pubmed_gap.py --n 400 --json out.json
    python3 measure_pubmed_gap.py --only retraction

MIT.
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
CROSSREF = "https://api.crossref.org/works"
CONTACT = os.environ.get("REFCHECK_MAILTO", "")
UA = ("refcheck-research/1.0 (https://github.com/KaizenShogun/refcheck"
      + ("; mailto:" + CONTACT if CONTACT else "") + ")")

BLOQUE = 10      # PMIDs per random block. Small blocks, many of them.
LOTE_CR = 40     # DOIs per Crossref request, same as refcheck itself.

# Which PubMed population, and how to get from the sampled record to the ARTICLE
# whose DOI we must ask Crossref about. For a retraction the sampled record is
# already the article; for the other two it is the notice, and the article is
# behind the *For link.
POBLACIONES = {
    "retraction": {
        "term": '"retracted publication"[pt]',
        "sigue": None,
        "que_es": "the retracted article itself",
    },
    "erratum": {
        "term": '"published erratum"[pt]',
        "sigue": "ErratumFor",
        "que_es": "the erratum notice, followed back to the corrected article",
    },
    "concern": {
        "term": '"expression of concern"[pt]',
        "sigue": "ExpressionOfConcernFor",
        "que_es": "the EoC notice, followed back to the article",
    },
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


NCBI = Ritmo(3, 1.0)     # NCBI's published limit without a key.
CR = Ritmo(1, 1.0)       # Crossref's public pool; raised if the header says so.


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


# ---------------------------------------------------------------- PubMed side

TECHO = 9998        # measured: efetch off the history server rejects retstart
                    # >= 9999 with a 400, whatever the result set holds. So a
                    # query bigger than that has a tail you simply cannot reach.
LIMITE = 9000       # keep every stratum comfortably under it


def busca(term):
    """esearch with history. Returns (count, webenv, query_key)."""
    url = (EUTILS + "esearch.fcgi?db=pubmed&retmode=json&retmax=0&usehistory=y&term="
           + urllib.parse.quote(term))
    r = json.loads(pide(url, NCBI))["esearchresult"]
    return int(r["count"]), r["webenv"], r["querykey"]


def estratos(term, desde=date(1800, 1, 1), hasta=date(2026, 12, 31), verboso=True):
    """Split by publication DATE until every stratum fits under the retstart cap.

    Without this the sample can only ever come from the 9,998 most recent
    matches — which for errata is the last three years, i.e. a measurement of
    current deposit practice dressed up as a measurement of the record.

    Splitting by year is not enough either: 2019 alone holds 16,544 errata, so a
    year-sized stratum would still hide its own tail. Days are the finest unit
    [dp] takes, and no single day comes close to the cap.
    """
    pendientes, hojas = [(desde, hasta)], []
    while pendientes:
        a, b = pendientes.pop()
        consulta = (f'({term}) AND ("{a:%Y/%m/%d}"[dp] : "{b:%Y/%m/%d}"[dp])')
        n, we, qk = busca(consulta)
        if n == 0:
            continue
        if n <= LIMITE or a == b:
            if n > TECHO:
                # A single day over the cap would be unreachable in its tail,
                # and pretending otherwise would silently bias the draw.
                print(f"   warning: {a} alone holds {n:,}, only the first "
                      f"{TECHO:,} are reachable", file=sys.stderr)
            hojas.append({"desde": a, "hasta": b, "n": n, "webenv": we, "qk": qk})
        else:
            medio = a + timedelta(days=(b - a).days // 2)
            pendientes += [(a, medio), (medio + timedelta(days=1), b)]
    hojas.sort(key=lambda h: h["desde"])
    if verboso:
        marco = sum(h["n"] for h in hojas)
        entero, _, _ = busca(term)
        print(f"   {len(hojas)} strata, {marco:,} records "
              f"(the unsliced query returns {entero:,})", file=sys.stderr)
        if marco > entero:
            # A record whose PubDate is a range ("1998-1999") satisfies the [dp]
            # filter of both strata it straddles, so the frame counts it twice
            # and those records are drawn slightly more often than the rest.
            print(f"   note: {marco - entero:,} ({100.0*(marco-entero)/entero:.1f}%) "
                  "straddle a stratum boundary and are counted twice",
                  file=sys.stderr)
    return hojas


def bloque_registros(webenv, querykey, retstart, retmax):
    """efetch straight off the history server — no need to list the PMIDs first."""
    url = (f"{EUTILS}efetch.fcgi?db=pubmed&retmode=xml&WebEnv={webenv}"
           f"&query_key={querykey}&retstart={retstart}&retmax={retmax}")
    return analiza(pide(url, NCBI))


def trae_registros(pmids):
    """efetch a batch; return {pmid: {"doi":…, "enlaces":[(reftype, pmid)…]}}."""
    if not pmids:
        return {}
    url = (EUTILS + "efetch.fcgi?db=pubmed&retmode=xml&id=" + ",".join(pmids))
    return analiza(pide(url, NCBI))


def analiza(xml):
    raiz = ET.fromstring(xml)
    salida = {}
    for art in raiz.iter("PubmedArticle"):
        # The PMID of the record is the one directly under MedlineCitation;
        # every other <PMID> in the tree belongs to a reference or a linked item.
        cita = art.find("MedlineCitation")
        if cita is None or cita.find("PMID") is None:
            continue
        pmid = (cita.find("PMID").text or "").strip()
        # Scope every lookup to the element that owns it. A bare iter() over the
        # whole PubmedArticle would happily return a DOI from <ReferenceList> —
        # somebody else's paper — for any article that has no DOI of its own.
        doi = ""
        for aid in art.findall("./PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi" and (aid.text or "").strip():
                doi = aid.text.strip().lower()
                break
        if not doi:                                  # ELocationID is the other place
            for el in cita.findall("./Article/ELocationID"):
                if el.get("EIdType") == "doi" and (el.text or "").strip():
                    doi = el.text.strip().lower()
                    break
        anno = 0
        for etiqueta in ("./Article/Journal/JournalIssue/PubDate/Year",
                         "./Article/Journal/JournalIssue/PubDate/MedlineDate"):
            el = cita.find(etiqueta)
            if el is not None and (el.text or "").strip()[:4].isdigit():
                anno = int(el.text.strip()[:4])
                break
        enlaces = []
        for cc in cita.findall("./CommentsCorrectionsList/CommentsCorrections"):
            p = cc.find("PMID")
            enlaces.append((cc.get("RefType", ""),
                            (p.text or "").strip() if p is not None else ""))
        salida[pmid] = {"doi": doi, "anno": anno, "enlaces": enlaces}
    return salida


def muestra(term, n, semilla):
    """N records drawn at random across the whole population, via date strata.

    Each draw picks a stratum with probability proportional to its size and then
    a random offset inside it, so every record has the same chance of being
    drawn regardless of when it was published.
    """
    hojas = estratos(term)
    total = sum(h["n"] for h in hojas)
    rnd = random.Random(semilla)
    pesos = [h["n"] for h in hojas]
    bloques = max(1, -(-n // BLOQUE))
    registros, orden = {}, []
    for _ in range(bloques):
        h = rnd.choices(hojas, weights=pesos, k=1)[0]
        tope = min(h["n"], TECHO) - BLOQUE
        arranque = rnd.randint(0, tope) if tope > 0 else 0
        for pmid, r in bloque_registros(h["webenv"], h["qk"], arranque, BLOQUE).items():
            # Two draws landing in the same place overlap; the dict absorbs it,
            # and `orden` keeps the sample size honest by counting each once.
            if pmid not in registros:
                registros[pmid] = r
                orden.append(pmid)
    orden = orden[:n]
    return total, orden, {p: registros[p] for p in orden}


# -------------------------------------------------------------- Crossref side

def updated_by(dois):
    """{doi: [update types…]} for the DOIs Crossref holds. Absent = no record."""
    salida = {}
    for i in range(0, len(dois), LOTE_CR):
        trozo = dois[i:i + LOTE_CR]
        filtro = ",".join("doi:" + urllib.parse.quote(d, safe="") for d in trozo)
        url = f"{CROSSREF}?rows={len(trozo)}&select=DOI,updated-by&filter={filtro}"
        items = json.loads(pide(url, CR))["message"].get("items") or []
        for w in items:
            tipos = [str(a.get("type", "")) for a in (w.get("updated-by") or [])]
            salida[str(w.get("DOI", "")).lower()] = tipos
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


def mide(clave, n, semilla, verboso=True):
    pob = POBLACIONES[clave]
    total, pmids, registros = muestra(pob["term"], n, semilla)
    if verboso:
        print(f"\n== {clave}: {pob['term']}  ({total:,} in PubMed)", file=sys.stderr)
        print(f"   sampled {len(pmids)} — {pob['que_es']}", file=sys.stderr)

    # Resolve to the article whose DOI Crossref should be flagging.
    articulos = []      # (pmid_sampled, pmid_article, doi_article, year_article)
    if pob["sigue"] is None:
        for p in pmids:
            r = registros.get(p)
            if r:
                articulos.append((p, p, r["doi"], r["anno"]))
    else:
        pendientes = {}
        for p in pmids:
            r = registros.get(p)
            if not r:
                continue
            destinos = [q for t, q in r["enlaces"] if t == pob["sigue"] and q]
            if destinos:
                pendientes[p] = destinos[0]
        objetivo = sorted(set(pendientes.values()))
        art_regs = {}
        for i in range(0, len(objetivo), 100):
            art_regs.update(trae_registros(objetivo[i:i + 100]))
        for p, q in pendientes.items():
            a = art_regs.get(q, {})
            articulos.append((p, q, a.get("doi", ""), a.get("anno", 0)))

    con_doi = [t for t in articulos if t[2]]
    sin_doi = len(articulos) - len(con_doi)

    cr = updated_by([t[2] for t in con_doi]) if con_doi else {}

    marcados, silenciosos, ausentes, ejemplos = 0, 0, 0, []
    epocas = {}
    for _, pm_art, d, anno in con_doi:
        if d not in cr:
            estado, ausentes = "missing", ausentes + 1
            if len(ejemplos) < 8:
                ejemplos.append((d, pm_art, "not in Crossref at all"))
        elif cr[d]:
            estado, marcados = "flagged", marcados + 1
        else:
            estado, silenciosos = "silent", silenciosos + 1
            if len(ejemplos) < 8:
                ejemplos.append((d, pm_art, "in Crossref, no updated-by"))
        e = epocas.setdefault(epoca(anno), {"n": 0, "flagged": 0})
        e["n"] += 1
        e["flagged"] += (estado == "flagged")

    return {
        "population": clave,
        "term": pob["term"],
        "pubmed_total": total,
        "sampled": len(pmids),
        "resolved_to_article": len(articulos),
        "no_doi": sin_doi,
        "with_doi": len(con_doi),
        "crossref_flags": marcados,
        "crossref_silent": silenciosos,
        "crossref_missing_work": ausentes,
        "by_era": epocas,
        "examples": ejemplos,
    }


def informa(r):
    n = r["with_doi"]
    pct = (lambda x: f"{100.0 * x / n:5.1f}%" if n else "   n/a")
    print(f"\n{r['population'].upper()}  ({r['term']}, {r['pubmed_total']:,} records in PubMed)")
    print(f"  sampled                                {r['sampled']:5d}")
    if r["resolved_to_article"] != r["sampled"]:
        print(f"  resolved to a corrected article        {r['resolved_to_article']:5d}"
              "   (the rest carry no back-link)")
    print(f"  of those, with a DOI                   {r['with_doi']:5d}")
    print(f"    Crossref flags it (updated-by)       {r['crossref_flags']:5d}  {pct(r['crossref_flags'])}")
    print(f"    Crossref holds it but says nothing   {r['crossref_silent']:5d}  {pct(r['crossref_silent'])}")
    print(f"    Crossref has no record of the DOI    {r['crossref_missing_work']:5d}  {pct(r['crossref_missing_work'])}")
    orden = [nombre for _, _, nombre in EPOCAS] + ["unknown"]
    filas = [(k, r["by_era"][k]) for k in orden if k in r["by_era"]]
    if len(filas) > 1:
        print("  flagged by Crossref, by year of the article:")
        for k, v in filas:
            cuota = f"{100.0 * v['flagged'] / v['n']:5.1f}%" if v["n"] else "   n/a"
            print(f"    {k:8s} {v['flagged']:4d}/{v['n']:<4d} {cuota}")
    if r["examples"]:
        print("  examples of the blind spot:")
        for d, p, por in r["examples"]:
            print(f"    {d:42s} pmid {p:9s} {por}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=200, help="sample size per population")
    ap.add_argument("--seed", type=int, default=20260911)
    ap.add_argument("--only", choices=sorted(POBLACIONES), action="append")
    ap.add_argument("--json", metavar="FILE", help="write the raw numbers here")
    a = ap.parse_args()

    claves = a.only or ["retraction", "erratum", "concern"]
    salida = []
    for k in claves:
        try:
            r = mide(k, a.n, a.seed)
        except ConnectionError as e:
            print(f"\n{k}: lookup failed, skipped — {e}", file=sys.stderr)
            continue
        informa(r)
        salida.append(r)

    if salida:
        print("\nWhat this measures: of the articles PubMed says carry a notice,")
        print("the share Crossref's `updated-by` would let a DOI-only checker find.")
    if a.json and salida:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"seed": a.seed, "n": a.n, "results": salida}, f, indent=2)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
