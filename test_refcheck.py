#!/usr/bin/env python3
"""Battery for refcheck. Offline by default — the network cases are marked and
skipped unless REFCHECK_RED=1, so the tests still mean something on a train.

What is actually being defended here: the DOI extractor (it eats messy files
written by tired people) and the severity ordering (a retraction must never be
reported below a correction).
"""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refcheck


def _tmpdir(caso):
    """A directory that cleans itself up when the test ends."""
    d = tempfile.TemporaryDirectory()
    caso.addCleanup(d.cleanup)
    return d.name


class Extraccion(unittest.TestCase):
    def test_bib_con_llaves(self):
        self.assertEqual(refcheck.dois_de("doi = {10.1371/journal.pone.0161231},"),
                         ["10.1371/journal.pone.0161231"])

    def test_url_completa(self):
        self.assertEqual(refcheck.dois_de("see https://doi.org/10.1038/nature12373 for details"),
                         ["10.1038/nature12373"])

    def test_puntuacion_final_no_se_traga(self):
        # Una bibliografía pegada termina las líneas con punto; el punto NO es del DOI.
        self.assertEqual(refcheck.dois_de("Smith et al., 10.1016/j.cell.2019.01.001."),
                         ["10.1016/j.cell.2019.01.001"])

    def test_duplicados_una_sola_vez(self):
        t = "10.1038/nature12373 y otra vez 10.1038/NATURE12373"
        self.assertEqual(refcheck.dois_de(t), ["10.1038/nature12373"])

    def test_mayusculas_a_minusculas(self):
        self.assertEqual(refcheck.dois_de("10.1038/NaTuRe12373"), ["10.1038/nature12373"])

    def test_varios_en_una_linea(self):
        self.assertEqual(len(refcheck.dois_de("10.1234/a 10.22222/b 10.333333/c")), 3)

    def test_prefijo_invalido_se_rechaza(self):
        # Un prefijo DOI real lleva de 4 a 9 dígitos tras "10.". "10.1/x" no es un DOI,
        # y colarlo sería mandar consultas basura a un servicio público ajeno.
        self.assertEqual(refcheck.dois_de("10.1/x 10.22/y"), [])

    def test_texto_sin_dois(self):
        self.assertEqual(refcheck.dois_de("no hay ningún identificador aquí"), [])


class Gravedad(unittest.TestCase):
    def test_retractacion_manda_sobre_correccion(self):
        obra = {"title": ["x"], "container-title": ["y"], "updated-by": [
            {"type": "correction", "DOI": "10.1/c", "updated": {"date-parts": [[2020, 1, 1]]}},
            {"type": "retraction", "DOI": "10.1/r", "updated": {"date-parts": [[2019, 1, 1]]}}]}
        with mock.patch.object(refcheck, "consulta", return_value=obra):
            r = refcheck.revisa("10.1/x")
        self.assertEqual(r["avisos"][0]["tipo"], "retraction",
                         "una retractación NUNCA debe quedar por debajo de una corrección")

    def test_expresion_de_preocupacion_entre_medias(self):
        self.assertLess(refcheck.GRAVEDAD["correction"], refcheck.GRAVEDAD["expression_of_concern"])
        self.assertLess(refcheck.GRAVEDAD["expression_of_concern"], refcheck.GRAVEDAD["retraction"])

    def test_tipo_desconocido_no_se_silencia(self):
        # Si Crossref inventa un tipo nuevo, debe avisar igual, no descartarlo.
        obra = {"title": ["x"], "container-title": [""], "updated-by": [
            {"type": "brand_new_thing", "DOI": "10.1/n", "updated": {"date-parts": [[2026, 1, 1]]}}]}
        with mock.patch.object(refcheck, "consulta", return_value=obra):
            r = refcheck.revisa("10.1/x")
        self.assertEqual(len(r["avisos"]), 1)
        self.assertEqual(r["avisos"][0]["gravedad"], 1)


class Robustez(unittest.TestCase):
    def test_doi_desconocido_no_revienta(self):
        with mock.patch.object(refcheck, "consulta", return_value=None):
            r = refcheck.revisa("10.9999/nada")
        self.assertEqual(r["estado"], "desconocido")
        self.assertEqual(r["avisos"], [])

    def test_sin_avisos_no_es_hallazgo(self):
        with mock.patch.object(refcheck, "consulta",
                               return_value={"title": ["limpio"], "container-title": [""], "updated-by": []}):
            r = refcheck.revisa("10.1/limpio")
        self.assertEqual(r["avisos"], [])

    def test_fecha_ausente_no_rompe_el_informe(self):
        obra = {"title": ["x"], "container-title": [""], "updated-by": [
            {"type": "correction", "DOI": "10.1/c", "updated": {}}]}
        with mock.patch.object(refcheck, "consulta", return_value=obra):
            r = refcheck.revisa("10.1/x")
        self.assertEqual(r["avisos"][0]["fecha"], "")
        refcheck.informe([r])  # no debe lanzar

    def test_informe_cuenta_bien(self):
        res = [{"doi": "a", "estado": "ok", "titulo": "t", "avisos": [
                    {"tipo": "retraction", "gravedad": 3, "fecha": "2020", "doi_aviso": "10.1/r", "etiqueta": "Retraction"}]},
               {"doi": "b", "estado": "ok", "titulo": "t", "avisos": []},
               {"doi": "c", "estado": "desconocido", "avisos": []}]
        txt = refcheck.informe(res)
        self.assertIn("3 reference(s) checked · 1 carry a change notice", txt)
        self.assertIn("1 not found in Crossref", txt)


class Lotes(unittest.TestCase):
    """El camino por lotes: una petición por cada 40 DOIs en vez de una por DOI."""

    def test_parte_en_lotes_del_tamano_declarado(self):
        vistos = []

        def falso(trozo, **kw):
            vistos.append(list(trozo))
            return {}

        with mock.patch.object(refcheck, "consulta_lote", side_effect=falso):
            refcheck.revisa_lote([f"10.1234/x{i}" for i in range(95)], pausa=0)
        self.assertEqual([len(v) for v in vistos], [40, 40, 15])

    def test_ausente_de_la_respuesta_es_desconocido(self):
        with mock.patch.object(refcheck, "consulta_lote", return_value={}):
            r = refcheck.revisa_lote(["10.9999/nada"], pausa=0)
        self.assertEqual(r[0]["estado"], "desconocido")

    def test_fallo_de_red_NO_se_disfraza_de_desconocido(self):
        # El fallo que importa: si la consulta se cae, decir "no encontrado" le
        # cuenta al lector que su referencia está limpia. No lo está: es un ?.
        with mock.patch.object(refcheck, "consulta_lote",
                               side_effect=ConnectionError("boom")):
            r = refcheck.revisa_lote(["10.1234/x"], pausa=0)
        self.assertEqual(r[0]["estado"], "sin_comprobar")
        self.assertNotEqual(r[0]["estado"], "desconocido")

    def test_un_lote_muerto_no_se_lleva_a_los_demas(self):
        def falso(trozo, **kw):
            if trozo[0].endswith("0"):
                raise ConnectionError("boom")
            return {trozo[0].lower(): {"title": ["t"], "container-title": [""],
                                       "updated-by": [{"type": "retraction", "DOI": "10.1/r",
                                                       "updated": {"date-parts": [[2020, 1, 1]]}}]}}

        dois = [f"10.1234/a{i}" for i in range(40)] + ["10.1234/b1"]
        with mock.patch.object(refcheck, "consulta_lote", side_effect=falso):
            r = refcheck.revisa_lote(dois, pausa=0)
        self.assertEqual(sum(1 for x in r if x["estado"] == "sin_comprobar"), 40)
        self.assertEqual(sum(1 for x in r if x["avisos"]), 1)

    def test_la_respuesta_casa_aunque_cambie_la_caja(self):
        # Crossref devuelve el DOI con su propia capitalización.
        with mock.patch.object(refcheck, "consulta_lote",
                               return_value={"10.1234/x": {"title": ["t"],
                                                           "container-title": [""],
                                                           "updated-by": []}}):
            r = refcheck.revisa_lote(["10.1234/X"], pausa=0)
        self.assertEqual(r[0]["estado"], "ok")

    def test_informe_no_cuenta_lo_no_comprobado_como_comprobado(self):
        res = [{"doi": "a", "estado": "ok", "titulo": "t", "avisos": []},
               {"doi": "b", "estado": "sin_comprobar", "error": "boom", "avisos": []}]
        txt = refcheck.informe(res)
        self.assertIn("1 reference(s) checked", txt)
        self.assertIn("could NOT be checked", txt)

    def test_informe_no_dice_limpio_si_no_comprobo_nada(self):
        res = [{"doi": "b", "estado": "sin_comprobar", "error": "boom", "avisos": []}]
        self.assertNotIn("Nothing found", refcheck.informe(res))


