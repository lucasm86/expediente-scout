"""Normalización documental: páginas, texto y duplicados por hash."""

from __future__ import annotations

from pathlib import Path

import fitz

from expediente_scout.domain.enums import Categoria, Relevancia
from expediente_scout.domain.manifest import calcular_sha256, cargar_manifest, guardar_manifest
from expediente_scout.domain.models import Documento


def _expediente_dir(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return Path(root).resolve() / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}"


def _resolver_ruta_segura(base: Path, ruta_relativa: str) -> Path:
    ruta = (base / ruta_relativa).resolve()
    if not ruta.is_relative_to(base.resolve()):
        raise ValueError(f"Ruta fuera del expediente: {ruta_relativa}")
    return ruta


def _leer_pdf(path: Path) -> tuple[int, str]:
    partes: list[str] = []
    with fitz.open(path) as pdf:
        paginas = pdf.page_count
        for idx, page in enumerate(pdf, start=1):
            texto = page.get_text("text") or ""
            partes.append(f"\n--- Página {idx} ---\n{texto.strip()}\n")
    return paginas, "".join(partes).strip() + "\n"


def _orden_documento(doc: Documento) -> tuple[str, str]:
    return (doc.actuacion_id or "", doc.id)


def normalizar_expediente(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    """Actualiza manifest con páginas, texto extraído y duplicados exactos por hash."""
    expediente_dir = _expediente_dir(root, jurisdiccion, numero, anio)
    manifest_path = expediente_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No existe manifest: {manifest_path}")

    text_dir = expediente_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)

    manifest = cargar_manifest(manifest_path)
    primer_doc_por_hash: dict[str, str] = {}

    for documento in sorted(manifest.documentos, key=_orden_documento):
        raw_path = _resolver_ruta_segura(expediente_dir, documento.ruta_raw)
        if not raw_path.exists():
            raise FileNotFoundError(f"No existe PDF raw: {raw_path}")

        hash_actual = calcular_sha256(raw_path)
        paginas, texto = _leer_pdf(raw_path)

        text_path = text_dir / f"{documento.id}.txt"
        text_path.write_text(texto, encoding="utf-8")

        documento.hash_sha256 = hash_actual
        documento.paginas = paginas
        documento.ruta_text = f"text/{documento.id}.txt"

        if hash_actual in primer_doc_por_hash:
            documento.categoria = Categoria.DUPLICADO
            documento.relevancia = Relevancia.DUPLICADO
            documento.duplicado_de = primer_doc_por_hash[hash_actual]
            documento.motivo_relevancia = f"Duplicado exacto de {documento.duplicado_de}"
        else:
            primer_doc_por_hash[hash_actual] = documento.id
            if documento.relevancia == Relevancia.DUPLICADO:
                documento.relevancia = Relevancia.REQUIERE_REVISION
            if documento.categoria == Categoria.DUPLICADO:
                documento.categoria = Categoria.SIN_CLASIFICAR
            documento.duplicado_de = None

    manifest.documentos = sorted(manifest.documentos, key=lambda doc: doc.id)
    guardar_manifest(manifest, manifest_path)
    return manifest_path
