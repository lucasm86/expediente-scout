from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import unicodedata

from expediente_scout.playbooks.loader import Playbook


IMPORTANCIA_PESO = {
    "baja": 1,
    "media": 2,
    "alta": 3,
}


@dataclass(frozen=True)
class ClasificacionActuacion:
    orden: int
    fecha: str | None
    descripcion: str
    archivo: str | None
    sha256: str | None
    hitos_detectados: list[str]
    importancia: str
    leer_completo: bool
    relevancia: str
    motivo: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "orden": self.orden,
            "fecha": self.fecha,
            "descripcion": self.descripcion,
            "archivo": self.archivo,
            "sha256": self.sha256,
            "hitos_detectados": self.hitos_detectados,
            "importancia": self.importancia,
            "leer_completo": self.leer_completo,
            "relevancia": self.relevancia,
            "motivo": self.motivo,
        }


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para búsqueda simple: minúsculas, sin tildes, espacios limpios."""
    text = unicodedata.normalize("NFKD", texto or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _mejor_importancia(importancias: list[str]) -> str:
    if not importancias:
        return "baja"

    return max(
        (i for i in importancias if i in IMPORTANCIA_PESO),
        key=lambda i: IMPORTANCIA_PESO[i],
        default="baja",
    )


def _relevancia_desde_importancia(importancia: str, hitos: list[str], leer_completo: bool) -> str:
    if not hitos:
        return "accesoria"

    if importancia == "alta" or leer_completo:
        return "alta"

    if importancia == "media":
        return "media"

    return "baja"


def clasificar_actuacion(
    actuacion: dict[str, Any],
    playbook: Playbook,
) -> ClasificacionActuacion:
    """Clasifica una actuación del índice PJN usando palabras clave del playbook."""
    descripcion = str(actuacion.get("descripcion") or "")
    descripcion_norm = normalizar_texto(descripcion)

    hitos_detectados: list[str] = []
    importancias: list[str] = []
    leer_completo = False
    motivos: list[str] = []

    for hito in playbook.hitos:
        hito_id = str(hito.get("id") or "")
        importancia = str(hito.get("importancia") or "baja").lower()
        keywords = hito.get("buscar_en_descripcion") or []

        if not isinstance(keywords, list):
            keywords = []

        matched_keywords: list[str] = []

        for kw in keywords:
            kw_norm = normalizar_texto(str(kw))
            if kw_norm and kw_norm in descripcion_norm:
                matched_keywords.append(str(kw))

        if matched_keywords:
            hitos_detectados.append(hito_id)
            importancias.append(importancia)
            leer_completo = leer_completo or bool(hito.get("leer_completo"))
            motivos.append(
                f"{hito_id}: coincidió con {', '.join(matched_keywords[:3])}"
            )

    importancia_final = _mejor_importancia(importancias)
    relevancia = _relevancia_desde_importancia(
        importancia_final,
        hitos_detectados,
        leer_completo,
    )

    if not motivos:
        motivos.append("Sin coincidencias con hitos del playbook.")

    return ClasificacionActuacion(
        orden=int(actuacion.get("orden") or 0),
        fecha=actuacion.get("fecha"),
        descripcion=descripcion,
        archivo=actuacion.get("archivo"),
        sha256=actuacion.get("sha256"),
        hitos_detectados=hitos_detectados,
        importancia=importancia_final,
        leer_completo=leer_completo,
        relevancia=relevancia,
        motivo=" | ".join(motivos),
    )


def clasificar_indice(
    indice: list[dict[str, Any]],
    playbook: Playbook,
) -> dict[str, Any]:
    """Clasifica todas las actuaciones de un índice PJN."""
    clasificadas = [
        clasificar_actuacion(actuacion, playbook).to_dict()
        for actuacion in indice
    ]

    hitos_resumen: dict[str, dict[str, Any]] = {}

    for item in clasificadas:
        for hito_id in item["hitos_detectados"]:
            bucket = hitos_resumen.setdefault(
                hito_id,
                {
                    "hito": hito_id,
                    "cantidad": 0,
                    "primer_orden": None,
                    "ultima_fecha": None,
                    "ordenes": [],
                },
            )

            bucket["cantidad"] += 1
            bucket["ordenes"].append(item["orden"])

            if bucket["primer_orden"] is None:
                bucket["primer_orden"] = item["orden"]

            if item.get("fecha"):
                bucket["ultima_fecha"] = item["fecha"]

    return {
        "playbook_id": playbook.id,
        "total_actuaciones": len(indice),
        "total_clasificadas": len(clasificadas),
        "total_con_hito": sum(1 for x in clasificadas if x["hitos_detectados"]),
        "total_leer_completo": sum(1 for x in clasificadas if x["leer_completo"]),
        "hitos_detectados": list(hitos_resumen.values()),
        "actuaciones": clasificadas,
    }
