from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re


ORDEN_HITOS_PRIORITARIO = [
    "ejecucion_sentencia",
    "honorarios",
    "apelacion",
    "camara",
    "sentencia",
    "autos_para_sentencia",
    "alegatos",
    "certificacion_prueba",
    "apertura_prueba",
    "prueba_producida",
    "traslado_contestacion",
    "contestacion_demanda",
    "litis_integrada",
    "traslado_demanda",
    "demanda_interpuesta",
]


@dataclass(frozen=True)
class ResultadoPaqueteAnalisis:
    extraccion_path: Path
    output_dir: Path
    indice_path: Path
    mapa_path: Path
    total_documentos: int
    total_bloques: int
    total_caracteres: int


def cargar_extraccion_texto(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe índice de extracción de texto: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("La extracción debe ser un objeto JSON.")

    if not isinstance(data.get("documentos"), list):
        raise ValueError("La extracción debe incluir una lista 'documentos'.")

    return data


def _slug(texto: str) -> str:
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9áéíóúñü._-]+", "_", texto)
    texto = texto.strip("_")
    return texto or "bloque"


def _leer_texto_doc(doc: dict[str, Any]) -> str:
    texto_path = doc.get("texto_path")
    if not texto_path:
        return ""

    path = Path(str(texto_path))
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8")


def _hitos_presentes(documentos: list[dict[str, Any]]) -> list[str]:
    vistos: set[str] = set()

    for doc in documentos:
        for hito in doc.get("hitos_detectados") or []:
            vistos.add(str(hito))

    ordenados = [h for h in ORDEN_HITOS_PRIORITARIO if h in vistos]
    extras = sorted(vistos - set(ordenados))
    return ordenados + extras


def _docs_por_hito(documentos: list[dict[str, Any]], hito: str) -> list[dict[str, Any]]:
    docs = [
        d for d in documentos
        if hito in [str(x) for x in (d.get("hitos_detectados") or [])]
    ]

    return sorted(docs, key=lambda d: int(d.get("orden") or 0))


def _frontmatter_doc(doc: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Orden: {doc.get('orden')}",
            f"Fecha: {doc.get('fecha')}",
            f"Archivo: {doc.get('archivo')}",
            f"PDF: {doc.get('pdf_path')}",
            f"Texto: {doc.get('texto_path')}",
            f"Páginas: {doc.get('paginas')}",
            f"Caracteres: {doc.get('caracteres')}",
            f"Hitos: {', '.join(map(str, doc.get('hitos_detectados') or []))}",
            f"Descripción: {doc.get('descripcion')}",
        ]
    )


def _generar_bloque_markdown(hito: str, docs: list[dict[str, Any]]) -> str:
    total_paginas = sum(int(d.get("paginas") or 0) for d in docs)
    total_caracteres = sum(int(d.get("caracteres") or 0) for d in docs)

    partes = [
        f"# Bloque: {hito}",
        "",
        "## Métricas",
        "",
        f"- Documentos: {len(docs)}",
        f"- Páginas: {total_paginas}",
        f"- Caracteres: {total_caracteres}",
        f"- Tokens aproximados: {round(total_caracteres / 4)}",
        "",
        "## Documentos",
        "",
    ]

    for doc in docs:
        texto = _leer_texto_doc(doc)
        partes.extend(
            [
                "---",
                "",
                f"## Documento orden {doc.get('orden')} - {doc.get('fecha')}",
                "",
                "```text",
                _frontmatter_doc(doc),
                "```",
                "",
                "### Texto extraído",
                "",
                "```text",
                texto.strip(),
                "```",
                "",
            ]
        )

    return "\n".join(partes).strip() + "\n"