@unittest.skipUnless(os.environ.get("REFCHECK_RED") == "1", "necesita red: REFCHECK_RED=1")
class ContraLaRealidad(unittest.TestCase):
    def test_correccion_conocida(self):
        r = refcheck.revisa("10.1371/journal.pone.0161231")
        self.assertTrue(any(a["tipo"] == "correction" for a in r["avisos"]))

    def test_articulo_limpio(self):
        r = refcheck.revisa("10.1038/nature12373")
        self.assertEqual(r["avisos"], [])

    def test_lote_real_contra_la_api(self):
        r = refcheck.revisa_lote(["10.1371/journal.pone.0161231",   # corregido
                                  "10.1016/j.nbd.2012.05.020",     # retractado
                                  "10.1038/nature12373",           # limpio
                                  "10.9999/no.existe.9999"])       # no está
        por = {x["doi"]: x for x in r}
        self.assertEqual(len(r), 4)
        self.assertTrue(any(a["tipo"] == "correction"
                            for a in por["10.1371/journal.pone.0161231"]["avisos"]))
        self.assertEqual(por["10.1016/j.nbd.2012.05.020"]["avisos"][0]["gravedad"], 3)
        self.assertEqual(por["10.1038/nature12373"]["avisos"], [])
        self.assertEqual(por["10.9999/no.existe.9999"]["estado"], "desconocido")


class Cortesia(unittest.TestCase):
    """Stay inside the rate the server states, not the one I assumed.

    Measured 2026-09-09: no mailto puts you in `public-array` at 1 request per
    second; a mailto puts you in `polite-array` at 3. The old default paused
    0.4 s — 2.5 requests a second — and most users never set a mailto.
    """

    def test_por_defecto_es_el_limite_publico(self):
        self.assertEqual(refcheck.Ritmo().hueco, 1.0)

    def test_aprende_el_pool_cortes(self):
        r = refcheck.Ritmo()
        r.aprende({"x-rate-limit-limit": "3", "x-rate-limit-interval": "1s"})
        self.assertAlmostEqual(r.hueco, 1 / 3, places=4)

    def test_aprende_intervalos_que_no_son_de_un_segundo(self):
        r = refcheck.Ritmo()
        r.aprende({"x-rate-limit-limit": "50", "x-rate-limit-interval": "10s"})
        self.assertAlmostEqual(r.hueco, 0.2, places=4)

    def test_cabecera_ausente_no_afloja_el_limite(self):
        r = refcheck.Ritmo()
        r.aprende({})
        self.assertEqual(r.hueco, 1.0)

    def test_cabecera_absurda_no_afloja_el_limite(self):
        for mala in ({"x-rate-limit-limit": "muchas", "x-rate-limit-interval": "1s"},
                     {"x-rate-limit-limit": "0", "x-rate-limit-interval": "1s"},
                     {"x-rate-limit-limit": "3", "x-rate-limit-interval": "0s"},
                     {"x-rate-limit-limit": "3"}):
            r = refcheck.Ritmo()
            r.aprende(mala)
            self.assertEqual(r.hueco, 1.0, mala)

    def test_espera_lo_que_falta_y_no_mas(self):
        r = refcheck.Ritmo(limite=1, intervalo=0.2)
        t0 = time.monotonic()
        r.espera()                       # first call: nothing to wait for
        primero = time.monotonic() - t0
        r.espera()                       # second: must cover the 0.2 s gap
        total = time.monotonic() - t0
        self.assertLess(primero, 0.05)
        self.assertGreaterEqual(total, 0.19)
        self.assertLess(total, 0.45)

    def test_el_lote_pide_permiso_antes_de_llamar(self):
        """The pacing must sit in the request path, not in an optional argument."""
        vistos = []
        ritmo = refcheck.Ritmo()
        ritmo.espera = lambda: vistos.append("waited")

        respuesta = io.BytesIO(b'{"message":{"items":[]}}')
        respuesta.headers = {"x-rate-limit-limit": "3", "x-rate-limit-interval": "1s"}

        with mock.patch.object(refcheck, "RITMO", ritmo), \
             mock.patch("urllib.request.urlopen") as u:
            u.return_value.__enter__.return_value = respuesta
            refcheck.consulta_lote(["10.1/a"])

        self.assertEqual(vistos, ["waited"], "the batch call did not pace itself")
        self.assertAlmostEqual(ritmo.hueco, 1 / 3, places=4,
                               msg="the declared rate was not read back off the response")


def _rw(tipo, rid, doi="10.1234/notice", fecha=(2019, 2, 1)):
    return {"DOI": doi, "type": tipo, "label": tipo.replace("_", " ").capitalize(),
            "source": "retraction-watch", "record-id": rid,
            "updated": {"date-parts": [list(fecha)]}}


