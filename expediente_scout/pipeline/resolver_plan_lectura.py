from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class ResultadoPlanLecturaResuelto:
    plan_path: Path
    raw_dir: Path
    output_path: Path
    total_seleccionadas: int
    total_accesorias: int
    total_faltantes: int


def cargar_plan_lectura(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe plan de lectura: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("El plan de lectura debe ser un objeto JSON.")

    if not isinstance(data.get("seleccionadas"), list):
        raise ValueError("El plan de lectura debe incluir una lista 'seleccionadas'.")

    if not isinstance(data.get("accesorias"), list):
        raise ValueError("El plan de lectura debe incluir una lista 'accesorias'.")

    return data


def indexar_pdfs_por_nombre(raw_dir: Path) -> dict[str, Path]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"No existe carpeta raw de PDFs: {raw_dir}")

    if not raw_dir.is_dir():
        raise ValueError(f"La ruta raw no es un directorio: {raw_dir}")

    pdfs = sorted(raw_dir.rglob("*.pdf"))
    indice: dict[str, Path] = {}
    duplicados: dict[str, list[Path]] = {}

    for pdf in pdfs:
        if pdf.name in indice:
            duplicados.setdefault(pdf.name, [indice[pdf.name]]).append(pdf)
        else:
            indice[pdf.name] = pdf

    if duplicados:
        nombres = ", ".join(sorted(duplicados)[:10])
        raise ValueError(f"Hay PDFs duplicados por nombre en raw: {nombres}")

    return indice


def resolver_items(
    items: list[dict[str, Any]],
    *,
    pdfs_por_nombre: dict[str, Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resueltos: list[dict[str, Any]] = []
    faltantes: list[dict[str, Any]] = []

    for item in items:
        archivo = item.get("archivo")

        pdf_path = pdfs_por_nombre.get(str(archivo)) if archivo else None

        item_resuelto = {
            **item,
            "pdf_path": str(pdf_path) if pdf_path else None,
            "pdf_existe": bool(pdf_path and pdf_path.exists()),
        }

        resueltos.append(item_resuelto)

        if not item_resuelto["pdf_existe"]:
            faltantes.append(
                {
                    "orden": item.get("orden"),
                    "fecha": item.get("fecha"),
                    "descripcion": item.get("descripcion"),
                    "archivo": archivo,
                    "motivo": "PDF no encontrado en carpeta raw",
                }
            )

    return resueltos, faltantes


def resolver_plan_lectura(
    plan: dict[str, Any],
    *,
    raw_dir: Path,
) -> dict[str, Any]:
    pdfs_por_nombre = indexar_pdfs_por_nombre(raw_dir)

    seleccionadas_resueltas, faltantes_seleccionadas = resolver_items(
        plan["seleccionadas"],
        pdfs_por_nombre=pdfs_por_nombre,
    )

    accesorias_resueltas, faltantes_accesorias = resolver_items(
        plan["accesorias"],
        pdfs_por_nombre=pdfs_por_nombre,
    )

    faltantes = faltantes_seleccionadas + faltantes_accesorias

    return {
        "playbook_id": plan.get("playbook_id"),
        "raw_dir": str(raw_dir),
        "total_pdfs_raw": len(pdfs_por_nombre),
        "total_actuaciones": plan.get("total_actuaciones"),
        "total_seleccionadas": len(seleccionadas_resueltas),
        "total_accesorias": len(accesorias_resueltas),
        "total_faltantes": len(faltantes),
        "faltantes": faltantes,
        "seleccionadas": seleccionadas_resueltas,
        "accesorias": accesorias_resueltas,
    }


def generar_plan_lectura_resuelto(
    *,
    plan_path: Path,
    raw_dir: Path,
    output_path: Path,
    strict: bool = True,
) -> ResultadoPlanLecturaResuelto:
    plan = cargar_plan_lectura(plan_path)
    resuelto = resolver_plan_lectura(plan, raw_dir=raw_dir)

    if strict and resuelto["total_faltantes"]:
        raise FileNotFoundError(
            f"Hay PDFs faltantes en el plan de lectura: {resuelto['total_faltantes']}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(resuelto, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ResultadoPlanLecturaResuelto(
        plan_path=plan_path,
        raw_dir=raw_dir,
        output_path=output_path,
        total_seleccionadas=int(resuelto["total_seleccionadas"]),
        total_accesorias=int(resuelto["total_accesorias"]),
        total_faltantes=int(resuelto["total_faltantes"]),
    )
