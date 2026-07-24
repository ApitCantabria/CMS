from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


def post_action(url: str, token: str, payload: dict, *, timeout: int = 10) -> dict:
    response = requests.post(
        url,
        json={**payload, "token": token},
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        logger.error("Apps Script rechazó la acción '%s'", payload.get("accion"))
        raise RuntimeError("El servicio de registro rechazó la operación.")
    return result


def incidence_payload(data: dict) -> dict:
    return {
        "accion": "incidencia",
        "usuario_nombre": data["usuario_nombre"].strip(),
        "tipo": data["tipo"],
        "categoria": data["categoria"],
        "nombre": data["nombre"].strip(),
        "entidad_id": str(data.get("entidad_id", "")).strip(),
        "municipio": str(data.get("municipio", "")).strip(),
        "asunto": data["asunto"].strip(),
        "descripcion": data["descripcion"].strip(),
    }


def restaurant_review_payload(data: dict) -> dict:
    return {
        "accion": "nueva_resena_restaurante",
        "restaurante_id": str(data.get("restaurante_id", "")).strip(),
        "restaurante": data["restaurante"].strip(),
        "fecha": data["fecha"],
        "guia": data["guia"].strip(),
        "num_personas": int(data["num_personas"]),
        "precio_por_persona": str(data["precio_por_persona"]).strip(),
        "rating": int(data["rating"]),
        "comentario": data["comentario"].strip(),
    }