class Contradicciones(unittest.TestCase):
    """Two assertions from one upstream record that disagree about what happened.

    Crossref appends rather than overwrites when a Retraction Watch record
    changes its nature, so the API serves both the old verdict and the new one
    with identical timestamps (CR-2746). Picking the worst is the expensive
    error: it bins a citation that was never retracted.
    """

    def test_mismo_registro_tipos_distintos_se_marca(self):
        a = refcheck.avisos_de({"updated-by": [_rw("retraction", 19937),
                                               _rw("expression_of_concern", 19937)]})
        self.assertTrue(all(x["contradice"] for x in a))
        self.assertEqual(sorted(a[0]["contradice"] + a[1]["contradice"]),
                         ["expression_of_concern", "retraction"])

    def test_ficha_marca_el_trabajo_entero(self):
        f = refcheck.ficha("10.1148/85.3.474",
                           {"updated-by": [_rw("retraction", 19937),
                                           _rw("expression_of_concern", 19937)]})
        self.assertTrue(f["contradictorio"])

    def test_informe_no_grita_la_retractacion_rancia(self):
        f = refcheck.ficha("10.1148/85.3.474",
                           {"updated-by": [_rw("retraction", 19937),
                                           _rw("expression_of_concern", 19937)]})
        txt = refcheck.informe([f])
        self.assertIn("CONTRADICTORY NOTICES", txt)
        self.assertNotIn("RETRACTED — do not cite this as evidence", txt)
        self.assertIn("retractiondatabase.org", txt)
        self.assertIn("contradicts", txt)

    def test_registros_distintos_no_son_contradiccion(self):
        """A paper genuinely corrected and later retracted is not a data bug."""
        f = refcheck.ficha("10.1234/x", {"updated-by": [_rw("correction", 100),
                                                        _rw("retraction", 200)]})
        self.assertFalse(f["contradictorio"])
        self.assertIn("RETRACTED", refcheck.informe([f]))

    def test_el_mismo_aviso_repetido_se_enseña_una_vez(self):
        """10.1038/nature12968 comes back with its retraction listed twice.

        Two identical lines make the reader look for a difference that is not
        there. Identical on every field, so nothing that could disagree is being
        hidden — that is what the contradiction check is for.
        """
        u = {"type": "retraction", "DOI": "10.1038/nature13598",
             "updated": {"date-parts": [[2014, 7, 2]]}, "source": "publisher"}
        rw = dict(u, source="retraction-watch")
        rw["record-id"] = "2081"
        f = refcheck.ficha("10.1038/nature12968", {"updated-by": [rw, u]})
        self.assertEqual(len(f["avisos"]), 1)
        self.assertEqual(refcheck.informe([f]).count("nature13598"), 1)

    def test_el_mismo_aviso_con_dos_fechas_es_uno_solo(self):
        """`10.1016/j.engfailanal.2019.01.024` is a withdrawn paper whose own DOI
        carries the retraction twice, deposited 2019-03-19 and again 2019-04-01.

        One withdrawal printed as two reads like a paper that was retracted, and
        then retracted again. The earliest date survives, because a re-deposit is
        not a second event.
        """
        uno = {"type": "retraction", "DOI": "10.1016/j.engfailanal.2019.01.024",
               "updated": {"date-parts": [[2019, 3, 19]]}}
        dos = dict(uno, updated={"date-parts": [[2019, 4, 1]]})
        f = refcheck.ficha("10.1016/j.engfailanal.2019.01.024",
                           {"updated-by": [dos, uno]})
        self.assertEqual(len(f["avisos"]), 1)
        self.assertEqual(f["avisos"][0]["fecha"], "2019-03-19")

    def test_dos_avisos_distintos_del_mismo_tipo_siguen_siendo_dos(self):
        """Collapsing by (type, DOI) must not swallow a second, real notice.

        A paper corrected in 2019 and corrected again in 2021 has two notices
        with two DOIs, and hiding one of them would be a worse bug than the
        duplicate it fixes.
        """
        a = {"type": "correction", "DOI": "10.1/c1",
             "updated": {"date-parts": [[2019, 1, 1]]}}
        b = {"type": "correction", "DOI": "10.1/c2",
             "updated": {"date-parts": [[2021, 5, 5]]}}
        f = refcheck.ficha("10.1/x", {"updated-by": [a, b]})
        self.assertEqual(len(f["avisos"]), 2)

    def test_avisos_sin_doi_se_separan_por_fecha(self):
        """With no notice DOI there is nothing else to tell two apart by."""
        a = {"type": "correction", "DOI": "", "updated": {"date-parts": [[2019, 1, 1]]}}
        b = {"type": "correction", "DOI": "", "updated": {"date-parts": [[2021, 5, 5]]}}
        f = refcheck.ficha("10.1/x", {"updated-by": [a, b]})
        self.assertEqual(len(f["avisos"]), 2)

    def test_fecha_vaga_no_borra_la_precisa(self):
        """min() over the raw strings would pick "2019" and lose the day."""
        self.assertEqual(refcheck.fecha_mas_temprana("2019", "2019-03-19"),
                         "2019-03-19")
        self.assertEqual(refcheck.fecha_mas_temprana("2020-01-02", "2019"), "2019")
        self.assertEqual(refcheck.fecha_mas_temprana("", "2019-03-19"), "2019-03-19")
        self.assertEqual(refcheck.fecha_mas_temprana("", ""), "")

    def test_al_deduplicar_sobrevive_la_copia_con_record_id(self):
        """Otherwise the contradiction check loses the evidence it runs on.

        The publisher's copy of a notice is anonymous; only the Retraction Watch
        one carries the record-id that proves two assertions share an origin. If
        the anonymous copy won, a stale retraction sitting next to its own
        downgrade would stop being flagged and start being shouted.
        """
        publicador = {"type": "retraction", "DOI": "10.1/r", "source": "publisher",
                      "updated": {"date-parts": [[2020, 1, 1]]}}
        rw = dict(publicador, source="retraction-watch")
        rw["record-id"] = 19937
        eoc = {"type": "expression_of_concern", "DOI": "10.1/e",
               "source": "retraction-watch", "record-id": 19937,
               "updated": {"date-parts": [[2020, 1, 1]]}}
        # publisher copy first on purpose: that is the order that used to break it
        f = refcheck.ficha("10.1/x", {"updated-by": [publicador, rw, eoc]})
        self.assertEqual(len(f["avisos"]), 2)
        self.assertTrue(f["contradictorio"],
                        "the deduplication threw away the record-id and disarmed the check")

    def test_dos_avisos_del_mismo_tipo_en_fechas_distintas_se_quedan(self):
        u1 = {"type": "correction", "DOI": "10.1/a", "updated": {"date-parts": [[2019, 1, 1]]}}
        u2 = {"type": "correction", "DOI": "10.1/b", "updated": {"date-parts": [[2021, 5, 4]]}}
        f = refcheck.ficha("10.1234/x", {"updated-by": [u1, u2]})
        self.assertEqual(len(f["avisos"]), 2)

    def test_sin_record_id_no_se_agrupa(self):
        """Without a record-id there is no evidence the two share an origin."""
        f = refcheck.ficha("10.1234/x", {"updated-by": [
            {"DOI": "a", "type": "correction", "source": "publisher"},
            {"DOI": "b", "type": "retraction", "source": "publisher"}]})
        self.assertFalse(f["contradictorio"])

    def test_mismo_registro_mismo_tipo_no_es_contradiccion(self):
        f = refcheck.ficha("10.1234/x", {"updated-by": [_rw("retraction", 7, doi="10.1/a"),
                                                        _rw("retraction", 7, doi="10.1/b")]})
        self.assertFalse(f["contradictorio"])

    @unittest.skipUnless(os.environ.get("REFCHECK_RED") == "1", "necesita red: REFCHECK_RED=1")
    def test_contra_la_api_real(self):
        """The live record that started all this. If Crossref fixes CR-2746 this
        test goes red — which is the correct way to find out."""
        r = refcheck.revisa("10.1148/85.3.474")
        self.assertTrue(r["contradictorio"],
                        "10.1148/85.3.474 no longer carries contradictory assertions "
                        "— check whether CR-2746 was fixed, then relax this test")


class ExtraccionPmid(unittest.TestCase):
    """A PMID is only a PMID where the text says so.

    The danger here is not missing one, it is inventing one: a bibliography is
    made of numbers — years, pages, volumes, ISBNs — and a greedy pattern would
    ship a stranger's page number to NCBI and then report back on whatever
    unrelated paper happens to hold that id.
    """

    def test_forma_vancouver(self):
        self.assertEqual(refcheck.pmids_de("Zhu N, et al. N Engl J Med. 2020. PMID: 31978945."),
                         ["31978945"])

    def test_sin_dos_puntos(self):
        self.assertEqual(refcheck.pmids_de("PMID 31978945"), ["31978945"])

    def test_campo_bibtex(self):
        self.assertEqual(refcheck.pmids_de("  pmid = {31978945},"), ["31978945"])

    def test_url_de_pubmed(self):
        self.assertEqual(refcheck.pmids_de("https://pubmed.ncbi.nlm.nih.gov/31978945/"),
                         ["31978945"])

    def test_url_antigua_de_pubmed(self):
        self.assertEqual(refcheck.pmids_de("http://www.ncbi.nlm.nih.gov/pubmed/17284678"),
                         ["17284678"])

    def test_numeros_sueltos_NO_son_pmids(self):
        suelto = ("Smith J. Lancet 1998;351(9103):637-41. Volume 351, ISBN 9780262033848, "
                  "pages 12345678 to 12345679, year 2019.")
        self.assertEqual(refcheck.pmids_de(suelto), [])

    def test_un_id_demasiado_largo_no_se_recorta(self):
        """`PMID: 315789451` must not become a lookup of PMID 31578945.

        Truncating to the first eight digits would return a real, unrelated
        paper and report on it as if it were the one cited — the worst kind of
        wrong answer, because it looks like an answer.
        """
        self.assertEqual(refcheck.pmids_de("PMID: 315789451"), ["315789451"])
        with mock.patch.object(refcheck, "consulta_pmids") as c:
            r = refcheck.resuelve_pmids(["315789451"])
        c.assert_not_called()        # no point asking: PubMed cannot hold it
        self.assertEqual(r["315789451"]["estado"], "desconocido")

    def test_ceros_a_la_izquierda_y_duplicados(self):
        t = "PMID: 0031978945 y https://pubmed.ncbi.nlm.nih.gov/31978945/"
        self.assertEqual(refcheck.pmids_de(t), ["31978945"])

    def test_orden_de_lectura(self):
        self.assertEqual(refcheck.pmids_de("PMID: 2 no, PMID: 31978945, PMID: 17284678")[1:],
                         ["31978945", "17284678"])


