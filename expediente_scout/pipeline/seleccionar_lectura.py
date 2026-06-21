from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class ResultadoSeleccionLectura:
    clasificacion_path: Path
    output_path: Path
    total_actuaciones: int
    total_seleccionadas: int
    total_accesorias: int


def cargar_clasificacion_playbook(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe clasificación playbook: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("La clasificación debe ser un objeto JSON.")

    if not isinstance(data.get("actuaciones"), list):
        raise ValueError("La clasificación debe incluir una lista 'actuaciones'.")

    return data


def seleccionar_lectura_desde_clasificacion(
    clasificacion: dict[str, Any],
) -> dict[str, Any]:
    actuaciones = clasificacion["actuaciones"]

    seleccionadas: list[dict[str, Any]] = []
    accesorias: list[dict[str, Any]] = []

    for item in actuaciones:
        if not isinstance(item, dict):
            continue

        base = {
            "orden": item.get("orden"),
            "fecha": item.get("fecha"),
            "descripcion": item.get("descripcion"),
            "archivo": item.get("archivo"),
            "sha256": item.get("sha256"),
            "hitos_detectados": item.get("hitos_detectados", []),
            "relevancia": item.get("relevancia"),
            "leer_completo": bool(item.get("leer_completo")),
            "motivo": item.get("motivo"),
        }

        debe_leerse = (
            bool(item.get("leer_completo"))
            or item.get("relevancia") == "alta"
            or bool(item.get("hitos_detectados"))
        )

        if debe_leerse:
            seleccionadas.append(
                {
                    **base,
                    "razon_seleccion": _razon_seleccion(item),
                }
            )
        else:
            accesorias.append(
                {
                    **base,
                    "razon_omision": _razon_omision(item),
                }
            )

    return {
        "playbook_id": clasificacion.get("playbook_id"),
        "total_actuaciones": len(actuaciones),
        "total_seleccionadas": len(seleccionadas),
        "total_accesorias": len(accesorias),
        "criterio": {
            "seleccionar_si": [
                "leer_completo = true",
                "relevancia = alta",
                "existen hitos_detectados",
            ],
            "omitir_si": [
                "sin hito detectado",
                "leer_completo = false",
                "relevancia accesoria o baja",
            ],
        },
        "seleccionadas": seleccionadas,
        "accesorias": accesorias,
    }


def _razon_seleccion(item: dict[str, Any]) -> str:
    razones: list[str] = []

    if item.get("leer_completo"):
        razones.append("marcada para lectura completa por el playbook")

    if item.get("relevancia") == "alta":
        razones.append("relevancia alta")

    hitos = item.get("hitos_detectados") or []
    if hitos:
        razones.append("vinculada a hito procesal: " + ", ".join(map(str, hitos)))

    return "; ".join(razones) if razones else "seleccionada por criterio general"


def _razon_omision(item: dict[str, Any]) -> str:
    if not item.get("hitos_detectados"):
        return "sin coincidencias con hitos procesales del playbook"

    if item.get("relevancia") in {"accesoria", "baja"}:
        return "relevancia baja o accesoria"

    return "no cumple criterio de lectura completa"


def generar_plan_lectura(
    *,
    clasificacion_path: Path,
    output_path: Path,
) -> ResultadoSeleccionLectura:
    clasificacion = cargar_clasificacion_playbook(clasificacion_path)
    plan = seleccionar_lectura_desde_clasificacion(clasificacion)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ResultadoSeleccionLectura(
        clasificacion_path=clasificacion_path,
        output_path=output_path,
        total_actuaciones=int(plan["total_actuaciones"]),
        total_seleccionadas=int(plan["total_seleccionadas"]),
        total_accesorias=int(plan["total_accesorias"]),
    )
