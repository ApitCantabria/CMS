import unittest
from datetime import date
import sys
import types

import pandas as pd

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.get = lambda *args, **kwargs: None
    requests_stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

from cms.data import DataSourceError, load_all_sheets, normalize_lookup, prepare_frame
from cms.resources import (
    attach_restaurant_ratings,
    filter_resource_content,
    row_applies_on,
)
from cms.submissions import incidence_payload, restaurant_review_payload


class DataTests(unittest.TestCase):
    def test_lookup_is_case_accent_and_space_insensitive(self):
        self.assertEqual(normalize_lookup("  San   Vicente  "), "san vicente")
        self.assertEqual(normalize_lookup("Café"), "cafe")

    def test_schema_error_names_missing_columns(self):
        with self.assertRaises(DataSourceError) as error:
            prepare_frame("recursos", pd.DataFrame({"recurso": ["Museo"]}))
        self.assertIn("municipio", str(error.exception))

    def test_loading_isolates_a_failed_sheet(self):
        urls = {"recursos": "ok", "restaurantes": "bad"}

        def reader(url):
            if url == "bad":
                raise RuntimeError("network")
            return pd.DataFrame({"recurso": ["Museo"], "municipio": ["Comillas"]})

        result = load_all_sheets(urls, reader=reader)
        self.assertIn("recursos", result.frames)
        self.assertIn("restaurantes", result.errors)


class ResourceTests(unittest.TestCase):
    def test_date_rules_include_and_exclude_expected_days(self):
        row = pd.Series({
            "fecha_inicio": pd.Timestamp("2026-07-01"),
            "fecha_fin": pd.Timestamp("2026-07-31"),
            "dias_semana": "viernes",
            "fechas_excluidas": "31/07/2026",
        })
        self.assertTrue(row_applies_on(row, date(2026, 7, 24)))
        self.assertFalse(row_applies_on(row, date(2026, 7, 25)))
        self.assertFalse(row_applies_on(row, date(2026, 7, 31)))

    def test_resource_id_is_preferred(self):
        raw = pd.DataFrame([
            {"recurso_id": "r1", "recurso": "Museo", "contenido": "Correcto"},
            {"recurso_id": "r2", "recurso": "Museo", "contenido": "Otro"},
        ])
        content, _ = prepare_frame("contenidos_recursos", raw)
        result = filter_resource_content(
            content,
            resource_id="r1",
            resource_name="Museo",
            selected_date=date(2026, 7, 24),
        )
        self.assertEqual(result["contenido"].tolist(), ["Correcto"])

    def test_legacy_name_fallback_is_normalized(self):
        raw = pd.DataFrame([
            {"recurso": "  CÁMARA   OSCURA ", "contenido": "Disponible"},
        ])
        content, _ = prepare_frame("contenidos_recursos", raw)
        result = filter_resource_content(
            content,
            resource_id="",
            resource_name="cámara oscura",
            selected_date=date(2026, 7, 24),
        )
        self.assertEqual(len(result), 1)

    def test_ratings_support_partial_id_migration(self):
        restaurants, _ = prepare_frame(
            "restaurantes",
            pd.DataFrame([
                {"restaurante_id": "a", "restaurante": "A", "municipio": "M"},
                {"restaurante_id": "b", "restaurante": "B", "municipio": "M"},
            ]),
        )
        reviews, _ = prepare_frame(
            "experiencias_restaurantes",
            pd.DataFrame([
                {"restaurante_id": "a", "restaurante": "A", "rating": 5},
                {"restaurante_id": "", "restaurante": "B", "rating": 3},
            ]),
        )
        result = attach_restaurant_ratings(restaurants, reviews)
        self.assertEqual(result["rating_medio"].tolist(), [5.0, 3.0])


class SubmissionTests(unittest.TestCase):
    def test_payloads_include_stable_ids_and_strip_text(self):
        incidence = incidence_payload({
            "usuario_nombre": " Ana ",
            "tipo": "recurso",
            "categoria": "correccion",
            "nombre": " Museo ",
            "entidad_id": " r1 ",
            "asunto": " Error ",
            "descripcion": " Texto ",
        })
        self.assertEqual(incidence["entidad_id"], "r1")
        self.assertEqual(incidence["usuario_nombre"], "Ana")

        review = restaurant_review_payload({
            "restaurante_id": " rest1 ",
            "restaurante": " Local ",
            "fecha": "24/07/2026",
            "guia": " Ana ",
            "num_personas": 2,
            "precio_por_persona": " 20 ",
            "rating": 4,
            "comentario": " Bien ",
        })
        self.assertEqual(review["restaurante_id"], "rest1")
        self.assertEqual(review["comentario"], "Bien")


if __name__ == "__main__":
    unittest.main()