def _resumen(pmid, doi=None, titulo="A paper", fecha="1979 Jan"):
    ids = [{"idtype": "pubmed", "value": pmid}]
    if doi:
        ids.append({"idtype": "doi", "value": doi})
    return {"uid": pmid, "title": titulo, "pubdate": fecha, "articleids": ids}


class ResolucionPmid(unittest.TestCase):
    """Three ways to end without a DOI, and they are three different sentences.

    Folding them together is the same mistake the tool already made once with
    failed lookups: a reader reads silence as "clean", and none of these three
    are clean.
    """

    def test_registro_con_doi(self):
        with mock.patch.object(refcheck, "consulta_pmids",
                               return_value={"1": _resumen("1", "10.1/A")}):
            r = refcheck.resuelve_pmids(["1"])
        self.assertEqual(r["1"]["estado"], "ok")
        self.assertEqual(r["1"]["doi"], "10.1/a")     # normalised like every other DOI

    def test_registro_sin_doi_no_es_limpio(self):
        with mock.patch.object(refcheck, "consulta_pmids",
                               return_value={"1": _resumen("1")}):
            r = refcheck.resuelve_pmids(["1"])
        self.assertEqual(r["1"]["estado"], "sin_doi")

    def test_pmid_inexistente(self):
        with mock.patch.object(refcheck, "consulta_pmids", return_value={}):
            r = refcheck.resuelve_pmids(["999999999"])
        self.assertEqual(r["999999999"]["estado"], "desconocido")

    def test_fallo_de_red_NO_se_disfraza(self):
        with mock.patch.object(refcheck, "consulta_pmids",
                               side_effect=ConnectionError("boom")):
            r = refcheck.resuelve_pmids(["1", "2"])
        self.assertEqual([v["estado"] for v in r.values()], ["sin_comprobar"] * 2)

    def test_parte_en_lotes(self):
        vistos = []

        def falso(trozo, **kw):
            vistos.append(len(trozo))
            return {p: _resumen(p, "10.1/" + p) for p in trozo}

        with mock.patch.object(refcheck, "consulta_pmids", side_effect=falso):
            refcheck.resuelve_pmids([str(i) for i in range(1, 251)])
        self.assertEqual(vistos, [refcheck.LOTE_PMID, refcheck.LOTE_PMID, 50])

    def test_un_lote_muerto_no_se_lleva_a_los_demas(self):
        def falso(trozo, **kw):
            if trozo[0] == "1":
                raise ConnectionError("boom")
            return {p: _resumen(p, "10.1/" + p) for p in trozo}

        with mock.patch.object(refcheck, "consulta_pmids", side_effect=falso), \
             mock.patch.object(refcheck, "LOTE_PMID", 1):
            r = refcheck.resuelve_pmids(["1", "2"])
        self.assertEqual(r["1"]["estado"], "sin_comprobar")
        self.assertEqual(r["2"]["estado"], "ok")

    def test_el_lote_pide_permiso_antes_de_llamar(self):
        """NCBI allows 3/s without a key. Same discipline as with Crossref."""
        vistos = []
        ritmo = refcheck.Ritmo()
        ritmo.espera = lambda: vistos.append("waited")
        cuerpo = json.dumps({"result": {"uids": ["1"],
                                        "1": _resumen("1", "10.1/A")}}).encode()
        respuesta = io.BytesIO(cuerpo)
        respuesta.headers = {"x-ratelimit-limit": "3"}   # NCBI's spelling, no interval

        with mock.patch.object(refcheck, "RITMO_PUBMED", ritmo), \
             mock.patch("urllib.request.urlopen") as u:
            u.return_value.__enter__.return_value = respuesta
            salida = refcheck.consulta_pmids(["1"])

        self.assertEqual(vistos, ["waited"])
        self.assertIn("1", salida)
        self.assertAlmostEqual(ritmo.hueco, 1 / 3, places=4)

    def test_error_dentro_de_la_respuesta_no_es_registro(self):
        cuerpo = json.dumps({"result": {"uids": ["9"],
                                        "9": {"uid": "9", "error": "cannot get document summary"}}}).encode()
        respuesta = io.BytesIO(cuerpo)
        respuesta.headers = {}
        with mock.patch("urllib.request.urlopen") as u:
            u.return_value.__enter__.return_value = respuesta
            self.assertEqual(refcheck.consulta_pmids(["9"]), {})


# A real MEDLINE export, trimmed to the tags that matter but not otherwise
# touched: the wrapped continuation lines, the `AID … [pii]` decoys and the
# cross-references are exactly as PubMed serves them on 2026-09-12. Four
# records, and between them every trap: thirteen CIN commentaries about the
# first paper, a RIN pointing at the notice that retracted the second, a title
# that wraps, and a book chapter whose only AID is a bookaccession, not a DOI.
NBIB = """PMID- 31978945
DP  - 2020 Feb 20
TI  - A Novel Coronavirus from Patients with Pneumonia in China, 2019.
LID - 10.1056/NEJMoa2001017 [doi]
JT  - The New England journal of medicine
CIN - N Engl J Med. 2020 Feb 20;382(8):760-762. doi: 10.1056/NEJMe2001126. PMID:
      31978944
CIN - Lancet. 2020 Feb 8;395(10222):391-393. doi: 10.1016/S0140-6736(20)30300-7. PMID:
      32035533
CIN - J Med Virol. 2020 May;92(5):461-463. doi: 10.1002/jmv.25711. PMID: 32073161
AID - NJ202002203820808 [pii]
AID - 10.1056/NEJMoa2001017 [doi]
SO  - N Engl J Med. 2020 Feb 20;382(8):727-733. doi: 10.1056/NEJMoa2001017. Epub 2020
      Jan 24.

PMID- 22668778
DP  - 2012 Sep
TI  - LRRK2 kinase activity mediates toxic interactions between genetic mutation and
      oxidative stress in a Drosophila model: suppression by curcumin.
LID - 10.1016/j.nbd.2012.05.020 [doi]
JT  - Neurobiology of disease
RIN - Neurobiol Dis. 2025 Jun 15;210:106930. doi: 10.1016/j.nbd.2025.106930. PMID:
      40320298
AID - S0969-9961(12)00206-9 [pii]
AID - 10.1016/j.nbd.2012.05.020 [doi]
SO  - Neurobiol Dis. 2012 Sep;47(3):385-92. doi: 10.1016/j.nbd.2012.05.020. Epub 2012
      Jun 2.

PMID- 5432876
DP  - 1970 Jun 10
TI  - Tryptophan metabolism in the magnesium deficient rat.
JT  - The Journal of vitaminology
AID - 10.5925/jnsv1954.16.140 [doi]
SO  - J Vitaminol (Kyoto). 1970 Jun 10;16(2):140-3. doi: 10.5925/jnsv1954.16.140.

PMID- 25905182
DP  - 2000
TI  - Role of Glucose and Lipids in the Atherosclerotic Cardiovascular Disease in
      Patients with Diabetes.
BTI - Endotext
AID - NBK278947 [bookaccession]
"""


