#!/usr/bin/env python3
"""refcheck — has anything you cite been quietly corrected?

Retractions are the famous case, and free tools already cover them: Zotero warns
you, Retraction Watch keeps the list. But a retraction is the rarest kind of
change to the scientific record. Measured against the Crossref API on 2026-09-08:

    retractions (what the familiar tools cover) ....  75,265
    corrections ................................... 213,113
    errata ........................................ 116,091
    expressions of concern .........................   4,233
    new editions ..................................  10,874
    withdrawals, removals, addenda, clarifications .   6,328
    ------------------------------------------------------
    the quiet ones ................................ 350,639   (4.7x the retractions)

Those are the quiet ones. Nobody emails you when the paper you are citing had
its numbers corrected two years after you read it — and unlike a retraction, the
paper is still perfectly valid, which is exactly why nobody looks.

This reads a list of DOIs (or a .bib file) and tells you which of your references
carry a published change notice, what kind, and where to read it.

It asks two registers, because one is not enough. Crossref only holds what a
publisher deposited; PubMed keeps the same information separately, compiled by
NLM indexers. Measured on 2026-09-11 over 400 records per category
(research/measure_pubmed_gap.py reproduces it): of the papers PubMed says carry
a notice, Crossref's data would let a DOI-only checker find

    retractions ............................ 93.7%
    expressions of concern ................. 91.8%
    corrections and errata ................. 78.8%   (60% for 2010-14 papers)

One corrected paper in five used to come back from this tool clean. Anything
only one register knows about is printed with its source next to it. That is
Crossref's recall against PubMed, not against the truth — PubMed has holes of
its own, this does not know their size, and both together only cover what got
deposited somewhere. Two registers beat one; two are still not all of them.

Biomedical bibliographies often cite by PMID and carry no DOI at all, so PMIDs
are translated through PubMed first. That translation has a hole, and the hole
is measured, not guessed: of 1,558 random PubMed records sampled on 2026-09-09,
72.5% listed a DOI — 95.7% of the recent ones, 48.6% of those from before 1990
(research/measure_pmid_doi.py reproduces it). A PMID with no DOI cannot be
checked against Crossref at all, and this says so rather than staying quiet,
because silence reads as "clean".

No terminal? The same check runs in a browser, with nothing to install:
https://kaizenshogun.github.io/refcheck/

Usage:
    refcheck.py refs.bib
    refcheck.py dois.txt
    echo 10.1371/journal.pone.0161231 | refcheck.py -
    refcheck.py refs.bib --json          machine-readable, for pipelines
    refcheck.py refs.txt --no-pubmed     Crossref only; never contact NCBI

Exit codes: 0 nothing found · 1 something found · 2 bad usage, or a reference
that could not be looked up. A failed lookup is not a clean reference, so it
does not let a CI gate go green. A PMID with no DOI, like a DOI Crossref does
not hold, exits 0: that is not a failure to be retried but a permanent "there
is nothing to ask", and a gate that can never go green gets switched off. The
report says so in words either way — the number is for machines, the sentence
is for you.

Standard library only. No account, no key, no tracking. MIT.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = "https://api.crossref.org/works/"
LOTE = 40   # DOIs per request. Measured safe against the API on 2026-09-08 (75 also
            # worked); 40 keeps the URL short and the public service unbothered.
# Crossref asks callers to identify themselves; being polite gets you the fast pool.
CONTACT = os.environ.get("REFCHECK_MAILTO", "")
UA = f"refcheck/1.0 (https://github.com/KaizenShogun/refcheck{'; mailto:' + CONTACT if CONTACT else ''})"


class Ritmo:
    """Obey the rate limit the API states, instead of the one I assumed.

    Measured 2026-09-09 by reading the response headers:

        no mailto  → x-api-pool: public-array · x-rate-limit-limit: 1 per 1s
        mailto set → x-api-pool: polite-array · x-rate-limit-limit: 3 per 1s

    refcheck used to pause 0.4 s between batches, which is 2.5 requests a second
    — two and a half times what the public pool permits, and most people never
    set REFCHECK_MAILTO. That is how you earn a 429 from a service the README
    asks you to be kind to. The default is now the conservative 1/s, raised only
    when the server itself says a higher rate is allowed.
    """

    def __init__(self, limite=1, intervalo=1.0):
        self.limite, self.intervalo, self.ultima = limite, intervalo, 0.0

    def aprende(self, cabeceras):
        # Two services, two spellings. Crossref sends `x-rate-limit-limit` plus an
        # explicit `x-rate-limit-interval`; NCBI sends `x-ratelimit-limit: 3` and
        # no interval, because its published limit is per second. Absent interval
        # therefore means one second — but only when the limit came from the
        # header NCBI uses. Guessing an interval for Crossref would be inventing
        # permission the server never gave.
        crudo_limite = cabeceras.get("x-rate-limit-limit")
        por_segundo = crudo_limite is None
        if por_segundo:
            crudo_limite = cabeceras.get("x-ratelimit-limit")
        try:
            limite = int(crudo_limite or 0)
            crudo = (cabeceras.get("x-rate-limit-interval", "") or "").strip().lower()
            if por_segundo and not crudo:
                intervalo = 1.0
            else:
                intervalo = float(crudo.rstrip("s")) if crudo.endswith("s") else float(crudo)
        except (TypeError, ValueError):
            return                       # header missing or odd: keep the safe default
        if limite > 0 and intervalo > 0:
            self.limite, self.intervalo = limite, intervalo

    @property
    def hueco(self):
        return self.intervalo / self.limite

    def espera(self):
        """Sleep only for whatever is left of the gap after the last request."""
        queda = self.hueco - (time.monotonic() - self.ultima)
        if queda > 0:
            time.sleep(queda)
        self.ultima = time.monotonic()


RITMO = Ritmo()

# How loudly to shout. A retraction means "do not use this". A correction means
# "check that the bit you are citing is still the bit that is written there".
GRAVEDAD = {
    "retraction": 3, "partial_retraction": 3, "removal": 3, "withdrawal": 3,
    "expression_of_concern": 2,
    "correction": 1, "erratum": 1, "corrigendum": 1,
    "addendum": 0, "clarification": 0, "new_edition": 0, "new_version": 0,
}
ETIQUETA = {
    3: "RETRACTED — do not cite this as evidence",
    2: "EXPRESSION OF CONCERN — the journal itself is unsure",
    1: "CORRECTED — check the number you are quoting is still there",
    0: "UPDATED — additional material published",
}
# Said in the loudest place because it is the one answer this tool cannot give you.
CONFLICTO = ("CONTRADICTORY NOTICES — check this one by hand, Crossref disagrees "
             "with itself")
# A different animal from CONFLICTO, and worth keeping apart. There, one source
# said two things at once and there is no way to order them. Here, two
# independent registers catalogue the same notice under different names — which
# is ordinary, both are telling the truth as they file it, and the reader mainly
# needs to know that the milder label is not the only label.
DISCREPANCIA = ("REGISTERS DISAGREE — Crossref and PubMed file the same notice "
                "under different names")

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9<>\[\]]+")

# Only where the text says so. A bibliography is full of bare numbers — years,
# pages, volumes, ISBNs — and guessing that one of them is a PMID would send a
# stranger's page number to NCBI and report the wrong paper back. So: the word
# PMID, a BibTeX `pmid = {…}` field, or a pubmed.ncbi.nlm.nih.gov URL. Nothing else.
PMID_RE = re.compile(
    r"""(?ix)
    (?: \bpmid \b \s* [:=]? \s* \{? \s* "? (?P<a>\d+)
      | pubmed\.ncbi\.nlm\.nih\.gov/ (?P<b>\d+)
      | ncbi\.nlm\.nih\.gov/pubmed/ (?P<c>\d+) )
    """)
# PubMed is around 41 million records, so a real id is eight digits at most. A
# longer one is a typo, and the whole digit run is captured rather than the
# first eight on purpose: taking a prefix would turn `PMID: 315789451` into a
# lookup of a real but completely unrelated paper. Better to say "no such
# record" than to quietly answer about the wrong one.
PMID_MAX = 99_999_999

PUBMED = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
LOTE_PMID = 100   # ids per esummary request; keeps the GET URL under ~1 kB
LOTE_AID = 50     # DOIs per `[aid]` search; sent by POST, so length is not the limit
# NCBI states 3 requests/second for callers without an API key, and says so in
# `x-ratelimit-limit` on every reply. Same discipline as with Crossref: start at
# the conservative rate and only speed up if the server itself allows it.
RITMO_PUBMED = Ritmo(limite=1, intervalo=1.0)


# MEDLINE — the `.nbib` that PubMed's own "Send to → Citation manager" button
# produces, and the file a systematic reviewer or a librarian actually has on
# disk. Read as loose text it is a trap, because a MEDLINE record carries the
# identifiers of OTHER papers: the commentaries written about it (CIN), the
# notice that retracted it (RIN), the article whose erratum it is (EFR). Each
# sits on its own tagged line with a DOI and a `PMID: ` that the forgiving
# regexes above cannot tell from the article's own. And the article's own id is
# written `PMID- 31978945`, with a hyphen, which PMID_RE does not accept.
#
# Measured 2026-09-12 on a 200-record export of a real PubMed search: 15 foreign
# DOIs pulled in, and 200 of the 200 real PMIDs missed — the only 8 ids returned
# belonged to strangers. So MEDLINE is parsed as the record format it is, and
# only the tags that identify THIS article are read.
MEDLINE_ETIQUETA = re.compile(r"^([A-Z][A-Z0-9]{1,5})\s*-\s?(.*)$")
# A whitelist, not a blacklist of the cross-reference tags. PubMed can add a new
# kind of cross-reference next year — it has before — and a blacklist would let
# the new one through silently, which is the failure mode this tool exists to
# catch in other people. These four are the only tags that speak about the
# record they sit in.
MEDLINE_ID = {"PMID", "AID", "LID", "SO"}


# RIS looks superficially the same — `TY  - JOUR`, `DO  - 10.x/y` — and a RIS
# file must keep going through the forgiving path, where its DOIs are found
# perfectly well. So detection asks for a tag that only MEDLINE has, rather than
# trusting that no RIS file will ever contain the letters PMID at a line start.
MEDLINE_PROPIAS = {"AID", "LID", "SO", "OWN", "STAT", "JT", "MH", "PT", "PST", "BTI"}


def es_medline(texto):
    """Does this look like a MEDLINE/`.nbib` export rather than prose?

    Three conditions, all necessary: enough tagged lines that it cannot be a
    bibliography that happens to start a line with capitals, at least one
    `PMID- ` record header, and at least one tag that exists in MEDLINE and
    nowhere else. A BibTeX file has none of the three; a RIS file has none.
    """
    etiquetadas = cabeceras = 0
    propias = False
    for linea in texto.splitlines():
        m = MEDLINE_ETIQUETA.match(linea)
        if m:
            etiquetadas += 1
            if m.group(1) == "PMID":
                cabeceras += 1
            elif m.group(1) in MEDLINE_PROPIAS:
                propias = True
    return cabeceras >= 1 and propias and etiquetadas >= 5


def registros_medline(texto):
    """The articles in a MEDLINE export, in file order, with nothing borrowed.

    Each entry is {'pmid', 'doi', 'titulo', 'fecha'}; doi may be empty, which is
    a fact to report and not a reason to drop the reference. A new record starts
    at every `PMID-` line, which is where MEDLINE starts one.
    """
    registros, actual, etiqueta = [], None, None
    valores = {}

    def cierra():
        if actual is None:
            return
        doi = ""
        for tag in ("AID", "LID"):
            for v in valores.get(tag, []):
                if v.lower().endswith("[doi]"):
                    hallado = DOI_RE.search(v)
                    if hallado:
                        doi = _limpia_doi(hallado.group(0))
                        break
            if doi:
                break
        if not doi:
            # No [doi] tag. The source line carries it for plenty of records —
            # `SO  - N Engl J Med. 2020;382(8):727-733. doi: 10.1056/NEJMoa2001017.`
            # — and SO describes this article, so it is safe to read.
            for v in valores.get("SO", []):
                hallado = DOI_RE.search(v)
                if hallado:
                    doi = _limpia_doi(hallado.group(0))
                    break
        actual["doi"] = doi
        actual["titulo"] = " ".join(valores.get("TI", []))[:300]
        actual["fecha"] = (valores.get("DP", [""])[0] or "")[:4]
        registros.append(actual)

    for linea in texto.splitlines():
        m = MEDLINE_ETIQUETA.match(linea)
        if m:
            etiqueta, valor = m.group(1), m.group(2).strip()
            if etiqueta == "PMID":
                cierra()
                crudo = valor.strip()
                actual = {"pmid": str(int(crudo)) if crudo.isdigit() else "",
                          "doi": "", "titulo": "", "fecha": ""}
                valores = {}
                continue
            if actual is not None and etiqueta in MEDLINE_ID | {"TI", "DP"}:
                valores.setdefault(etiqueta, []).append(valor)
            continue
        if linea.startswith(" ") and actual is not None and etiqueta:
            # Continuation of the previous tag — long titles and source lines
            # wrap. Only folded into tags we read; a wrapped CIN line stays
            # unread, which is the whole point.
            if etiqueta in MEDLINE_ID | {"TI", "DP"} and valores.get(etiqueta):
                valores[etiqueta][-1] += " " + linea.strip()
    cierra()
    return [r for r in registros if r["pmid"] or r["doi"]]


def _limpia_doi(bruto):
    return bruto.rstrip(".,;)}\"'").rstrip("}").lower()


def dois_de(texto):
    """Pull DOIs out of anything: a plain list, a .bib, a pasted bibliography.

    Deliberately forgiving — the person running this has a messy file, not a
    clean dataset, and a tool that demands a clean dataset does not get used.
    """
    vistos, salida = set(), []
    for bruto in DOI_RE.findall(texto):
        # _limpia_doi also drops the closing brace of a BibTeX  doi = {10.x/y},
        d = _limpia_doi(bruto)
        if d not in vistos:
            vistos.add(d)
            salida.append(d)
    return salida


def pmids_de(texto):
    """Pull PubMed ids out of the same mess, in the order they appear.

    Normalised to their integer form so that `PMID: 0031978945` and
    `pubmed.ncbi.nlm.nih.gov/31978945` are one reference, not two.
    """
    vistos, salida = set(), []
    for m in PMID_RE.finditer(texto):
        crudo = m.group("a") or m.group("b") or m.group("c")
        p = str(int(crudo))          # drop leading zeros
        if p != "0" and p not in vistos:
            vistos.add(p)
            salida.append(p)
    return salida


def consulta_pmids(pmids, reintentos=3):
    """One esummary request for up to LOTE_PMID ids. Returns {pmid: record}.

    An id PubMed does not hold comes back inside `result` carrying an `error`
    key, which is a different thing from the request failing, and the two must
    not be merged: one means "no such paper", the other means "we do not know".
    """
    url = PUBMED + "?" + urllib.parse.urlencode(
        {"db": "pubmed", "retmode": "json", "id": ",".join(pmids)})
    ultimo = None
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            RITMO_PUBMED.espera()
            with urllib.request.urlopen(req, timeout=60) as r:
                RITMO_PUBMED.aprende(r.headers)
                datos = json.load(r).get("result") or {}
            salida = {}
            for uid in datos.get("uids") or []:
                rec = datos.get(str(uid)) or {}
                if not rec.get("error"):
                    salida[str(uid)] = rec
            return salida
        except Exception as e:
            ultimo = e
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
    raise ConnectionError(f"PubMed lookup failed: {ultimo}")


# PubMed keeps the same information as Crossref's `updated-by`, in
# CommentsCorrectionsList, and keeps it independently: NLM indexers build it,
# not the publisher's deposit pipeline. Measured on 2026-09-11, the two
# disagree often enough to matter — see research/measure_pubmed_gap.py.
#
# Only the RefTypes that are a verdict on the record are taken. `CommentIn` is
# a letter to the editor, `UpdateIn` is versioning, `SummaryForPatientsIn` is a
# plain-language summary: none of them says the paper changed, and printing
# them would be exactly the noise a reference manager is right to leave out.
REFTYPE = {
    "RetractionIn": "retraction",
    "PartialRetractionIn": "partial_retraction",
    "ExpressionOfConcernIn": "expression_of_concern",
    "ErratumIn": "erratum",
    "CorrectedandRepublishedIn": "correction",
}
# "J Natl Cancer Inst. 2024 Dec 1;116(12):2044. doi: 10.1093/jnci/djae263."
RS_DOI = re.compile(r"\bdoi:\s*(10\.\d{4,9}/\S+?)\.?\s*$", re.I)
RS_ANNO = re.compile(r"\b(1[89]|20)\d{2}\b")


def _pide_ncbi(url, campos, reintentos=3):
    """POST to E-utilities. POST because a batch of DOIs outgrows a GET URL."""
    datos = urllib.parse.urlencode(campos).encode()
    ultimo = None
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, data=datos, headers={"User-Agent": UA})
            RITMO_PUBMED.espera()
            with urllib.request.urlopen(req, timeout=60) as r:
                RITMO_PUBMED.aprende(r.headers)
                return r.read()
        except Exception as e:
            ultimo = e
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
    raise ConnectionError(f"PubMed lookup failed: {ultimo}")


def _avisos_de_xml(xml):
    """{doi: {"pmid", "titulo", "avisos"}} from a PubMed efetch reply."""
    salida = {}
    for art in ET.fromstring(xml).iter("PubmedArticle"):
        cita = art.find("MedlineCitation")
        if cita is None or cita.find("PMID") is None:
            continue
        # Every lookup is scoped to the element that owns it. A bare iter() over
        # the article would return a DOI out of <ReferenceList> — somebody
        # else's paper — for any record that has no DOI of its own.
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
        avisos = []
        for cc in cita.findall("./CommentsCorrectionsList/CommentsCorrections"):
            tipo = REFTYPE.get(cc.get("RefType", ""))
            if not tipo:
                continue
            ref = cc.find("RefSource")
            ref = (ref.text or "").strip() if ref is not None else ""
            pm = cc.find("PMID")
            m = RS_DOI.search(ref)
            anno = RS_ANNO.search(ref)
            avisos.append({
                "tipo": tipo,
                "gravedad": GRAVEDAD.get(tipo, 1),
                "fecha": anno.group(0) if anno else "",
                "doi_aviso": m.group(1).rstrip(".").lower() if m else "",
                # Not every notice in PubMed has a DOI. Without this the report
                # would print a bare "https://doi.org/" and send the reader nowhere.
                "pmid_aviso": (pm.text or "").strip() if pm is not None else "",
                "etiqueta": tipo.replace("_", " ").title(),
                "fuente": "pubmed",
                "registro": None,
                "contradice": [],
            })
        titulo = cita.find("./Article/ArticleTitle")
        salida[doi] = {
            "pmid": (cita.find("PMID").text or "").strip(),
            "titulo": "".join(titulo.itertext()).strip() if titulo is not None else "",
            "avisos": avisos,
        }
    return salida


def avisos_pubmed(dois):
    """Ask PubMed what IT knows about these DOIs. Raises if the lookup fails.

    Two requests per batch and no way around it: `[aid]` search answers with a
    list of PMIDs and never says which DOI matched which, so the records have
    to be fetched to be matched back by their own DOI.
    """
    salida = {}
    for i in range(0, len(dois), LOTE_AID):
        trozo = dois[i:i + LOTE_AID]
        term = " OR ".join(f'"{d}"[aid]' for d in trozo)
        r = json.loads(_pide_ncbi(ESEARCH, {"db": "pubmed", "retmode": "json",
                                            "retmax": str(len(trozo) * 3),
                                            "term": term}))
        ids = (r.get("esearchresult") or {}).get("idlist") or []
        if not ids:
            continue
        xml = _pide_ncbi(EFETCH, {"db": "pubmed", "retmode": "xml", "id": ",".join(ids)})
        for doi, rec in _avisos_de_xml(xml).items():
            if doi in {d.lower() for d in trozo}:
                salida[doi] = rec
    return salida


def _doi_de_registro(rec):
    for a in rec.get("articleids") or []:
        if a.get("idtype") == "doi" and a.get("value"):
            return str(a["value"]).strip().rstrip(".").lower()
    return None


def resuelve_pmids(pmids):
    """PMID → DOI, in batches. Returns {pmid: {...}} with an honest state.

    Three ways this ends without a DOI, and they are three different sentences
    to print, never one:
      · `sin_doi`      — the record exists and lists no DOI. Measured at 27.5%
                         of PubMed overall, over half of it from before 1990.
                         Crossref is indexed by DOI, so there is nothing to ask.
      · `desconocido`  — PubMed has no such id. Probably a typo in the citation.
      · `sin_comprobar`— the lookup itself failed. Unknown, and must not be
                         allowed to pass for clean.
    """
    salida = {}
    # A number too long to be a PubMed id is answered here, without spending a
    # request on a service that cannot possibly hold it.
    posibles = []
    for p in pmids:
        if int(p) > PMID_MAX:
            salida[p] = {"estado": "desconocido"}
        else:
            posibles.append(p)
    pmids = posibles
    for i in range(0, len(pmids), LOTE_PMID):
        trozo = pmids[i:i + LOTE_PMID]
        try:
            registros = consulta_pmids(trozo)
        except ConnectionError as e:
            for p in trozo:
                salida[p] = {"estado": "sin_comprobar", "error": str(e)}
            continue
        for p in trozo:
            rec = registros.get(p)
            if rec is None:
                salida[p] = {"estado": "desconocido"}
                continue
            doi = _doi_de_registro(rec)
            titulo = (rec.get("title") or "").strip()
            if doi:
                salida[p] = {"estado": "ok", "doi": doi, "titulo": titulo}
            else:
                salida[p] = {"estado": "sin_doi", "titulo": titulo,
                             "fecha": (rec.get("pubdate") or "").strip()}
    return salida


def consulta(doi, reintentos=3):
    url = API + urllib.parse.quote(doi)
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)["message"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None          # DOI not in Crossref: not an error, just unknown
            if e.code in (429, 500, 502, 503) and intento < reintentos - 1:
                time.sleep(2 ** intento)
                continue
            return None
        except Exception:
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
                continue
            return None
    return None


def marca_contradicciones(avisos):
    """Flag assertions that come from one upstream record but disagree on type.

    Crossref does not overwrite a Retraction Watch assertion when the upstream
    record changes its nature: it appends a second one carrying the same
    `record-id`, the same source and the same timestamp, with a different type.
    So 10.1148/85.3.474 is served as both `retraction` and
    `expression_of_concern` — and the retraction is the stale half, downgraded
    upstream on 2026-03-26. Reported by a user in 2026-05, acknowledged by
    Crossref (CR-2746), still live. https://community.crossref.org/t/15831

    Nothing in the response says which half is current, so this tool must not
    pick one. Taking the worst — what it did until this was measured — is the
    expensive mistake: it tells a reader to bin a citation that was never
    retracted. Both halves get flagged and the reader is sent upstream.
    """
    grupos = {}
    for a in avisos:
        if a.get("registro") is None:
            continue        # no record-id: no evidence these share an origin
        grupos.setdefault((a["fuente"], a["registro"]), []).append(a)
    for miembros in grupos.values():
        tipos = sorted({m["tipo"] for m in miembros})
        if len(tipos) > 1:
            for m in miembros:
                m["contradice"] = [t for t in tipos if t != m["tipo"]]
    return avisos


def fecha_mas_temprana(*fechas):
    """The earliest of several Crossref dates, preferring the precise one.

    Dates arrive as "2019", "2019-03" or "2019-03-19" depending on what the
    depositor filled in. A plain string min() would pick "2019" over
    "2019-03-19" and throw away the day for nothing, so the year decides first
    and precision breaks the tie.
    """
    vivas = [f for f in fechas if f]
    if not vivas:
        return ""
    anno = min(int(f.split("-")[0]) if f.split("-")[0].isdigit() else 9999
               for f in vivas)
    candidatas = [f for f in vivas
                  if (f.split("-")[0].isdigit() and int(f.split("-")[0]) == anno)
                  or anno == 9999]
    return sorted(candidatas, key=lambda f: (-len(f), f))[0]


def avisos_de(obra):
    """Change notices attached to one work record, worst first."""
    avisos = []
    for u in (obra.get("updated-by") or []):
        tipo = (u.get("type") or "unknown").lower()
        partes = (u.get("updated") or {}).get("date-parts", [[None]])[0]
        fecha = "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(partes) if p) if partes and partes[0] else ""
        avisos.append({
            "tipo": tipo,
            "gravedad": GRAVEDAD.get(tipo, 1),
            "fecha": fecha,
            "doi_aviso": u.get("DOI", ""),
            "etiqueta": u.get("label") or tipo.replace("_", " ").title(),
            "fuente": u.get("source", ""),
            "registro": str(u["record-id"]) if u.get("record-id") is not None else None,
            "contradice": [],
        })
    # The same notice often arrives twice, once from the publisher and once from
    # Retraction Watch: 10.1038/nature12968 carries its retraction listed two
    # identical times. Printing it twice makes the reader look for a difference
    # that is not there. Same type, same notice DOI, same date = the same event,
    # whoever reported it, so the source is deliberately left out of the key.
    #
    # But which copy survives is not arbitrary. The Retraction Watch one carries
    # a `record-id`, and that id is the only evidence that two assertions come
    # from one upstream record — which is what the contradiction check runs on.
    # Keeping the publisher's anonymous copy instead would silently disarm it.
    #
    # The date is deliberately NOT part of the key. One notice deposited twice
    # with two dates is still one notice: `10.1016/j.engfailanal.2019.01.024` is
    # a withdrawn paper that carries its own retraction on 2019-03-19 and again
    # on 2019-04-01, and printing both makes a single withdrawal read as two.
    # Found on 2026-09-12 while measuring, not by a user, which is the cheap way
    # round. When the copies disagree on the date, the earliest is shown: a
    # re-deposit is not a second event, and the first date is the one closest to
    # when the notice actually appeared.
    unicos, indice = [], {}
    for a in avisos:
        # A notice with no DOI of its own cannot be told apart from another of
        # the same type except by its date, so there the date stays in the key.
        clave = (a["tipo"], a["doi_aviso"]) if a["doi_aviso"] else \
                (a["tipo"], "", a["fecha"])
        if clave not in indice:
            indice[clave] = len(unicos)
            unicos.append(a)
            continue
        previo = unicos[indice[clave]]
        pronto = fecha_mas_temprana(previo["fecha"], a["fecha"])
        if a["registro"] is not None and previo["registro"] is None:
            unicos[indice[clave]] = a
        unicos[indice[clave]]["fecha"] = pronto
    avisos = unicos
    marca_contradicciones(avisos)
    avisos.sort(key=lambda a: (-a["gravedad"], a["fecha"]))
    return avisos


def ficha(doi, obra):
    avisos = avisos_de(obra)
    return {"doi": doi, "estado": "ok", "titulo": (obra.get("title") or [""])[0],
            "revista": (obra.get("container-title") or [""])[0],
            "contradictorio": any(a["contradice"] for a in avisos),
            "avisos": avisos}


def revisa(doi):
    """Return the change notices attached to one DOI, worst first."""
    obra = consulta(doi)
    if obra is None:
        return {"doi": doi, "estado": "desconocido", "avisos": []}
    return ficha(doi, obra)


def consulta_lote(dois, reintentos=3):
    """One request for up to LOTE DOIs. Returns {doi: work}, or raises.

    Crossref answers a `filter=doi:a,doi:b,…` query with only the DOIs it holds,
    so a DOI missing from the reply means "no record", not "lookup failed" —
    and those two must never be shown to the reader as the same thing.
    """
    filtro = ",".join("doi:" + urllib.parse.quote(d, safe="") for d in dois)
    url = f"{API.rstrip('/')}?rows={len(dois)}&select=DOI,title,container-title,updated-by&filter={filtro}"
    ultimo = None
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            RITMO.espera()
            with urllib.request.urlopen(req, timeout=60) as r:
                RITMO.aprende(r.headers)
                items = json.load(r)["message"].get("items") or []
            return {str(w.get("DOI", "")).lower(): w for w in items}
        except Exception as e:
            ultimo = e
            if intento < reintentos - 1:
                time.sleep(2 ** intento)
    raise ConnectionError(f"Crossref lookup failed: {ultimo}")


def revisa_lote(dois, pausa=None, avisa=None):
    """Check every DOI, in batches. Never reports a failed lookup as 'not found'.

    Pacing is handled by RITMO, which follows the rate the server declares.
    `pausa` is an extra courtesy delay on top, for anyone who wants to go slower
    still; it is not the thing keeping us inside the limit.
    """
    resultados, hechos = [], 0
    for i in range(0, len(dois), LOTE):
        trozo = dois[i:i + LOTE]
        try:
            obras = consulta_lote(trozo)
        except ConnectionError as e:
            # This batch is lost, the rest of the bibliography is not.
            for d in trozo:
                resultados.append({"doi": d, "estado": "sin_comprobar",
                                   "error": str(e), "avisos": []})
            obras = None
        if obras is not None:
            for d in trozo:
                w = obras.get(d.lower())
                resultados.append(ficha(d, w) if w
                                  else {"doi": d, "estado": "desconocido", "avisos": []})
        hechos += len(trozo)
        if avisa:
            avisa(hechos, len(dois))
        if pausa and i + LOTE < len(dois):
            time.sleep(pausa)
    return resultados


def fusiona_pubmed(resultados, avisa=None):
    """Add what PubMed knows and Crossref does not. Mutates `resultados`.

    A notice already reported by Crossref is not repeated. The key is
    (severity, notice DOI), and both halves of that are deliberate:

      · Not the DOI alone. The two registers sometimes catalogue one notice at
        different severities — on the 1998 Lancet paper, notice
        10.1016/s0140-6736(04)15715-2 is a `correction` to Crossref and a
        `RetractionIn` to PubMed. Keying on the DOI would keep whichever
        arrived first and drop the other, and half the time the one dropped is
        the graver. Under-warning quietly is the failure this tool exists to
        avoid, so both are kept, both are labelled, and the reference is
        headlined as a disagreement instead of as either verdict.

      · Not the type either. `correction` and `erratum` are one word in two
        vocabularies, not two events; printing both lines for the same notice
        DOI would be pure noise, and a "the registers disagree!" banner over a
        spelling difference trains the reader to ignore the banner.

    When a notice carries no DOI there is nothing to match on but the type, so a
    same-type notice is treated as the same one. That can hide a second,
    genuinely different erratum — the safe direction to be wrong in, since the
    reader is already being sent to look at the paper.

    A DOI Crossref has no record of is NOT skipped. Those are the ones where a
    second source pays for itself.
    """
    dois = [r["doi"] for r in resultados if r.get("doi")]
    if not dois:
        return resultados
    try:
        conocido = avisos_pubmed(dois)
    except ConnectionError as e:
        # PubMed being down must not cost us the Crossref answer we already have.
        for r in resultados:
            if r.get("doi"):
                r["pubmed_error"] = str(e)
        return resultados
    if avisa:
        avisa(len(dois), len(dois))

    for r in resultados:
        rec = conocido.get((r.get("doi") or "").lower())
        r["en_pubmed"] = rec is not None
        if rec is None:
            continue
        r.setdefault("pmid", rec["pmid"])
        if not r.get("titulo"):
            r["titulo"] = rec["titulo"]
        ya = {(a["gravedad"], a["doi_aviso"].lower()) for a in r["avisos"]}
        ya_grav = {a["gravedad"] for a in r["avisos"]}
        nuevos = [a for a in rec["avisos"]
                  if ((a["gravedad"], a["doi_aviso"].lower()) not in ya if a["doi_aviso"]
                      else a["gravedad"] not in ya_grav)]
        if nuevos:
            r["avisos"] = sorted(r["avisos"] + nuevos,
                                 key=lambda a: (-a["gravedad"], a["fecha"]))
            r["discrepancia"] = sorted(
                {a["doi_aviso"] for a in nuevos if a["doi_aviso"]}
                & {a["doi_aviso"].lower() for a in r["avisos"]
                   if a.get("fuente") != "pubmed" and a.get("doi_aviso")})
            # Crossref had no record at all, but PubMed does and it has something
            # to say. The reference HAS been checked — saying "not found" now
            # would file a real warning under "nothing to report".
            if r["estado"] in ("desconocido", "sin_comprobar"):
                r["estado"] = "ok"
                r["solo_pubmed"] = True
    return resultados


def referencias_de(texto, usar_pubmed=True):
    """Everything the text points at: DOIs, plus PMIDs turned into DOIs.

    Returns (dois, origen, sueltos):
      · dois    — what to ask Crossref, in reading order, no duplicates
      · origen  — {doi: pmid} for the ones that arrived as a PubMed id, so the
                  report can name the reference the way the reader wrote it
      · sueltos — PMIDs that produced no DOI, already shaped as results

    A paper cited with both its DOI and its PMID resolves to one entry, not two:
    the point is to check references, not identifiers.
    """
    if es_medline(texto):
        return _referencias_medline(texto)

    dois = dois_de(texto)
    origen, sueltos = {}, []
    pmids = pmids_de(texto) if usar_pubmed else []
    if not pmids:
        return dois, origen, sueltos

    vistos = {d.lower() for d in dois}
    for pmid, r in resuelve_pmids(pmids).items():
        if r["estado"] == "ok":
            doi = r["doi"]
            origen.setdefault(doi, pmid)
            if doi not in vistos:
                vistos.add(doi)
                dois.append(doi)
        elif r["estado"] == "sin_doi":
            sueltos.append({"doi": "", "pmid": pmid, "estado": "pmid_sin_doi",
                            "titulo": r.get("titulo", ""), "fecha": r.get("fecha", ""),
                            "avisos": []})
        elif r["estado"] == "desconocido":
            sueltos.append({"doi": "", "pmid": pmid, "estado": "pmid_desconocido",
                            "avisos": []})
        else:
            sueltos.append({"doi": "", "pmid": pmid, "estado": "sin_comprobar",
                            "error": r.get("error", ""), "avisos": []})
    return dois, origen, sueltos


def _referencias_medline(texto):
    """Same three lists as referencias_de, from a MEDLINE export, with no lookup.

    The file already states each article's own DOI and PMID, so the round trip
    to NCBI that a loose bibliography needs is not needed here — and neither is
    the guessing. A record with no DOI keeps its title and year from the file
    itself, so it can be named in the report instead of being dropped.
    """
    dois, origen, sueltos, vistos = [], {}, [], set()
    for r in registros_medline(texto):
        doi, pmid = r["doi"], r["pmid"]
        if doi:
            if pmid:
                origen.setdefault(doi, pmid)
            if doi not in vistos:
                vistos.add(doi)
                dois.append(doi)
        elif pmid:
            sueltos.append({"doi": "", "pmid": pmid, "estado": "pmid_sin_doi",
                            "titulo": r["titulo"], "fecha": r["fecha"],
                            "avisos": []})
    return dois, origen, sueltos


def nombre(r):
    """How to name a reference back to the person who wrote it."""
    if r.get("doi"):
        return f"{r['doi']} (PMID {r['pmid']})" if r.get("pmid") else r["doi"]
    return f"PMID {r['pmid']}" if r.get("pmid") else "?"


def informe(resultados, ancho=78):
    con = [r for r in resultados if r["avisos"]]
    desc = [r for r in resultados if r["estado"] == "desconocido"]
    sinc = [r for r in resultados if r["estado"] == "sin_comprobar"]
    sin_doi = [r for r in resultados if r["estado"] == "pmid_sin_doi"]
    pmid_desc = [r for r in resultados if r["estado"] == "pmid_desconocido"]
    lineas = []
    chocan = [r for r in con if r.get("contradictorio")]
    for r in sorted(con, key=lambda r: -r["avisos"][0]["gravedad"]):
        peor = r["avisos"][0]
        lineas.append("")
        # A disagreement only takes the headline when settling it would change
        # the verdict. On the 1998 Lancet paper the registers differ over a 2004
        # notice, but both list the 2010 retraction, so the paper is retracted
        # either way and "registers disagree" would bury the undisputed fact.
        disputado = set(r.get("discrepancia") or [])
        firme = [a for a in r["avisos"]
                 if not (a.get("fuente") == "pubmed" and a.get("doi_aviso") in disputado)]
        discute_lo_peor = bool(disputado) and (
            max((a["gravedad"] for a in firme), default=-1) < peor["gravedad"])
        if r.get("contradictorio"):
            titular = CONFLICTO
        elif discute_lo_peor:
            titular = DISCREPANCIA
        else:
            titular = ETIQUETA[peor["gravedad"]]
        lineas.append(f"  {titular}")
        t = r.get("titulo", "")
        lineas.append(f"    {t[:ancho - 4]}" if t else "")
        lineas.append(f"    {nombre(r)}")
        for a in r["avisos"]:
            fecha = f" ({a['fecha']})" if a["fecha"] else ""
            # .get: a report loaded from an older --json run has no such key.
            choca = a.get("contradice") or []
            choque = f"  [contradicts: {', '.join(choca)}]" if choca else ""
            if a.get("doi_aviso"):
                enlace = f"https://doi.org/{a['doi_aviso']}"
            elif a.get("pmid_aviso"):
                enlace = f"https://pubmed.ncbi.nlm.nih.gov/{a['pmid_aviso']}/"
            else:
                enlace = "(no link published)"
            # Say where it came from when Crossref did not have it, so the reader
            # knows which register to argue with — and so a silent Crossref is
            # visible as a silent Crossref rather than as agreement.
            via = "  [per PubMed]" if a.get("fuente") == "pubmed" else ""
            lineas.append(f"      → {a['etiqueta']}{fecha}: {enlace}{choque}{via}")
        if r.get("contradictorio"):
            lineas.append("      Same upstream record, two different verdicts, same date — the API")
            lineas.append("      does not say which is current. Look it up: retractiondatabase.org")
        elif r.get("discrepancia"):
            for d in r["discrepancia"]:
                lineas.append(f"      Two of the lines above are the same notice ({d}),")
                lineas.append("      filed at different severities. Read it and judge for yourself.")
    comprobadas = len(resultados) - len(sinc) - len(sin_doi) - len(pmid_desc)
    cab = [f"  {comprobadas} reference(s) checked · {len(con)} carry a change notice"]
    if chocan:
        cab.append(f"  {len(chocan)} of them carry CONTRADICTORY notices — decide those by hand")
    if sinc:
        cab.append(f"  {len(sinc)} could NOT be checked — the lookup failed. Not clean: unknown.")
    if desc:
        cab.append(f"  {len(desc)} not found in Crossref (preprints, books, bad DOI) — not checked")
    if sin_doi:
        cab.append(f"  {len(sin_doi)} PMID(s) have no DOI in PubMed — nothing to ask Crossref "
                   "about, so NOT checked")
    if pmid_desc:
        cab.append(f"  {len(pmid_desc)} PMID(s) do not exist in PubMed — check the citation")
    if not con and comprobadas > 0:
        cab.append("  Nothing found. That is the expected result most of the time;")
        cab.append("  it is the 1-in-N that this exists for.")
    if sinc or sin_doi or pmid_desc:
        lineas.append("")           # do not let these hang off the last notice
    for r in sinc:
        lineas.append(f"      ? not checked: {nombre(r)}")
    for r in sin_doi:
        t = (r.get("titulo") or "")[:ancho - 24]
        fecha = f" · {r['fecha']}" if r.get("fecha") else ""
        lineas.append(f"      ? no DOI, not checked: PMID {r['pmid']}{fecha}{'  ' + t if t else ''}")
    for r in pmid_desc:
        lineas.append(f"      ? no such record: PMID {r['pmid']}")
    return "\n".join(cab + lineas)


def main():
    p = argparse.ArgumentParser(
        description="Check whether the papers you cite carry a published correction, "
                    "erratum, expression of concern or retraction.")
    p.add_argument("fichero", help="file with DOIs or a .bib file; use - for stdin")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--pausa", type=float, default=None,
                   help="extra seconds between API calls, on top of the rate the "
                        "server declares (public pool 1/s, polite pool 3/s)")
    p.add_argument("--no-pubmed", action="store_true",
                   help="never contact NCBI: no PMID translation and no second "
                        "opinion. Faster and quieter, but measured on 2026-09-11 "
                        "it misses about one corrected paper in five")
    a = p.parse_args()

    texto = sys.stdin.read() if a.fichero == "-" else open(a.fichero, encoding="utf-8", errors="replace").read()
    dois, origen, sueltos = referencias_de(texto, usar_pubmed=not a.no_pubmed)
    if not dois and not sueltos:
        pistas = "No DOIs found in that file."
        if a.no_pubmed and pmids_de(texto):
            pistas += " There are PMIDs, but --no-pubmed was given."
        print(pistas, file=sys.stderr)
        return 2

    # Only draw progress on a real terminal; piped into a log it is just \r noise.
    ruidoso = not a.json and len(dois) > LOTE and sys.stderr.isatty()

    def avisa(hechos, total):
        if ruidoso:
            print(f"\r  checking {hechos}/{total}…", end="", file=sys.stderr, flush=True)

    resultados = revisa_lote(dois, pausa=a.pausa, avisa=avisa)
    if not a.no_pubmed:
        if ruidoso:
            print("\r  asking PubMed too…            ", end="", file=sys.stderr, flush=True)
        fusiona_pubmed(resultados)
    for r in resultados:
        if r["doi"] in origen:
            r["pmid"] = origen[r["doi"]]      # cited as a PMID: say so back
    resultados.extend(sueltos)
    if ruidoso:
        print("\r" + " " * 30 + "\r", end="", file=sys.stderr)

    if a.json:
        json.dump(resultados, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(informe(resultados))

    if any(r["avisos"] for r in resultados):
        return 1
    # A reference we could not look up must not let a CI gate go green.
    if any(r["estado"] == "sin_comprobar" for r in resultados):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