def _generar_mapa_general(
    *,
    documentos: list[dict[str, Any]],
    bloques: list[dict[str, Any]],
    extraccion_path: Path,
) -> str:
    total_paginas = sum(int(d.get("paginas") or 0) for d in documentos)
    total_caracteres = sum(int(d.get("caracteres") or 0) for d in documentos)

    partes = [
        "# Mapa general del paquete de análisis",
        "",
        "## Fuente",
        "",
        f"- Extracción: {extraccion_path}",
        f"- Documentos seleccionados: {len(documentos)}",
        f"- Páginas totales: {total_paginas}",
        f"- Caracteres totales: {total_caracteres}",
        f"- Tokens aproximados: {round(total_caracteres / 4)}",
        "",
        "## Bloques por hito",
        "",
    ]

    for bloque in bloques:
        partes.append(
            f"- `{bloque['hito']}`: {bloque['documentos']} documentos, "
            f"{bloque['paginas']} páginas, {bloque['caracteres']} caracteres, "
            f"archivo `{bloque['archivo']}`"
        )

    partes.extend(
        [
            "",
            "## Documentos en orden de actuación",
            "",
        ]
    )

    for doc in sorted(documentos, key=lambda d: int(d.get("orden") or 0)):
        partes.append(
            f"- Orden {doc.get('orden')} | {doc.get('fecha')} | "
            f"{', '.join(map(str, doc.get('hitos_detectados') or []))} | "
            f"{doc.get('descripcion')} | {doc.get('archivo')}"
        )

    return "\n".join(partes).strip() + "\n"


def generar_paquete_desde_extraccion(
    extraccion: dict[str, Any],
    *,
    extraccion_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    documentos = [
        d for d in extraccion["documentos"]
        if isinstance(d, dict) and d.get("extraido") and not d.get("sin_texto")
    ]

    bloques_dir = output_dir / "bloques"
    bloques_dir.mkdir(parents=True, exist_ok=True)

    bloques: list[dict[str, Any]] = []

    for idx, hito in enumerate(_hitos_presentes(documentos), start=1):
        docs = _docs_por_hito(documentos, hito)
        if not docs:
            continue

        nombre = f"{idx:02d}_{_slug(hito)}.md"
        bloque_path = bloques_dir / nombre
        bloque_md = _generar_bloque_markdown(hito, docs)
        bloque_path.write_text(bloque_md, encoding="utf-8")

        paginas = sum(int(d.get("paginas") or 0) for d in docs)
        caracteres = sum(int(d.get("caracteres") or 0) for d in docs)

        bloques.append(
            {
                "hito": hito,
                "archivo": str(bloque_path),
                "documentos": len(docs),
                "paginas": paginas,
                "caracteres": caracteres,
                "tokens_aprox": round(caracteres / 4),
                "ordenes": [d.get("orden") for d in docs],
            }
        )

    mapa_path = output_dir / "00_mapa_general.md"
    mapa_path.write_text(
        _generar_mapa_general(
            documentos=documentos,
            bloques=bloques,
            extraccion_path=extraccion_path,
        ),
        encoding="utf-8",
    )

    total_caracteres = sum(int(d.get("caracteres") or 0) for d in documentos)

    indice = {
        "playbook_id": extraccion.get("playbook_id"),
        "extraccion_path": str(extraccion_path),
        "output_dir": str(output_dir),
        "mapa_general": str(mapa_path),
        "total_documentos": len(documentos),
        "total_bloques": len(bloques),
        "total_paginas": sum(int(d.get("paginas") or 0) for d in documentos),
        "total_caracteres": total_caracteres,
        "tokens_aprox": round(total_caracteres / 4),
        "bloques": bloques,
    }

    indice_path = output_dir / "indice_paquete.json"
    indice_path.write_text(
        json.dumps(indice, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return indice


def generar_paquete_analisis(
    *,
    extraccion_path: Path,
    output_dir: Path,
) -> ResultadoPaqueteAnalisis:
    extraccion = cargar_extraccion_texto(extraccion_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    indice = generar_paquete_desde_extraccion(
        extraccion,
        extraccion_path=extraccion_path,
        output_dir=output_dir,
    )

    return ResultadoPaqueteAnalisis(
        extraccion_path=extraccion_path,
        output_dir=output_dir,
        indice_path=output_dir / "indice_paquete.json",
        mapa_path=output_dir / "00_mapa_general.md",
        total_documentos=int(indice["total_documentos"]),
        total_bloques=int(indice["total_bloques"]),
        total_caracteres=int(indice["total_caracteres"]),
    )
