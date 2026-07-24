SHEET_ID = "1J1T4vS736sotTVP9KgdSje0OxlBvFU_7alO4Mwap5YY"

SHEET_NAMES = {
    "recursos": "recursos",
    "contenidos_recursos": "contenidos-recursos",
    "restaurantes": "restaurantes",
    "experiencias_restaurantes": "experiencias_restaurantes",
}

SHEET_URLS = {
    key: (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
        f"?tqx=out:csv&sheet={sheet_name}"
    )
    for key, sheet_name in SHEET_NAMES.items()
}

SHEET_SCHEMAS = {
    "recursos": {
        "required": {"recurso", "municipio"},
        "recommended": {"recurso_id"},
    },
    "contenidos_recursos": {
        "required": {"recurso"},
        "recommended": {"recurso_id", "contenido"},
    },
    "restaurantes": {
        "required": {"restaurante", "municipio"},
        "recommended": {"restaurante_id"},
    },
    "experiencias_restaurantes": {
        "required": {"restaurante"},
        "recommended": {"restaurante_id"},
    },
}

DATE_COLUMNS = {
    "fecha_inicio",
    "fecha_fin",
    "actualizado",
    "ultima_actualizacion",
    "fecha",
}
