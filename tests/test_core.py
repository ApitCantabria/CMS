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

from cms.config import SHEET_URLS
from cms.data import DataSourceError, load_all_sheets, normalize_lookup, prepare_frame
from cms.resources import (
    attach_restaurant_ratings,
    filter_resource_content,
    latest_resource_confirmation,
    row_applies_on,
)
from cms.submissions import (
    incidence_payload,
    resource_confirmation_payload,
    resource_experience_payload,
    restaurant_review_payload,
)


class DataTests(unittest.TestCase):
    def test_sheet_exports_force_exactly_one_header_row(self):
        self.assertTrue(
            all("headers=1" in url for url in SHEET_URLS.values())
        )

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

    def test_annual_date_range_ignores_year(self):
        row = pd.Series({
            "fecha_inicio": pd.Timestamp("2026-06-15"),
            "fecha_fin": pd.Timestamp("2026-09-15"),
            "repeticion": "anual",
        })

        self.assertTrue(row_applies_on(row, date(2032, 7, 20)))
        self.assertFalse(row_applies_on(row, date(2032, 10, 20)))

    def test_annual_date_range_supports_year_end_spans(self):
        row = pd.Series({
            "fecha_inicio": pd.Timestamp("2026-10-21"),
            "fecha_fin": pd.Timestamp("2027-02-28"),
            "repeticion": "ANUAL",
        })

        self.assertTrue(row_applies_on(row, date(2032, 12, 1)))
        self.assertTrue(row_applies_on(row, date(2033, 2, 15)))
        self.assertFalse(row_applies_on(row, date(2033, 5, 1)))

    def test_annual_exclusions_compare_only_month_and_day(self):
        row = pd.Series({
            "fecha_inicio": pd.Timestamp("2026-01-01"),
            "fecha_fin": pd.Timestamp("2026-12-31"),
            "fechas_excluidas": "25/12/2026",
            "repeticion": "anual",
        })

        self.assertFalse(row_applies_on(row, date(2032, 12, 25)))
        self.assertTrue(row_applies_on(row, date(2032, 12, 26)))

    def test_point_in_time_date_range_still_uses_year(self):
        row = pd.Series({
            "fecha_inicio": pd.Timestamp("2026-06-15"),
            "fecha_fin": pd.Timestamp("2026-09-15"),
            "repeticion": "puntual",
        })

        self.assertTrue(row_applies_on(row, date(2026, 7, 20)))
        self.assertFalse(row_applies_on(row, date(2027, 7, 20)))

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

    def test_latest_resource_confirmation_prefers_stable_id(self):
        confirmations, _ = prepare_frame(
            "confirmaciones_recursos",
            pd.DataFrame([
                {
                    "recurso_id": "r1",
                    "recurso": "Museo",
                    "fecha": "01/07/2026",
                    "guia": "Ana",
                    "secciones": "Horarios",
                },
                {
                    "recurso_id": "r1",
                    "recurso": "Museo",
                    "fecha": "20/07/2026",
                    "guia": "Ana",
                    "secciones": "Toda la ficha",
                },
                {
                    "recurso_id": "r2",
                    "recurso": "Museo",
                    "fecha": "24/07/2026",
                    "guia": "Luis",
                    "secciones": "Tarifas",
                },
            ]),
        )

        latest = latest_resource_confirmation(
            confirmations,
            resource_id="r1",
            resource_name="Museo",
        )

        self.assertEqual(latest.strftime("%d/%m/%Y"), "20/07/2026")


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

        review_without_optional_values = restaurant_review_payload({
            "restaurante_id": "rest1",
            "restaurante": "Local",
            "fecha": "25/07/2026",
            "guia": "Ana",
            "num_personas": None,
            "precio_por_persona": "",
            "rating": 5,
            "comentario": "Muy bien",
        })
        self.assertEqual(review_without_optional_values["num_personas"], "")
        self.assertEqual(review_without_optional_values["precio_por_persona"], "")

        experience = resource_experience_payload({
            "recurso_id": " r1 ",
            "recurso": " Museo ",
            "fecha": "25/07/2026",
            "guia": " Ana ",
            "comentario": " Muy útil ",
        })
        self.assertEqual(experience["accion"], "nueva_experiencia_recurso")
        self.assertEqual(experience["recurso_id"], "r1")
        self.assertEqual(experience["comentario"], "Muy útil")

        confirmation = resource_confirmation_payload({
            "recurso_id": " r1 ",
            "recurso": " Museo ",
            "municipio": " Santander ",
            "guia": " Ana ",
            "secciones": [" Horarios ", " Tarifas "],
            "comentario": " Comprobado ",
        })
        self.assertEqual(confirmation["accion"], "confirmar_recurso")
        self.assertEqual(confirmation["secciones"], ["Horarios", "Tarifas"])
        self.assertEqual(confirmation["guia"], "Ana")


if __name__ == "__main__":
    unittest.main()
