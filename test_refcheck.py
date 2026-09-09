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
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refcheck


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
