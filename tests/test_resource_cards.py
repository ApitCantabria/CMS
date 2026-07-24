import unittest
from unittest.mock import MagicMock
import sys

import pandas as pd

sys.modules.setdefault("streamlit", MagicMock())

from app import build_resource_sections, render_html, st


class ResourceCardTests(unittest.TestCase):
    def test_card_markup_uses_streamlit_html_renderer(self):
        st.html.reset_mock()

        render_html(
            '<div class="card"><div class="disclaimer">Aviso</div></div>'
        )

        st.html.assert_called_once_with(
            '<div class="card"><div class="disclaimer">Aviso</div></div>'
        )

    def test_groups_rows_and_consolidates_shared_source(self):
        rows = pd.DataFrame([
            {
                "bloque": "tarifa",
                "subtipo": "General",
                "contenido": "5 €",
                "fuente": "Ayuntamiento",
                "prioridad": 1,
            },
            {
                "bloque": "Tarifas",
                "subtipo": "Reducida",
                "contenido": "3 €",
                "fuente": "Ayuntamiento",
                "prioridad": 2,
            },
        ])

        markup = build_resource_sections(rows)

        self.assertEqual(markup.count("resource-section-title\">Tarifas"), 1)
        self.assertEqual(markup.count("Fuente: Ayuntamiento"), 1)
        self.assertIn("General", markup)
        self.assertIn("Reducida", markup)

    def test_strips_html_hides_empty_rows_and_links_safe_urls(self):
        rows = pd.DataFrame([
            {
                "bloque": "horario",
                "subtipo": "General",
                "contenido": "<p>Lunes a viernes</p><script>oculto()</script>",
                "fuente": "",
            },
            {
                "bloque": "tarifa",
                "subtipo": "General",
                "contenido": "<div><br></div>",
                "fuente": "",
            },
            {
                "bloque": "contacto",
                "subtipo": "Reservas",
                "contenido": "https://example.com/reservas",
                "fuente": "",
            },
        ])

        markup = build_resource_sections(rows)

        self.assertIn("Lunes a viernes", markup)
        self.assertNotIn("<p>", markup)
        self.assertNotIn("<script>", markup)
        self.assertNotIn("oculto()", markup)
        self.assertNotIn("resource-section-title\">Tarifas", markup)
        self.assertIn('href="https://example.com/reservas"', markup)

    def test_keeps_distinct_sources_with_their_rows_and_adds_web_to_contact(self):
        rows = pd.DataFrame([
            {
                "bloque": "acceso",
                "subtipo": "Aforo",
                "contenido": "20 personas",
                "fuente": "Fuente A",
            },
            {
                "bloque": "misas",
                "subtipo": "Domingos",
                "contenido": "12:00",
                "fuente": "Fuente B",
            },
        ])

        markup = build_resource_sections(rows, "https://example.com")

        self.assertIn("Acceso · Aforo", markup)
        self.assertIn("Misas · Domingos", markup)
        self.assertEqual(markup.count("Fuente: Fuente A"), 1)
        self.assertEqual(markup.count("Fuente: Fuente B"), 1)
        self.assertIn("resource-section-title\">Contacto", markup)
        self.assertIn('href="https://example.com"', markup)

    def test_does_not_repeat_generic_information_in_additional_section(self):
        rows = pd.DataFrame([
            {
                "bloque": "información",
                "subtipo": "Servicios",
                "contenido": "Exposición permanente",
                "fuente": "Fuente oficial",
            },
        ])

        markup = build_resource_sections(rows)

        self.assertIn("resource-section-title\">Información adicional", markup)
        self.assertIn("detail-label\">Servicios", markup)
        self.assertNotIn("Información · Servicios", markup)

if __name__ == "__main__":
    unittest.main()
