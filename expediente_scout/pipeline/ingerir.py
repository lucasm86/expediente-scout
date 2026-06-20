"""Pipeline de ingesta básica del Paso 1."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import fitz

from expediente_scout.domain.enums import Categoria, EstadoDescarga, Relevancia
from expediente_scout.domain.manifest import (
    calcular_sha256,
    crear_id_actuacion,
    crear_id_documento,
    crear_manifest,
    guardar_manifest,
)
from expediente_scout.domain.models import Actuacion, Captura, Documento, Expediente
from expediente_scout.domain.paths import crear_estructura
from expediente_scout.ingesta.fuente_captura import FuenteCaptura


def _contar_paginas_pdf(path: Path) -> int:
    with fitz.open(path) as doc:
        return doc.page_count


def ingerir_captura(
    root: Path,
    jurisdiccion: str,
    numero: str,
    anio: int,
    fuente: FuenteCaptura,
) -> Path:
    """Ingiere una carpeta raw + índice y crea manifest.json."""
    expediente_dir = crear_estructura(root, jurisdiccion, numero, anio)
    raw_destino = expediente_dir / "raw"
    actuaciones: list[Actuacion] = []
    documentos: list[Documento] = []

    for item in sorted(fuente.leer_indice(), key=lambda x: x.orden):
        origen = fuente.ruta_raw() / item.archivo
        if not origen.is_file():
            raise FileNotFoundError(f"No existe PDF de captura: {origen}")

        destino = raw_destino / Path(item.archivo).name
        shutil.copy2(origen, destino)

        hash_sha256 = calcular_sha256(destino)
        doc_id = crear_id_documento(hash_sha256)
        act_id = crear_id_actuacion(item.orden)

        documento = Documento(
            id=doc_id,
            nombre_archivo=destino.name,
            ruta_raw=str(destino.relative_to(expediente_dir)),
            fecha=item.fecha,
            categoria=Categoria.SIN_CLASIFICAR,
            hash_sha256=hash_sha256,
            paginas=_contar_paginas_pdf(destino),
            estado_descarga=EstadoDescarga.COMPLETO,
            relevancia=Relevancia.REQUIERE_REVISION,
            actuacion_id=act_id,
        )
        actuacion = Actuacion(
            id=act_id,
            orden=item.orden,
            fecha=item.fecha,
            descripcion=item.descripcion,
            tipo_estimado=Categoria.SIN_CLASIFICAR,
            fuente_ref=f"mock índice fila {item.orden}",
            documentos=[doc_id],
        )
        actuaciones.append(actuacion)
        documentos.append(documento)

    expediente = Expediente(
        id=f"{jurisdiccion}-{numero}-{anio}",
        jurisdiccion=jurisdiccion,
        numero=numero,
        anio=anio,
        fuente=fuente.fuente_id,
    )

    captura_id = str(uuid5(NAMESPACE_URL, f"{expediente.id}:{fuente.fuente_id}:paso1"))
    captura = Captura(
        captura_id=captura_id,
        fecha_captura=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
        adapter=fuente.fuente_id,
        resultado="ok",
        actuaciones_nuevas=len(actuaciones),
        documentos_nuevos=len(documentos),
        log_ref=None,
    )

    manifest = crear_manifest(
        expediente=expediente,
        capturas=[captura],
        actuaciones=actuaciones,
        documentos=documentos,
    )
    manifest_path = expediente_dir / "manifest.json"
    guardar_manifest(manifest, manifest_path)
    return manifest_path
