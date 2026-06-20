"""Ingesta básica e idempotente de capturas locales."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from expediente_scout.domain.enums import EstadoDescarga
from expediente_scout.domain.manifest import (
    calcular_sha256,
    cargar_manifest,
    crear_id_actuacion,
    crear_id_documento,
    guardar_manifest,
)
from expediente_scout.domain.models import Actuacion, Captura, Documento, EstadoAnalisis, Expediente, Manifest
from expediente_scout.domain.paths import crear_estructura
from expediente_scout.ingesta.fuente_captura import FuenteCaptura, ItemIndice

_BACKSLASH = chr(92)


def _expediente_id(jurisdiccion: str, numero: str, anio: int) -> str:
    return f"{jurisdiccion}-{numero}-{anio}"


def _validar_nombre_archivo(nombre: str) -> None:
    path = Path(nombre)
    if path.name != nombre or ".." in path.parts or "/" in nombre or _BACKSLASH in nombre:
        raise ValueError(f"Nombre de archivo inseguro en índice: {nombre}")


def _manifest_vacio(jurisdiccion: str, numero: str, anio: int, fuente_id: str) -> Manifest:
    expediente = Expediente(
        id=_expediente_id(jurisdiccion, numero, anio),
        jurisdiccion=jurisdiccion,
        numero=numero,
        anio=anio,
        fuente=fuente_id,
    )
    return Manifest(
        expediente=expediente,
        capturas=[],
        actuaciones=[],
        documentos=[],
        estado_analisis=EstadoAnalisis(),
    )


def _copiar_si_cambio(origen: Path, destino: Path, hash_origen: str) -> bool:
    if destino.exists() and calcular_sha256(destino) == hash_origen:
        return False
    shutil.copy2(origen, destino)
    return True


def _crear_documento_desde_item(item: ItemIndice, doc_id: str, hash_sha256: str, act_id: str) -> Documento:
    return Documento(
        id=doc_id,
        nombre_archivo=item.archivo,
        ruta_raw=f"raw/{item.archivo}",
        fecha=item.fecha,
        hash_sha256=hash_sha256,
        estado_descarga=EstadoDescarga.COMPLETO,
        actuacion_id=act_id,
    )


def _doc_id_para_item(
    item: ItemIndice,
    act_id: str,
    hash_sha256: str,
    documentos_por_id: dict[str, Documento],
) -> str:
    """Devuelve un ID estable; conserva duplicados exactos como documentos separados."""
    base_id = crear_id_documento(hash_sha256)
    existente = documentos_por_id.get(base_id)
    if existente is None:
        return base_id
    if existente.nombre_archivo == item.archivo and existente.actuacion_id == act_id:
        return base_id

    candidato = f"{base_id}-act-{item.orden:04d}"
    existente_candidato = documentos_por_id.get(candidato)
    if existente_candidato is None:
        return candidato
    if existente_candidato.nombre_archivo == item.archivo and existente_candidato.actuacion_id == act_id:
        return candidato

    # Caso extremo: misma actuación con más de un archivo idéntico. Estable por nombre.
    stem_seguro = Path(item.archivo).stem.replace(" ", "_")[:32]
    return f"{base_id}-{stem_seguro}"


def ingerir_captura(
    root: Path,
    jurisdiccion: str,
    numero: str,
    anio: int,
    fuente: FuenteCaptura,
) -> Path:
    """Ingiere PDFs + índice y actualiza manifest sin duplicar actuaciones/documentos."""
    expediente_dir = crear_estructura(root, jurisdiccion, numero, anio)
    raw_dir = expediente_dir / "raw"
    manifest_path = expediente_dir / "manifest.json"

    if manifest_path.exists():
        manifest = cargar_manifest(manifest_path)
    else:
        manifest = _manifest_vacio(jurisdiccion, numero, anio, fuente.fuente_id)

    actuaciones_por_id = {act.id: act for act in manifest.actuaciones}
    documentos_por_id = {doc.id: doc for doc in manifest.documentos}

    nuevas_actuaciones = 0
    nuevos_documentos = 0
    hubo_cambios = False

    for item in sorted(fuente.leer_indice(), key=lambda i: i.orden):
        _validar_nombre_archivo(item.archivo)
        origen = fuente.ruta_raw() / item.archivo
        if not origen.exists():
            raise FileNotFoundError(f"PDF no encontrado en captura: {origen}")

        hash_sha256 = calcular_sha256(origen)
        act_id = crear_id_actuacion(item.orden)
        doc_id = _doc_id_para_item(item, act_id, hash_sha256, documentos_por_id)
        destino = raw_dir / item.archivo

        if _copiar_si_cambio(origen, destino, hash_sha256):
            hubo_cambios = True

        actuacion = actuaciones_por_id.get(act_id)
        if actuacion is None:
            actuacion = Actuacion(
                id=act_id,
                orden=item.orden,
                fecha=item.fecha,
                descripcion=item.descripcion,
                fuente_ref=f"indice fila {item.orden}",
                documentos=[],
            )
            actuaciones_por_id[act_id] = actuacion
            manifest.actuaciones.append(actuacion)
            nuevas_actuaciones += 1
            hubo_cambios = True

        if doc_id not in documentos_por_id:
            documento = _crear_documento_desde_item(item, doc_id, hash_sha256, act_id)
            documentos_por_id[doc_id] = documento
            manifest.documentos.append(documento)
            nuevos_documentos += 1
            hubo_cambios = True

        if doc_id not in actuacion.documentos:
            actuacion.documentos.append(doc_id)
            hubo_cambios = True

    manifest.actuaciones = sorted(manifest.actuaciones, key=lambda act: act.orden)
    manifest.documentos = sorted(manifest.documentos, key=lambda doc: doc.id)

    if hubo_cambios or not manifest_path.exists():
        if nuevas_actuaciones or nuevos_documentos or not manifest.capturas:
            manifest.capturas.append(
                Captura(
                    captura_id=str(uuid4()),
                    fecha_captura=datetime.now(timezone.utc),
                    adapter=fuente.fuente_id,
                    resultado="ok",
                    actuaciones_nuevas=nuevas_actuaciones,
                    documentos_nuevos=nuevos_documentos,
                    log_ref=None,
                )
            )
        guardar_manifest(manifest, manifest_path)

    return manifest_path


def listar_expedientes(root: Path) -> list[Path]:
    """Devuelve manifests locales bajo data/expedientes."""
    base = root / "data" / "expedientes"
    if not base.exists():
        return []
    return sorted(base.glob("*/*/manifest.json"))


def estado_expediente(root: Path, jurisdiccion: str, numero: str, anio: int) -> dict[str, object]:
    """Devuelve un resumen local del expediente."""
    expediente_dir = root / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}"
    manifest_path = expediente_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No existe manifest: {manifest_path}")

    manifest = cargar_manifest(manifest_path)
    ultima = max(manifest.actuaciones, key=lambda act: act.orden, default=None)
    ultima_txt = "sin actuaciones"
    if ultima is not None:
        fecha = ultima.fecha.isoformat() if ultima.fecha else "sin fecha"
        ultima_txt = f"{fecha} - {ultima.descripcion}"

    return {
        "expediente_id": manifest.expediente.id,
        "manifest_path": str(manifest_path),
        "actuaciones": len(manifest.actuaciones),
        "documentos": len(manifest.documentos),
        "ultima_actuacion": ultima_txt,
    }