class Medline(unittest.TestCase):
    """The `.nbib` PubMed hands you is a record format, not loose text.

    Read as text it answers about the wrong papers — measured 2026-09-12 on a
    200-record export: 15 foreign DOIs in, 200 of 200 real PMIDs out.
    """

    def test_se_reconoce(self):
        self.assertTrue(refcheck.es_medline(NBIB))

    def test_una_bibliografia_normal_no_se_confunde(self):
        self.assertFalse(refcheck.es_medline(
            "Zhu N, et al. N Engl J Med. 2020;382(8):727-733. PMID: 31978945.\n"
            "Lee BD, et al. doi:10.1016/j.nbd.2012.05.020\n"))

    def test_un_ris_no_se_confunde(self):
        # RIS has the same `XX  - value` shape, and must keep going through the
        # forgiving path, where its DOIs are found perfectly well.
        ris = ("TY  - JOUR\nAU  - Zhu, Na\nTI  - A Novel Coronavirus\n"
               "DO  - 10.1056/NEJMoa2001017\nN1  - PMID: 31978945\nER  -\n")
        self.assertFalse(refcheck.es_medline(ris))
        self.assertEqual(refcheck.dois_de(ris), ["10.1056/nejmoa2001017"])
        self.assertEqual(refcheck.pmids_de(ris), ["31978945"])

    def test_un_bibtex_no_se_confunde(self):
        self.assertFalse(refcheck.es_medline(
            "@article{zhu2020,\n  title = {A Novel Coronavirus},\n"
            "  doi = {10.1056/NEJMoa2001017},\n  pmid = {31978945},\n}\n"))

    def test_cada_registro_trae_su_propio_par(self):
        regs = refcheck.registros_medline(NBIB)
        self.assertEqual([(r["pmid"], r["doi"]) for r in regs], [
            ("31978945", "10.1056/nejmoa2001017"),
            ("22668778", "10.1016/j.nbd.2012.05.020"),
            ("5432876", "10.5925/jnsv1954.16.140"),
            ("25905182", ""),
        ])

    def test_los_comentarios_ajenos_no_entran(self):
        # CIN is "Comment in": someone else's paper about yours. Reading it as a
        # reference reports on a paper the user never cited.
        dois, _, _ = refcheck.referencias_de(NBIB)
        for ajeno in ("10.1056/nejme2001126", "10.1016/s0140-6736(20)30300-7",
                      "10.1002/jmv.25711"):
            self.assertNotIn(ajeno, dois)

    def test_la_nota_de_retractacion_no_es_una_referencia(self):
        # RIN points at the notice that retracted this paper. It belongs in the
        # verdict, not in the list of things being checked.
        dois, _, _ = refcheck.referencias_de(NBIB)
        self.assertNotIn("10.1016/j.nbd.2025.106930", dois)

    def test_los_pmid_ajenos_no_entran(self):
        _, origen, sueltos = refcheck.referencias_de(NBIB)
        pmids = set(origen.values()) | {s["pmid"] for s in sueltos}
        self.assertEqual(pmids, {"31978945", "22668778", "5432876", "25905182"})

    def test_el_articulo_sin_doi_se_nombra_en_vez_de_desaparecer(self):
        _, _, sueltos = refcheck.referencias_de(NBIB)
        self.assertEqual(len(sueltos), 1)
        s = sueltos[0]
        self.assertEqual(s["pmid"], "25905182")
        self.assertEqual(s["estado"], "pmid_sin_doi")
        self.assertEqual(s["fecha"], "2000")
        self.assertIn("Atherosclerotic", s["titulo"])

    def test_un_titulo_partido_en_dos_lineas_se_recompone(self):
        regs = refcheck.registros_medline(NBIB)
        self.assertIn("oxidative stress in a Drosophila model", regs[1]["titulo"])

    def test_un_pii_no_se_confunde_con_un_doi(self):
        regs = refcheck.registros_medline(NBIB)
        self.assertEqual(regs[0]["doi"], "10.1056/nejmoa2001017")

    def test_no_hace_falta_preguntarle_a_nadie(self):
        # The file already states every identifier, so the round trip to NCBI a
        # loose bibliography needs is not just unnecessary here — making it would
        # be asking a public service for something already in hand.
        with mock.patch.object(refcheck, "resuelve_pmids",
                               side_effect=AssertionError("no debería consultar")):
            dois, origen, sueltos = refcheck.referencias_de(NBIB)
        self.assertEqual(len(dois), 3)
        self.assertEqual(origen["10.1016/j.nbd.2012.05.020"], "22668778")

    def test_un_fichero_vacio_o_sin_registros_no_revienta(self):
        self.assertEqual(refcheck.registros_medline(""), [])
        self.assertFalse(refcheck.es_medline(""))
        self.assertEqual(refcheck.registros_medline("PMID- \nTI  - nada\n"), [])

    def test_saltos_de_linea_de_windows(self):
        # A file downloaded on Windows and opened on Linux, which is most of them.
        regs = refcheck.registros_medline(NBIB.replace("\n", "\r\n"))
        self.assertEqual([r["pmid"] for r in regs],
                         ["31978945", "22668778", "5432876", "25905182"])


class Referencias(unittest.TestCase):
    def test_doi_y_pmid_del_mismo_articulo_son_una_referencia(self):
        texto = "Zhu N, et al. doi:10.1056/NEJMoa2001017. PMID: 31978945."
        with mock.patch.object(refcheck, "resuelve_pmids", return_value={
                "31978945": {"estado": "ok", "doi": "10.1056/nejmoa2001017"}}):
            dois, origen, sueltos = refcheck.referencias_de(texto)
        self.assertEqual(dois, ["10.1056/nejmoa2001017"])
        self.assertEqual(origen["10.1056/nejmoa2001017"], "31978945")
        self.assertEqual(sueltos, [])

    def test_pmid_sin_doi_llega_al_informe_como_no_comprobado(self):
        with mock.patch.object(refcheck, "resuelve_pmids", return_value={
                "759788": {"estado": "sin_doi", "titulo": "Old paper", "fecha": "1979 Jan"}}):
            dois, _, sueltos = refcheck.referencias_de("PMID: 759788")
        self.assertEqual(dois, [])
        self.assertEqual(sueltos[0]["estado"], "pmid_sin_doi")
        texto = refcheck.informe(sueltos)
        self.assertIn("no DOI", texto)
        self.assertNotIn("Nothing found", texto)

    def test_no_pubmed_no_toca_ncbi(self):
        with mock.patch.object(refcheck, "resuelve_pmids") as r:
            dois, origen, sueltos = refcheck.referencias_de("PMID: 31978945",
                                                            usar_pubmed=False)
        r.assert_not_called()
        self.assertEqual((dois, origen, sueltos), ([], {}, []))

    def test_sin_pmids_no_se_llama_a_ncbi(self):
        with mock.patch.object(refcheck, "resuelve_pmids") as r:
            refcheck.referencias_de("10.1038/nature12373")
        r.assert_not_called()

    def test_el_recuento_no_cuenta_lo_que_no_se_pudo_comprobar(self):
        resultados = [
            refcheck.ficha("10.1/a", {"updated-by": []}),
            {"doi": "", "pmid": "1", "estado": "pmid_sin_doi", "titulo": "", "fecha": "", "avisos": []},
            {"doi": "", "pmid": "2", "estado": "pmid_desconocido", "avisos": []}]
        texto = refcheck.informe(resultados)
        self.assertIn("1 reference(s) checked", texto)
        self.assertIn("1 PMID(s) have no DOI", texto)
        self.assertIn("1 PMID(s) do not exist", texto)

    def test_el_nombre_devuelve_el_identificador_que_escribio_quien_cita(self):
        self.assertEqual(refcheck.nombre({"doi": "10.1/a"}), "10.1/a")
        self.assertEqual(refcheck.nombre({"doi": "10.1/a", "pmid": "7"}), "10.1/a (PMID 7)")
        self.assertEqual(refcheck.nombre({"doi": "", "pmid": "7"}), "PMID 7")

    @unittest.skipUnless(os.environ.get("REFCHECK_RED") == "1", "necesita red: REFCHECK_RED=1")
    def test_contra_pubmed_real(self):
        """Three live records: one with a DOI, one from 1979 without, one that
        does not exist. If NCBI changes its answer shape, this goes red."""
        r = refcheck.resuelve_pmids(["31978945", "759788", "999999999"])
        self.assertEqual(r["31978945"]["estado"], "ok")
        self.assertEqual(r["31978945"]["doi"], "10.1056/nejmoa2001017")
        self.assertEqual(r["759788"]["estado"], "sin_doi")
        self.assertEqual(r["999999999"]["estado"], "desconocido")


