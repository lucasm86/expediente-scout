from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re

import fitz


@dataclass(frozen=True)
class ResultadoExtraccionTextoSeleccionado:
    plan_path: Path
    output_dir: Path
    indice_path: Path
    total_seleccionadas: int
    total_extraidas: int
    total_sin_texto: int
    total_errores: int


def cargar_plan_resuelto(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe plan de lectura resuelto: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("El plan resuelto debe ser un objeto JSON.")

    if not isinstance(data.get("seleccionadas"), list):
        raise ValueError("El plan resuelto debe incluir una lista 'seleccionadas'.")

    return data


def _nombre_texto(item: dict[str, Any]) -> str:
    orden = item.get("orden")
    archivo = str(item.get("archivo") or "documento.pdf")
    stem = Path(archivo).stem

    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_")
    if not stem:
        stem = "documento"

    if isinstance(orden, int):
        return f"{orden:04d}_{stem}.txt"

    return f"{stem}.txt"


def extraer_texto_pdf(pdf_path: Path) -> tuple[int, str]:
    partes: list[str] = []

    with fitz.open(pdf_path) as pdf:
        paginas = pdf.page_count

        for idx, page in enumerate(pdf, start=1):
            texto = page.get_text("text") or ""
            partes.append(f"\n--- Página {idx} ---\n{texto.strip()}\n")

    return paginas, "".join(partes).strip() + "\n"


def extraer_textos_desde_plan(
    plan: dict[str, Any],
    *,
    output_dir: Path,
    strict: bool = True,
) -> dict[str, Any]:
    seleccionadas = plan["seleccionadas"]
    textos_dir = output_dir / "textos_seleccionados"
    textos_dir.mkdir(parents=True, exist_ok=True)

    documentos: list[dict[str, Any]] = []
    errores: list[dict[str, Any]] = []

    for item in seleccionadas:
        if not isinstance(item, dict):
            continue

        pdf_path_raw = item.get("pdf_path")
        pdf_path = Path(str(pdf_path_raw)) if pdf_path_raw else None

        base = {
            "orden": item.get("orden"),
            "fecha": item.get("fecha"),
            "descripcion": item.get("descripcion"),
            "archivo": item.get("archivo"),
            "pdf_path": str(pdf_path) if pdf_path else None,
            "hitos_detectados": item.get("hitos_detectados", []),
            "relevancia": item.get("relevancia"),
            "leer_completo": item.get("leer_completo"),
        }

        if not pdf_path or not pdf_path.exists():
            error = {
                **base,
                "error": "PDF no encontrado",
            }
            errores.append(error)
            documentos.append(
                {
                    **base,
                    "texto_path": None,
                    "paginas": 0,
                    "caracteres": 0,
                    "sin_texto": True,
                    "extraido": False,
                    "error": error["error"],
                }
            )
            if strict:
                raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")
            continue

        try:
            paginas, texto = extraer_texto_pdf(pdf_path)
            texto_path = textos_dir / _nombre_texto(item)
            texto_path.write_text(texto, encoding="utf-8")

            sin_texto = not bool(texto.strip())

            documentos.append(
                {
                    **base,
                    "texto_path": str(texto_path),
                    "paginas": paginas,
                    "caracteres": len(texto),
                    "sin_texto": sin_texto,
                    "extraido": True,
                    "error": None,
                }
            )
        except Exception as exc:
            error = {
                **base,
                "error": str(exc),
            }
            errores.append(error)
            documentos.append(
                {
                    **base,
                    "texto_path": None,
                    "paginas": 0,
                    "caracteres": 0,
                    "sin_texto": True,
                    "extraido": False,
                    "error": str(exc),
                }
            )
            if strict:
                raise

    total_extraidas = sum(1 for d in documentos if d["extraido"])
    total_sin_texto = sum(1 for d in documentos if d["sin_texto"])

    return {
        "playbook_id": plan.get("playbook_id"),
        "total_seleccionadas": len(seleccionadas),
        "total_extraidas": total_extraidas,
        "total_sin_texto": total_sin_texto,
        "total_errores": len(errores),
        "documentos": documentos,
        "errores": errores,
    }


def generar_extraccion_texto(
    *,
    plan_path: Path,
    output_dir: Path,
    strict: bool = True,
) -> ResultadoExtraccionTextoSeleccionado:
    plan = cargar_plan_resuelto(plan_path)
    resultado = extraer_textos_desde_plan(
        plan,
        output_dir=output_dir,
        strict=strict,
    )

    indice_path = output_dir / "extraccion_texto.json"
    indice_path.parent.mkdir(parents=True, exist_ok=True)
    indice_path.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ResultadoExtraccionTextoSeleccionado(
        plan_path=plan_path,
        output_dir=output_dir,
        indice_path=indice_path,
        total_seleccionadas=int(resultado["total_seleccionadas"]),
        total_extraidas=int(resultado["total_extraidas"]),
        total_sin_texto=int(resultado["total_sin_texto"]),
        total_errores=int(resultado["total_errores"]),
    )
