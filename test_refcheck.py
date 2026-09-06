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


@unittest.skipUnless(os.environ.get("REFCHECK_RED") == "1", "necesita red: REFCHECK_RED=1")
class ContraLaRealidad(unittest.TestCase):
    def test_correccion_conocida(self):
        r = refcheck.revisa("10.1371/journal.pone.0161231")
        self.assertTrue(any(a["tipo"] == "correction" for a in r["avisos"]))

    def test_articulo_limpio(self):
        r = refcheck.revisa("10.1038/nature12373")
        self.assertEqual(r["avisos"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