def _xml(*articulos):
    """A minimal efetch reply. Each article is (pmid, doi, [(RefType, RefSource)])."""
    trozos = []
    for pmid, doi, ccs in articulos:
        cc = "".join(
            f'<CommentsCorrections RefType="{t}"><RefSource>{s}</RefSource>'
            f'<PMID Version="1">99{i}</PMID></CommentsCorrections>'
            for i, (t, s) in enumerate(ccs))
        trozos.append(
            f'<PubmedArticle><MedlineCitation><PMID Version="1">{pmid}</PMID>'
            f'<Article><ArticleTitle>Un titulo</ArticleTitle></Article>'
            f'<CommentsCorrectionsList>{cc}</CommentsCorrectionsList></MedlineCitation>'
            f'<PubmedData><ArticleIdList>'
            f'<ArticleId IdType="pubmed">{pmid}</ArticleId>'
            f'<ArticleId IdType="doi">{doi}</ArticleId>'
            f'</ArticleIdList></PubmedData></PubmedArticle>')
    return f"<PubmedArticleSet>{''.join(trozos)}</PubmedArticleSet>".encode()


class AvisosPubmed(unittest.TestCase):
    """PubMed's CommentsCorrections, which is the half Crossref does not have."""

    def test_lee_los_tipos_que_son_un_veredicto(self):
        x = _xml(("7", "10.1/a", [
            ("RetractionIn", "Lancet. 2010 Feb 6;375(9713):445. doi: 10.1016/x."),
            ("ErratumIn", "J. 2025 Feb 1;117(2):380. doi: 10.1093/y."),
            ("ExpressionOfConcernIn", "J. 2024 Dec 1;116(12):2044. doi: 10.1093/z."),
        ]))
        avisos = refcheck._avisos_de_xml(x)["10.1/a"]["avisos"]
        self.assertEqual([a["tipo"] for a in avisos],
                         ["retraction", "erratum", "expression_of_concern"])
        self.assertEqual([a["fecha"] for a in avisos], ["2010", "2025", "2024"])
        self.assertEqual(avisos[0]["doi_aviso"], "10.1016/x")
        self.assertTrue(all(a["fuente"] == "pubmed" for a in avisos))

    def test_ignora_lo_que_no_es_un_aviso_de_cambio(self):
        """A letter to the editor is a conversation, not a verdict. The 1998
        Lancet paper carries 22 of them; printing those would drown the two
        that matter and teach the reader to skip the whole block."""
        x = _xml(("7", "10.1/a", [
            ("CommentIn", "Lancet. 1998;351:611. doi: 10.1016/c."),
            ("UpdateIn", "Cochrane. 2020. doi: 10.1002/u."),
            ("SummaryForPatientsIn", "Ann Intern Med. 2015. doi: 10.7326/s."),
            ("RetractionIn", "Lancet. 2010;375:445. doi: 10.1016/r."),
        ]))
        avisos = refcheck._avisos_de_xml(x)["10.1/a"]["avisos"]
        self.assertEqual([a["tipo"] for a in avisos], ["retraction"])

    def test_un_aviso_sin_doi_conserva_su_pmid(self):
        """Otherwise the report prints a bare https://doi.org/ and the reader
        is sent nowhere at all."""
        x = _xml(("7", "10.1/a", [("ErratumIn", "Lancet. 1998 Mar 21;351(9106):905.")]))
        a = refcheck._avisos_de_xml(x)["10.1/a"]["avisos"][0]
        self.assertEqual(a["doi_aviso"], "")
        self.assertEqual(a["pmid_aviso"], "990")
        self.assertIn("pubmed.ncbi.nlm.nih.gov/990/", refcheck.informe(
            [{"doi": "10.1/a", "estado": "ok", "titulo": "", "avisos": [a]}]))

    def test_no_coge_el_doi_de_una_referencia_ajena(self):
        """A record with no DOI of its own sits next to a reference list full of
        other people's DOIs. Grabbing one of those would report a change notice
        against a paper the reader never cited."""
        x = (b'<PubmedArticleSet><PubmedArticle><MedlineCitation>'
             b'<PMID Version="1">7</PMID><Article><ArticleTitle>T</ArticleTitle></Article>'
             b'</MedlineCitation><PubmedData><ArticleIdList>'
             b'<ArticleId IdType="pubmed">7</ArticleId></ArticleIdList>'
             b'<ReferenceList><Reference><ArticleIdList>'
             b'<ArticleId IdType="doi">10.9/ajena</ArticleId>'
             b'</ArticleIdList></Reference></ReferenceList>'
             b'</PubmedData></PubmedArticle></PubmedArticleSet>')
        self.assertEqual(refcheck._avisos_de_xml(x), {})


