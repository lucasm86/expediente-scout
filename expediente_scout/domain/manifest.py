"""Funciones para crear, guardar y cargar manifest.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Actuacion, Captura, Documento, EstadoAnalisis, Expediente, Manifest


def calcular_sha256(path: Path) -> str:
    """Calcula sha256 de un archivo."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def crear_id_documento(hash_sha256: str) -> str:
    """Crea ID estable de documento desde hash."""
    if len(hash_sha256) < 8:
        raise ValueError("hash_sha256 demasiado corto")
    return f"doc-{hash_sha256[:8]}"


def crear_id_actuacion(orden: int) -> str:
    """Crea ID estable de actuación desde orden."""
    if orden < 1:
        raise ValueError("orden debe ser positivo")
    return f"act-{orden:04d}"


def crear_manifest(
    expediente: Expediente,
    actuaciones: list[Actuacion],
    documentos: list[Documento],
    capturas: list[Captura] | None = None,
    estado_analisis: EstadoAnalisis | None = None,
) -> Manifest:
    """Construye un Manifest v1.0."""
    return Manifest(
        schema_version="1.0",
        expediente=expediente,
        capturas=capturas or [],
        actuaciones=actuaciones,
        documentos=documentos,
        estado_analisis=estado_analisis or EstadoAnalisis(),
    )


def guardar_manifest(manifest: Manifest, ruta: Path) -> None:
    """Guarda manifest como JSON estable."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    data = manifest.model_dump(mode="json")
    ruta.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def cargar_manifest(ruta: Path) -> Manifest:
    """Carga y valida manifest.json."""
    data = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return Manifest.model_validate(data)
