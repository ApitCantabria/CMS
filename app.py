"""
Base de datos para guías
Recursos y Restaurantes
Formularios internos + Google Apps Script + Google Sheets
"""

import streamlit as st
import pandas as pd
from datetime import date
import textwrap
import re
import html as html_lib
import logging
from html.parser import HTMLParser
from urllib.parse import urlparse

from cms.config import SHEET_URLS
from cms.data import load_all_sheets
from cms.resources import (
    attach_restaurant_ratings,
    filter_resource_content,
    related_rows,
)
from cms.submissions import (
    incidence_payload,
    post_action,
    restaurant_review_payload,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AppitCant",
    page_icon="logo_apit.png",
    layout="centered",
    initial_sidebar_state="collapsed",
)

SELECT_MUNICIPIO = "Seleccione un municipio..."
TODOS_MUNICIPIOS = "Todos"
TODOS_RECURSOS = "Todos"


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────

def html(s: str) -> str:
    return textwrap.dedent(s).strip()


def esc_html_multiline(value) -> str:
    return esc(plain_text_content(value)).replace("\n", "<br>")
    

def esc(value) -> str:
    if pd.isna(value):
        return ""
    return html_lib.escape(str(value))


class _VisibleTextParser(HTMLParser):
    """Extract visible text without passing source HTML to the UI."""

    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "div", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "li", "main", "p",
        "section", "tr",
    }
    IGNORED_TAGS = {"script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORED_TAGS:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.IGNORED_TAGS:
            self.ignored_depth = max(0, self.ignored_depth - 1)
        elif not self.ignored_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored_depth:
            self.parts.append(data)


def plain_text_content(value) -> str:
    """Normalize plain/rich text into safe visible text."""
    if pd.isna(value):
        return ""

    raw = str(value).strip()
    if not raw:
        return ""

    parser = _VisibleTextParser()
    try:
        parser.feed(raw)
        parser.close()
        text = "".join(parser.parts)
    except Exception:
        text = raw

    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def has_visible_content(value) -> bool:
    return bool(plain_text_content(value))


def render_html(markup: str) -> None:
    """Prevent indented templates becoming visible Markdown code blocks."""
    st.markdown(html(markup), unsafe_allow_html=True)


def safe_key(texto: str) -> str:
    texto = str(texto).lower().strip()
    texto = re.sub(r"[^a-z0-9áéíóúñü]+", "_", texto)
    return texto.strip("_")


def safe_external_url(value) -> str:
    if pd.isna(value):
        return ""

    url = str(value).strip()
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    return url


def add_years_safe(value: date, years: int) -> date:
    try:
        return date(value.year + years, value.month, value.day)
    except ValueError:
        return date(value.year + years, value.month, 28)


def normalize_rating(value) -> int:
    rating = pd.to_numeric(value, errors="coerce")

    if pd.isna(rating):
        return 0

    return max(0, min(5, int(round(rating))))


# ─────────────────────────────────────────────
# GOOGLE APPS SCRIPT
# ─────────────────────────────────────────────

def post_to_apps_script(payload: dict):
    return post_action(
        st.secrets["APPS_SCRIPT_URL"],
        st.secrets["APPS_SCRIPT_TOKEN"],
        payload,
    )


def save_incidencia(data: dict):
    return post_to_apps_script(incidence_payload(data))


def save_resena_restaurante(data: dict):
    return post_to_apps_script(restaurant_review_payload(data))


# ─────────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────────

@st.cache_data(ttl=600)
def load_data():
    return load_all_sheets(SHEET_URLS)


def filtrar_contenido(
    df: pd.DataFrame,
    recurso: str,
    fecha: date,
    recurso_id="",
) -> pd.DataFrame:
    return filter_resource_content(
        df,
        resource_id=recurso_id,
        resource_name=recurso,
        selected_date=fecha,
    )


# ─────────────────────────────────────────────
# ESTILOS
# ─────────────────────────────────────────────

def inject_css():
    st.markdown(html("""
    <style>
    .block-container {
        max-width: 720px;
        padding: 1rem 1rem 4rem;
    }

    .app-header {
        margin: 0.4rem 0 1.6rem;
    }

    .app-title {
        color: #004EA8;
        font-size: 1.45rem;
        font-weight: 800;
        line-height: 1.15;
        margin: 1rem 0 0.45rem;
    }

    .app-subtitle {
        color: #374151;
        font-size: 0.98rem;
        margin: 0 0 0.35rem;
    }

    .app-meta {
        color: #6b7280;
        font-size: 0.84rem;
        margin: 0 0 1.15rem;
    }

    div.stButton > button:first-child {
        border: 1px solid #d1d5db;
        border-radius: 8px;
        background: #ffffff;
        color: #111827;
        font-weight: 500;
        padding: 0.55rem 0.85rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }

    div.stButton > button:first-child:hover {
        border-color: #004EA8;
        color: #004EA8;
    }

    .section-header {
        background: linear-gradient(135deg, #1a4a6b 0%, #0d7c9e 100%);
        color: white;
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        font-weight: 600;
    }

    .card {
        background: #ffffff;
        border: 1px solid #e5e9ef;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 1px 4px rgba(0,0,0,.06);
    }

    .card-title {
        font-weight: 700;
        font-size: 1rem;
        color: #1a2e40;
        margin-bottom: 0.4rem;
    }

    .badge {
        display: inline-block;
        background: #e0f2fe;
        color: #0369a1;
        border-radius: 20px;
        padding: 0.15rem 0.65rem;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 0.3rem;
        margin-bottom: 0.2rem;
    }

    .badge-green {
        background: #dcfce7;
        color: #15803d;
    }

    .badge-amber {
        background: #fef9c3;
        color: #92400e;
    }

    .bloque {
        background: #f4f8fc;
        border-left: 3px solid #0d7c9e;
        border-radius: 0 8px 8px 0;
        padding: 0.55rem 0.8rem;
        margin-bottom: 0.45rem;
    }

    .bloque-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #0d7c9e;
        text-transform: uppercase;
    }

    .bloque-subtipo {
        font-weight: 600;
        color: #1a2e40;
        font-size: 0.87rem;
    }

    .bloque-contenido {
        color: #374151;
        font-size: 0.87rem;
    }

    .reviews-title {
        color: #1a2e40;
        font-size: 0.78rem;
        font-weight: 700;
        margin: 0.85rem 0 0.25rem;
        text-transform: uppercase;
    }

    .review {
        background: #f9fafb;
        border: 1px solid #e5e9ef;
        border-radius: 8px;
        padding: 0.6rem 0.75rem;
        margin-top: 0.5rem;
    }

    .review-meta {
        color: #6b7280;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 0.25rem;
    }

    .review-comment {
        color: #374151;
        font-size: 0.87rem;
        line-height: 1.45;
    }

    .disclaimer {
        background: #fffbeb;
        border: 1px solid #fcd34d;
        border-radius: 8px;
        padding: 0.55rem 0.8rem;
        margin-top: 0.6rem;
        font-size: 0.78rem;
        color: #78350f;
    }

    .no-results {
        text-align: center;
        color: #6b7280;
        padding: 1.5rem 1rem;
        font-size: 0.9rem;
    }
    </style>
    """), unsafe_allow_html=True)


# ─────────────────────────────────────────────
# BLOQUES VISUALES
# ─────────────────────────────────────────────

def build_bloque(bloque_tipo, subtipo, contenido, fuente):
    if not has_visible_content(contenido):
        return ""

    fuente_html = (
        f'<br><small style="color:#9ca3af">Fuente: {esc(plain_text_content(fuente))}</small>'
        if has_visible_content(fuente) else ""
    )

    return (
        '<div class="bloque">'
        f'<div class="bloque-label">{esc(plain_text_content(bloque_tipo))}</div>'
        f'<div class="bloque-subtipo">{esc(plain_text_content(subtipo))}</div>'
        f'<div class="bloque-contenido">{esc_html_multiline(contenido)}{fuente_html}</div>'
        '</div>'
    )


def build_bloques_contenido(contenido_fecha: pd.DataFrame) -> str:
    """Render meaningful rows or a consistent empty-resource placeholder."""
    bloques = []

    if not contenido_fecha.empty and "bloque" in contenido_fecha.columns:
        sort_cols = [
            col for col in ["prioridad", "bloque", "subtipo"]
            if col in contenido_fecha.columns
        ]
        if sort_cols:
            contenido_fecha = contenido_fecha.sort_values(
                sort_cols,
                na_position="last",
            )

        for bloque_tipo, grupo in contenido_fecha.groupby(
            "bloque",
            sort=False,
            dropna=False,
        ):
            for _, fila in grupo.iterrows():
                bloque = build_bloque(
                    bloque_tipo,
                    fila.get("subtipo", ""),
                    fila.get("contenido", ""),
                    fila.get("fuente", ""),
                )
                if bloque:
                    bloques.append(bloque)

    if bloques:
        return "".join(bloques)

    return (
        '<div class="no-results">'
        'No hay contenido disponible todavía.'
        '</div>'
    )


def build_disclaimer(web, ultima_act):
    web_link = ""
    safe_web = safe_external_url(web)

    if safe_web:
        web_link = f' · <a href="{esc(safe_web)}" target="_blank" rel="noopener noreferrer">Web oficial</a>'

    if pd.notna(ultima_act) and ultima_act:
        try:
            fecha_act = pd.to_datetime(ultima_act).strftime("%d/%m/%Y")
            act_str = f" · Última actualización: <strong>{fecha_act}</strong>"
        except Exception:
            act_str = ""
    else:
        act_str = ""

    return (
        '<div class="disclaimer">'
        '<strong>Aviso:</strong> La información puede estar desactualizada. '
        'Contrástela con la fuente oficial antes de utilizarla.'
        f'{web_link}{act_str}'
        '</div>'
    )


def build_resena(r_stars, guia, fecha_str, n_p, comentario):
    return (
        '<div class="review">'
        '<div class="review-meta">'
        f'{esc(r_stars)} · {esc(guia)} · {esc(fecha_str)} · {esc(n_p)} pax'
        '</div>'
        '<div class="review-comment">'
        f'{esc(comentario)}'
        '</div>'
        '</div>'
    )


# ─────────────────────────────────────────────
# FORMULARIOS
# ─────────────────────────────────────────────

def mensaje_error_envio():
    st.error(
        "No ha sido posible enviar la información. "
        "Inténtelo de nuevo más tarde o contacte con APIT Cantabria."
    )


def formulario_incidencia(
    tipo,
    categoria,
    nombre,
    municipio="",
    item_key="",
    entidad_id="",
):
    key_parts = [tipo, categoria, municipio, nombre, item_key]
    form_key = "form_incidencia_" + "_".join(
        safe_key(part) for part in key_parts if str(part).strip()
    )

    with st.expander("Reportar dato incorrecto", expanded=False):
        with st.form(form_key):

            guia = st.text_input(
                "Nombre del guía",
                placeholder="Nombre y apellidos",
                key=f"guia_{form_key}",
            )

            descripcion = st.text_area(
                "¿Qué dato es incorrecto o falta?",
                placeholder="Indique brevemente qué información debe corregirse o completarse.",
                key=f"descripcion_{form_key}",
            )

            enviar = st.form_submit_button("Enviar")

            if enviar:
                if not guia.strip():
                    st.warning("Indique su nombre.")
                    return

                if not descripcion.strip():
                    st.warning("Describa brevemente el problema.")
                    return

                try:
                    save_incidencia({
                        "usuario_nombre": guia,
                        "tipo": tipo,
                        "categoria": categoria,
                        "nombre": nombre,
                        "entidad_id": entidad_id,
                        "municipio": municipio,
                        "asunto": f"Corrección de {tipo}: {nombre}",
                        "descripcion": descripcion,
                    })

                    st.success("Gracias. La información ha sido registrada y será revisada por APIT Cantabria.")

                except Exception:
                    mensaje_error_envio()


def formulario_nuevo_recurso():
    with st.expander("Proponer nuevo recurso turístico", expanded=False):
        with st.form("form_nuevo_recurso"):

            guia = st.text_input("Nombre del guía", placeholder="Nombre y apellidos")
            nombre = st.text_input("Nombre del recurso")
            municipio = st.text_input("Municipio")

            descripcion = st.text_area(
                "Información básica",
                placeholder="Indique web oficial, horarios, datos útiles o motivo por el que debería añadirse."
            )

            enviar = st.form_submit_button("Enviar")

            if enviar:
                if not guia.strip():
                    st.warning("Indique su nombre.")
                    return

                if not nombre.strip():
                    st.warning("El nombre del recurso es obligatorio.")
                    return

                try:
                    save_incidencia({
                        "usuario_nombre": guia,
                        "tipo": "recurso",
                        "categoria": "nuevo",
                        "nombre": nombre,
                        "municipio": municipio,
                        "asunto": f"Nuevo recurso turístico: {nombre}",
                        "descripcion": descripcion,
                    })

                    st.success("Gracias. La propuesta ha sido registrada y será revisada por APIT Cantabria.")

                except Exception:
                    mensaje_error_envio()


def formulario_nuevo_restaurante():
    with st.expander("Proponer nuevo restaurante", expanded=False):
        with st.form("form_nuevo_restaurante"):

            guia = st.text_input("Nombre del guía", placeholder="Nombre y apellidos")
            nombre = st.text_input("Nombre del restaurante")
            municipio = st.text_input("Municipio")

            descripcion = st.text_area(
                "Información básica",
                placeholder="Indique si admite grupos, precio aproximado, experiencia con grupos o cualquier dato útil."
            )

            enviar = st.form_submit_button("Enviar")

            if enviar:
                if not guia.strip():
                    st.warning("Indique su nombre.")
                    return

                if not nombre.strip():
                    st.warning("El nombre del restaurante es obligatorio.")
                    return

                try:
                    save_incidencia({
                        "usuario_nombre": guia,
                        "tipo": "restaurante",
                        "categoria": "nuevo",
                        "nombre": nombre,
                        "municipio": municipio,
                        "asunto": f"Nuevo restaurante: {nombre}",
                        "descripcion": descripcion,
                    })

                    st.success("Gracias. La propuesta ha sido registrada y será revisada por APIT Cantabria.")

                except Exception:
                    mensaje_error_envio()


def formulario_nueva_resena_restaurante(
    nombre,
    municipio="",
    item_key="",
    restaurante_id="",
):
    key_parts = [municipio, nombre, item_key]
    form_key = "form_resena_" + "_".join(
        safe_key(part) for part in key_parts if str(part).strip()
    )

    with st.expander("Añadir reseña", expanded=False):
        with st.form(form_key):

            guia = st.text_input(
                "Nombre del guía",
                placeholder="Nombre y apellidos",
                key=f"guia_{form_key}",
            )

            fecha_visita = st.date_input(
                "Fecha",
                value=date.today(),
                format="DD/MM/YYYY",
                key=f"fecha_{form_key}",
            )

            n_personas = st.number_input(
                "Personas",
                min_value=1,
                step=1,
                key=f"personas_{form_key}",
            )

            precio = st.text_input(
                "Precio por persona",
                placeholder="Ejemplo: 22",
                key=f"precio_{form_key}",
            )

            valoracion = st.selectbox(
                "Valoración",
                [
                    "Seleccione...",
                    "⭐",
                    "⭐⭐",
                    "⭐⭐⭐",
                    "⭐⭐⭐⭐",
                    "⭐⭐⭐⭐⭐",
                ],
                key=f"rating_{form_key}",
            )

            comentario = st.text_area(
                "Comentario",
                placeholder="Breve valoración de la experiencia.",
                key=f"comentario_{form_key}",
            )

            enviar = st.form_submit_button("Guardar reseña")

            if enviar:
                if not guia.strip():
                    st.warning("Indique su nombre.")
                    return

                if valoracion == "Seleccione...":
                    st.warning("Seleccione una valoración.")
                    return

                if not comentario.strip():
                    st.warning("El comentario es obligatorio.")
                    return

                try:
                    save_resena_restaurante({
                        "restaurante_id": restaurante_id,
                        "restaurante": nombre,
                        "fecha": fecha_visita.strftime("%d/%m/%Y"),
                        "guia": guia,
                        "num_personas": int(n_personas),
                        "precio_por_persona": precio,
                        "rating": len(valoracion),
                        "comentario": comentario,
                    })

                    st.success("Gracias. La reseña ha sido registrada.")
                    st.cache_data.clear()

                except Exception:
                    mensaje_error_envio()

# ─────────────────────────────────────────────
# MÓDULO RECURSOS
# ─────────────────────────────────────────────

def modulo_recursos(dfs):
    recursos_df = dfs["recursos"]
    contenidos_df = dfs["contenidos_recursos"]

    hoy = date.today()
    fecha_max = add_years_safe(hoy, 2)

    col_fecha, col_muni = st.columns([1, 1])

    with col_fecha:
        fecha_sel = st.date_input(
            "Consultar fecha",
            value=hoy,
            min_value=hoy,
            max_value=fecha_max,
            format="DD/MM/YYYY",
            key="rec_fecha",
        )

    with col_muni:
        municipios = [SELECT_MUNICIPIO, TODOS_MUNICIPIOS] + sorted(
            recursos_df["municipio"].dropna().unique()
        )
        muni = st.selectbox("Municipio", municipios, key="rec_muni")

    if muni == SELECT_MUNICIPIO:
        st.markdown(
            '<div class="no-results">Seleccione un municipio para consultar los recursos disponibles.</div>',
            unsafe_allow_html=True,
        )
        return

    df_fil = recursos_df.copy()

    if "activo" in df_fil.columns:
        df_fil = df_fil[df_fil["activo"] == True]

    if muni != TODOS_MUNICIPIOS:
        df_fil = df_fil[df_fil["municipio"] == muni]

    if df_fil.empty:
        mensaje = (
            "No hay recursos registrados."
            if muni == TODOS_MUNICIPIOS
            else "No hay recursos registrados para el municipio seleccionado."
        )
        st.markdown(f'<div class="no-results">{mensaje}</div>', unsafe_allow_html=True)
        return

    recursos = [TODOS_RECURSOS] + sorted(df_fil["recurso"].dropna().unique())
    recurso_sel = st.selectbox("Recurso", recursos, key="rec_recurso")

    formulario_nuevo_recurso()

    if recurso_sel != TODOS_RECURSOS:
        df_fil = df_fil[df_fil["recurso"] == recurso_sel]

    if "prioridad" in df_fil.columns:
        df_fil = df_fil.sort_values(["prioridad", "recurso"])
    else:
        df_fil = df_fil.sort_values("recurso")

    if df_fil.empty:
        st.markdown(
            '<div class="no-results">No hay información para el recurso seleccionado.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(f"**{len(df_fil)} recurso(s) encontrado(s)**")

    for idx, rec in df_fil.iterrows():
        nombre = rec["recurso"]
        recurso_id = rec.get("recurso_id", "")
        municipio = rec.get("municipio", "")
        tipo_rec = rec.get("tipo", "")
        web = rec.get("web_oficial", "")
        ultima_act = rec.get("ultima_actualizacion", None)

        contenido_fecha = filtrar_contenido(
            contenidos_df,
            nombre,
            fecha_sel,
            recurso_id,
        )

        bloques_html = build_bloques_contenido(contenido_fecha)

        render_html(f"""
        <div class="card">
            <div class="card-title">🏛️ {esc(nombre)}</div>
            <div>
                <span class="badge">{esc(municipio)}</span>
                <span class="badge badge-amber">{esc(tipo_rec)}</span>
            </div>
            {bloques_html}
            {build_disclaimer(web, ultima_act)}
        </div>
        """)

        formulario_incidencia(
            tipo="recurso",
            categoria="correccion",
            nombre=nombre,
            municipio=municipio,
            item_key=idx,
            entidad_id=recurso_id,
        )


# ─────────────────────────────────────────────
# MÓDULO RESTAURANTES
# ─────────────────────────────────────────────

def modulo_restaurantes(dfs):
    rest_df = dfs["restaurantes"]
    exp_df = dfs["experiencias_restaurantes"]

    rest_df = attach_restaurant_ratings(rest_df, exp_df)

    municipios = [SELECT_MUNICIPIO, TODOS_MUNICIPIOS] + sorted(
        rest_df["municipio"].dropna().unique()
    )

    muni = st.selectbox("Municipio", municipios, key="rest_muni")

    formulario_nuevo_restaurante()

    if muni == SELECT_MUNICIPIO:
        st.info("Seleccione un municipio para consultar los restaurantes disponibles.")
        return

    df_fil = rest_df.copy()

    if muni != TODOS_MUNICIPIOS:
        df_fil = df_fil[df_fil["municipio"] == muni]

    df_fil = df_fil.sort_values(
        "rating_medio",
        ascending=False,
        na_position="last",
    )

    if df_fil.empty:
        if muni == TODOS_MUNICIPIOS:
            st.info("No hay restaurantes registrados.")
        else:
            st.info("No hay restaurantes registrados para el municipio seleccionado.")
        return

    st.markdown(f"**{len(df_fil)} restaurante(s) encontrado(s)**")

    for _, row in df_fil.iterrows():
        nombre = row["restaurante"]
        restaurante_id = row.get("restaurante_id", "")
        municipio = row.get("municipio", "")
        grupos = row.get("admite_grupos", "")
        precio = row.get("precio_menu_grupos", None)
        rating = row.get("rating_medio", None)
        n_res = int(row.get("n_resenas", 0)) if pd.notna(row.get("n_resenas")) else 0

        etiquetas_html = f'<span class="badge">{esc(municipio)}</span>'

        if str(grupos).strip().upper() in ["SÍ", "SI", "YES", "TRUE", "VERDADERO"]:
            etiquetas_html += '<span class="badge badge-green">Admite grupos</span>'

        if pd.notna(precio) and str(precio).strip():
            etiquetas_html += f'<span class="badge badge-amber">Menú grupo: {esc(precio)} €/p.</span>'

        if pd.notna(rating):
            estrellas = normalize_rating(rating)
            stars_str = "⭐" * estrellas + "☆" * (5 - estrellas)
            rating_html = (
                '<div class="bloque">'
                '<div class="bloque-label">Valoración media</div>'
                f'<div class="bloque-contenido">{esc(stars_str)} {rating:.1f}/5 '
                f'({n_res} reseña(s))</div>'
                '</div>'
            )
        else:
            rating_html = (
                '<div class="bloque">'
                '<div class="bloque-label">Valoración media</div>'
                '<div class="bloque-contenido">Sin reseñas aún</div>'
                '</div>'
            )

        resenas = related_rows(
            exp_df,
            id_column="restaurante_id",
            entity_id=restaurante_id,
            name_column="restaurante",
            entity_name=nombre,
        )

        if "fecha" in resenas.columns:
            resenas["fecha"] = pd.to_datetime(resenas["fecha"], errors="coerce")
            resenas = resenas.sort_values("fecha", ascending=False)

        if resenas.empty:
            resenas_html = (
                '<div class="reviews-title">Experiencias</div>'
                '<small style="color:#6b7280">Sin reseñas registradas.</small>'
            )
        else:
            resenas_html = '<div class="reviews-title">Últimas experiencias</div>'

            for _, res in resenas.head(3).iterrows():
                fecha_str = (
                    pd.to_datetime(res["fecha"]).strftime("%d/%m/%Y")
                    if pd.notna(res.get("fecha"))
                    else ""
                )

                r_stars = "⭐" * normalize_rating(res.get("rating", 0))
                resenas_html += build_resena(
                    r_stars,
                    res.get("guia", ""),
                    fecha_str,
                    res.get("num_personas", ""),
                    res.get("comentario", ""),
                )

        render_html(f"""
        <div class="card">
            <div class="card-title">🍽️ {esc(nombre)}</div>
            <div>{etiquetas_html}</div>
            {rating_html}
            {resenas_html}
        </div>
        """)

        formulario_incidencia(
            tipo="restaurante",
            categoria="correccion",
            nombre=nombre,
            municipio=municipio,
            item_key=row.name,
            entidad_id=restaurante_id,
        )

        formulario_nueva_resena_restaurante(
            nombre=nombre,
            municipio=municipio,
            item_key=row.name,
            restaurante_id=restaurante_id,
        )

# ─────────────────────────────────────────────
# APP PRINCIPAL
# ─────────────────────────────────────────────

def render_header():
    st.markdown('<div class="app-header">', unsafe_allow_html=True)
    st.image("logo_apit.png", width=92)
    st.markdown(
        """
        <h1 class="app-title">Una base de datos<br>de guías para guías</h1>
        <p class="app-meta">Recursos turísticos · Restaurantes · Experiencias</p>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Actualizar datos", key="refresh_header"):
        st.cache_data.clear()
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def main():
    inject_css()
    render_header()

    try:
        with st.spinner("Cargando datos…"):
            load_result = load_data()
            
    except Exception:
        logger.exception("Fallo inesperado durante la carga de datos")
        st.error(
            "No ha sido posible cargar la información. "
            "Inténtelo de nuevo más tarde o contacte con APIT Cantabria."
        )
        return

    dfs = load_result.frames
    if load_result.warnings:
        for warning in load_result.warnings:
            logger.warning(warning)

    tab_rec, tab_rest = st.tabs(["Recursos", "Restaurantes"])

    with tab_rec:
        st.markdown(
            '<div class="section-header">Recursos Turísticos</div>',
            unsafe_allow_html=True,
        )
        missing = {"recursos", "contenidos_recursos"} - set(dfs)
        if missing:
            st.error(
                "No se puede mostrar esta sección porque no se han podido "
                f"cargar estas hojas: {', '.join(sorted(missing))}."
            )
        else:
            modulo_recursos(dfs)

    with tab_rest:
        st.markdown(
            '<div class="section-header">Restaurantes</div>',
            unsafe_allow_html=True,
        )
        missing = {"restaurantes", "experiencias_restaurantes"} - set(dfs)
        if missing:
            st.error(
                "No se puede mostrar esta sección porque no se han podido "
                f"cargar estas hojas: {', '.join(sorted(missing))}."
            )
        else:
            modulo_restaurantes(dfs)

    st.markdown(
        '<div style="text-align:center;color:#9ca3af;'
        'font-size:0.72rem;margin-top:2rem;padding-bottom:1rem;">'
        'GuíaHub · Información para uso profesional interno'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