class FusionDeRegistros(unittest.TestCase):
    """Merging the two registers, which is where the honesty lives."""

    def _fusiona(self, resultados, xml):
        with mock.patch.object(refcheck, "_pide_ncbi") as p:
            p.side_effect = [json.dumps({"esearchresult": {"idlist": ["7"]}}).encode(), xml]
            return refcheck.fusiona_pubmed(resultados)

    def test_anade_lo_que_crossref_calla(self):
        r = [{"doi": "10.1/a", "estado": "ok", "titulo": "", "avisos": []}]
        self._fusiona(r, _xml(("7", "10.1/a",
                               [("ExpressionOfConcernIn", "J. 2024. doi: 10.1016/eoc.")])))
        self.assertEqual(len(r[0]["avisos"]), 1)
        self.assertEqual(r[0]["avisos"][0]["fuente"], "pubmed")
        self.assertIn("per PubMed", refcheck.informe(r))

    def test_no_repite_el_mismo_aviso_con_otro_nombre(self):
        """`correction` and `erratum` are one word in two vocabularies. Two
        lines for one notice is noise, and a disagreement banner over a
        vocabulary difference teaches the reader to ignore the banner."""
        crossref = {"tipo": "correction", "gravedad": 1, "fecha": "2024-03-21",
                    "doi_aviso": "10.1016/fix", "etiqueta": "Correction",
                    "fuente": "crossref", "registro": None, "contradice": []}
        r = [{"doi": "10.1/a", "estado": "ok", "titulo": "", "avisos": [crossref]}]
        self._fusiona(r, _xml(("7", "10.1/a", [("ErratumIn", "J. 2024. doi: 10.1016/fix.")])))
        self.assertEqual(len(r[0]["avisos"]), 1)
        self.assertFalse(r[0].get("discrepancia"))

    def test_conserva_las_dos_cuando_difieren_en_GRAVEDAD(self):
        """Crossref files 10.1016/s0140-6736(04)15715-2 as a correction and
        PubMed as a retraction. Keeping only one drops a severity-3 verdict on
        a coin flip, which is the exact failure this tool exists to avoid."""
        crossref = {"tipo": "correction", "gravedad": 1, "fecha": "2004-03-06",
                    "doi_aviso": "10.1016/same", "etiqueta": "Correction",
                    "fuente": "crossref", "registro": None, "contradice": []}
        r = [{"doi": "10.1/a", "estado": "ok", "titulo": "", "avisos": [crossref]}]
        self._fusiona(r, _xml(("7", "10.1/a", [("RetractionIn", "J. 2004. doi: 10.1016/same.")])))
        self.assertEqual(len(r[0]["avisos"]), 2)
        self.assertEqual(r[0]["discrepancia"], ["10.1016/same"])
        self.assertIn("REGISTERS DISAGREE", refcheck.informe(r))

    def test_la_discrepancia_no_tapa_lo_que_ambos_confirman(self):
        """Both registers list the 2010 retraction of the 1998 Lancet paper and
        differ only over a 2004 notice. The headline must stay RETRACTED."""
        firme = {"tipo": "retraction", "gravedad": 3, "fecha": "2010-02-06",
                 "doi_aviso": "10.1016/ret", "etiqueta": "Retraction",
                 "fuente": "crossref", "registro": None, "contradice": []}
        blando = {"tipo": "correction", "gravedad": 1, "fecha": "2004-03-06",
                  "doi_aviso": "10.1016/same", "etiqueta": "Correction",
                  "fuente": "crossref", "registro": None, "contradice": []}
        r = [{"doi": "10.1/a", "estado": "ok", "titulo": "", "avisos": [firme, blando]}]
        self._fusiona(r, _xml(("7", "10.1/a", [("RetractionIn", "J. 2004. doi: 10.1016/same.")])))
        texto = refcheck.informe(r)
        self.assertIn("RETRACTED", texto)
        self.assertNotIn("REGISTERS DISAGREE", texto)

    def test_rescata_un_doi_que_crossref_no_tiene(self):
        """2.5% of retracted papers are not in Crossref at all — a whole
        publisher, eurrev, turned up in the sample. Leaving those as 'not
        found' files a live retraction under 'nothing to report'."""
        r = [{"doi": "10.1/a", "estado": "desconocido", "avisos": []}]
        self._fusiona(r, _xml(("7", "10.1/a", [("RetractionIn", "J. 2020. doi: 10.1016/r.")])))
        self.assertEqual(r[0]["estado"], "ok")
        self.assertTrue(r[0]["solo_pubmed"])
        self.assertEqual(r[0]["titulo"], "Un titulo")

    def test_si_pubmed_falla_no_se_pierde_la_respuesta_de_crossref(self):
        r = [{"doi": "10.1/a", "estado": "ok", "titulo": "T", "avisos": []}]
        with mock.patch.object(refcheck, "_pide_ncbi",
                               side_effect=ConnectionError("NCBI down")):
            refcheck.fusiona_pubmed(r)
        self.assertEqual(r[0]["estado"], "ok")
        self.assertIn("NCBI down", r[0]["pubmed_error"])

    @unittest.skipUnless(os.environ.get("REFCHECK_RED") == "1", "necesita red: REFCHECK_RED=1")
    def test_contra_la_realidad_el_hueco_sigue_ahi(self):
        """10.1093/jnci/djr419 carries an expression of concern (2024) and an
        erratum (2025) in PubMed, and Crossref's record is empty. Measured
        2026-09-11. If Crossref ever deposits them, this goes red — which is
        how I want to find out."""
        rec = refcheck.avisos_pubmed(["10.1093/jnci/djr419"])["10.1093/jnci/djr419"]
        self.assertEqual(rec["pmid"], "22010178")
        tipos = {a["tipo"] for a in rec["avisos"]}
        self.assertIn("expression_of_concern", tipos)
        self.assertIn("erratum", tipos)
        obra = refcheck.consulta("10.1093/jnci/djr419")
        self.assertEqual(refcheck.avisos_de(obra), [])


class Titulos(unittest.TestCase):
    """Crossref serves the publisher's JATS markup and the XML's line breaks.

    Measured 2026-09-13 on a 1,000-record export: two of the 24 flagged papers
    printed a literal `<i>vs</i>` and `<scp>HbA1c</scp>`, and one title came out
    across three lines. A title the reader cannot read cannot be matched to the
    line in their document, which is the only job the title has here.
    """

    def test_quita_el_marcado_jats(self):
        self.assertEqual(refcheck.limpia_titulo("Effect on <scp>HbA1c</scp> levels"),
                         "Effect on HbA1c levels")
        self.assertEqual(refcheck.limpia_titulo("CO<sub>2</sub> and H<sub>2</sub>O"),
                         "CO2 and H2O")

    def test_junta_las_lineas_del_xml(self):
        crudo = "Sequential nephron blockade\n      <i>vs</i>\n      . dual blockade"
        self.assertEqual(refcheck.limpia_titulo(crudo),
                         "Sequential nephron blockade vs. dual blockade")

    def test_un_menor_que_de_verdad_se_queda(self):
        """Stripping anything between < and > would eat real mathematics."""
        self.assertEqual(refcheck.limpia_titulo("When a < b holds for all n"),
                         "When a < b holds for all n")

    def test_espacio_frances_intacto(self):
        self.assertEqual(refcheck.limpia_titulo("Une étude : le cas ; oui ?"),
                         "Une étude : le cas ; oui ?")

    def test_entidades(self):
        self.assertEqual(refcheck.limpia_titulo("Salt &amp; pressure"), "Salt & pressure")

    def test_vacio_y_nulo(self):
        self.assertEqual(refcheck.limpia_titulo(""), "")
        self.assertEqual(refcheck.limpia_titulo(None), "")

    def test_la_ficha_lo_aplica(self):
        obra = {"DOI": "10.1/a", "title": ["A <i>b</i> c"],
                "container-title": ["J <scp>Med</scp>"]}
        f = refcheck.ficha("10.1/a", obra)
        self.assertEqual(f["titulo"], "A b c")
        self.assertEqual(f["revista"], "J Med")


class Cache(unittest.TestCase):
    """Measured 2026-09-13: a real 1,000-record PubMed export takes 62 s to
    check and 0.39 s on the second run. Someone screening a systematic review
    runs that file again every time they add a batch, and the public registers
    should not pay for it twice.

    The dangerous half is what must NOT be cached, so that is what most of these
    are about: in a tool whose silence reads as "clean", a stored failure or a
    stale answer served without a word is worse than no cache at all.
    """

    def setUp(self):
        self.ruta = os.path.join(_tmpdir(self), "checked.json")

    def _ficha(self, doi="10.1/a", estado="ok", avisos=()):
        return {"doi": doi, "estado": estado, "titulo": "T", "avisos": list(avisos)}

    def test_ida_y_vuelta(self):
        refcheck.escribe_cache([self._ficha()], ruta=self.ruta, ahora=1000.0)
        vivos = refcheck.lee_cache(ruta=self.ruta, ahora=1060.0)
        self.assertIn("10.1/a", vivos)
        edad, r = vivos["10.1/a"]
        self.assertEqual(edad, 60.0)
        self.assertEqual(r["titulo"], "T")

    def test_una_consulta_fallida_NUNCA_se_guarda(self):
        """This is the whole safety argument. 'I could not reach Crossref' must
        never come back tomorrow as an answer, let alone as a clean one."""
        refcheck.escribe_cache([self._ficha(estado="sin_comprobar")],
                               ruta=self.ruta, ahora=1000.0)
        self.assertEqual(refcheck.lee_cache(ruta=self.ruta, ahora=1000.0), {})

    def test_desconocido_si_se_guarda(self):
        """'Crossref has no record under this DOI' is an answer, not a failure."""
        refcheck.escribe_cache([self._ficha(estado="desconocido")],
                               ruta=self.ruta, ahora=1000.0)
        self.assertIn("10.1/a", refcheck.lee_cache(ruta=self.ruta, ahora=1000.0))

    def test_caduca(self):
        refcheck.escribe_cache([self._ficha()], ruta=self.ruta, ahora=1000.0)
        viejo = 1000.0 + refcheck.CACHE_DIAS * 86400 + 1
        self.assertEqual(refcheck.lee_cache(ruta=self.ruta, ahora=viejo), {})

    def test_un_reloj_hacia_atras_no_sirve_del_futuro(self):
        refcheck.escribe_cache([self._ficha()], ruta=self.ruta, ahora=2000.0)
        self.assertEqual(refcheck.lee_cache(ruta=self.ruta, ahora=1000.0), {})

    def test_fichero_corrupto_no_revienta(self):
        with open(self.ruta, "w", encoding="utf-8") as f:
            f.write("{ this is not json")
        self.assertEqual(refcheck.lee_cache(ruta=self.ruta), {})
        refcheck.escribe_cache([self._ficha()], ruta=self.ruta, ahora=1000.0)
        self.assertIn("10.1/a", refcheck.lee_cache(ruta=self.ruta, ahora=1000.0))

    def test_no_se_puede_escribir_no_es_un_error(self):
        """A read-only home directory is someone else's problem, not a crash."""
        imposible = os.path.join(self.ruta, "nope", "checked.json")
        with open(self.ruta, "w", encoding="utf-8") as f:
            f.write("{}")          # now self.ruta is a file, so it cannot be a dir
        refcheck.escribe_cache([self._ficha()], ruta=imposible, ahora=1000.0)

    def test_es_privado(self):
        """It is a list of what someone has been reading."""
        refcheck.escribe_cache([self._ficha()], ruta=self.ruta, ahora=1000.0)
        self.assertEqual(os.stat(self.ruta).st_mode & 0o777, 0o600)

    def test_el_tope_tira_lo_mas_viejo(self):
        viejos = [{"doi": f"10.1/{i}", "estado": "ok", "titulo": "", "avisos": []}
                  for i in range(5)]
        for i, f in enumerate(viejos):
            refcheck.escribe_cache([f], ruta=self.ruta, ahora=1000.0 + i)
        with mock.patch.object(refcheck, "CACHE_MAX", 2):
            refcheck.escribe_cache([], ruta=self.ruta, ahora=1010.0)
        quedan = set(refcheck.lee_cache(ruta=self.ruta, ahora=1010.0))
        self.assertEqual(quedan, {"10.1/3", "10.1/4"})

    def test_el_informe_dice_que_viene_de_disco(self):
        r = [{"doi": "10.1/a", "estado": "ok", "titulo": "T", "avisos": [],
              "de_cache": 7200}]
        texto = refcheck.informe(r)
        self.assertIn("came from the local cache", texto)
        self.assertIn("2 h old", texto)

    def test_edad_legible(self):
        self.assertEqual(refcheck.edad_legible(30), "1 min")
        self.assertEqual(refcheck.edad_legible(3600 * 5), "5 h")
        self.assertEqual(refcheck.edad_legible(86400), "1 day")
        self.assertEqual(refcheck.edad_legible(86400 * 3), "3 days")


class CacheEnLaCLI(unittest.TestCase):
    """The end the reader sees: same report, no second trip over the wire."""

    def setUp(self):
        self.dir = _tmpdir(self)
        self.ruta = os.path.join(self.dir, "checked.json")
        self.refs = os.path.join(self.dir, "refs.txt")
        with open(self.refs, "w", encoding="utf-8") as f:
            f.write("10.5555/aaa\n10.5555/BBB\n")
        self.obras = {"10.5555/aaa": {"DOI": "10.5555/aaa", "title": ["Uno"], "updated-by": [
                          {"type": "retraction", "label": "Retraction",
                           "DOI": "10.5555/rrr", "updated": {"date-parts": [[2020, 1, 1]]}}]},
                      "10.5555/bbb": {"DOI": "10.5555/bbb", "title": ["Dos"]}}

    def _corre(self, argv):
        llamadas = []

        def falso_lote(dois, reintentos=3):
            llamadas.append(list(dois))
            return {d.lower(): self.obras[d.lower()] for d in dois
                    if d.lower() in self.obras}

        salida = io.StringIO()
        with mock.patch.object(refcheck, "consulta_lote", falso_lote), \
             mock.patch.object(refcheck, "fusiona_pubmed", lambda r, avisa=None: None), \
             mock.patch.object(refcheck, "ruta_cache", lambda: self.ruta), \
             mock.patch.object(sys, "argv", argv), \
             mock.patch.object(sys, "stdout", salida):
            codigo = refcheck.main()
        return codigo, salida.getvalue(), llamadas

    def test_la_segunda_vez_no_se_pregunta_nada(self):
        c1, t1, ll1 = self._corre(["refcheck.py", self.refs])
        self.assertEqual(len(ll1), 1)
        c2, t2, ll2 = self._corre(["refcheck.py", self.refs])
        self.assertEqual(ll2, [], "asked the API again for what it already had")
        self.assertEqual(c1, c2)
        self.assertIn("RETRACTED", t2)
        self.assertIn("2 of those came from the local cache", t2)
        # Same report, bar the line that admits where it came from.
        sin = "\n".join(l for l in t2.splitlines() if "local cache" not in l)
        self.assertEqual(t1.strip(), sin.strip())

    def test_no_cache_vuelve_a_preguntar(self):
        self._corre(["refcheck.py", self.refs])
        _, texto, llamadas = self._corre(["refcheck.py", self.refs, "--no-cache"])
        self.assertEqual(len(llamadas), 1)
        self.assertNotIn("local cache", texto)

    def test_solo_se_pregunta_por_lo_que_falta(self):
        self._corre(["refcheck.py", self.refs])
        with open(self.refs, "a", encoding="utf-8") as f:
            f.write("10.5555/ccc\n")
        self.obras["10.5555/ccc"] = {"DOI": "10.5555/ccc", "title": ["Tres"]}
        _, texto, llamadas = self._corre(["refcheck.py", self.refs])
        self.assertEqual(llamadas, [["10.5555/ccc"]])
        self.assertIn("3 reference(s) checked", texto)

    def test_el_json_cacheado_es_el_mismo_json(self):
        """A pipeline must not be able to tell the two apart, bar the one field
        that admits where the answer came from."""
        _, frio, _ = self._corre(["refcheck.py", self.refs, "--json", "--no-cache"])
        self._corre(["refcheck.py", self.refs])          # fill the cache
        _, caliente, llamadas = self._corre(["refcheck.py", self.refs, "--json"])
        self.assertEqual(llamadas, [])
        limpio = [{k: v for k, v in r.items() if k != "de_cache"}
                  for r in json.loads(caliente)]
        self.assertEqual(json.loads(frio), limpio)

    def test_un_fallo_no_se_queda_pegado(self):
        """The lookup fails, the run says so — and tomorrow's run asks again
        instead of serving yesterday's failure."""
        salida = io.StringIO()
        with mock.patch.object(refcheck, "consulta_lote",
                               side_effect=ConnectionError("down")), \
             mock.patch.object(refcheck, "fusiona_pubmed", lambda r, avisa=None: None), \
             mock.patch.object(refcheck, "ruta_cache", lambda: self.ruta), \
             mock.patch.object(sys, "argv", ["refcheck.py", self.refs]), \
             mock.patch.object(sys, "stdout", salida):
            self.assertEqual(refcheck.main(), 2)
        self.assertIn("could NOT be checked", salida.getvalue())
        _, texto, llamadas = self._corre(["refcheck.py", self.refs])
        self.assertEqual(len(llamadas), 1, "a failed lookup was cached")
        self.assertNotIn("local cache", texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
