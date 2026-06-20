"""Detección de novedades entre una captura y el manifest local."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from expediente_scout.domain.manifest import calcular_sha256, cargar_manifest, crear_id_actuacion, crear_id_documento
from expediente_scout.domain.models import Documento, Manifest
from expediente_scout.domain.paths import crear_estructura
from expediente_scout.ingesta.fuente_captura import FuenteCaptura, ItemIndice


@dataclass(frozen=True)
class NovedadItem:
    orden: int
    fecha: str | None
    descripcion: str
    archivo: str
    actuacion_id: str
    documento_id: str


@dataclass(frozen=True)
class ResumenNovedades:
    manifest_existe: bool
    actuaciones_nuevas: list[NovedadItem] = field(default_factory=list)
    documentos_nuevos: list[NovedadItem] = field(default_factory=list)

    @property
    def total_actuaciones_nuevas(self) -> int:
        return len(self.actuaciones_nuevas)

    @property
    def total_documentos_nuevos(self) -> int:
        return len(self.documentos_nuevos)


def _doc_id_para_item(
    item: ItemIndice,
    act_id: str,
    hash_sha256: str,
    documentos_por_id: dict[str, Documento],
) -> str:
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

    stem_seguro = Path(item.archivo).stem.replace(" ", "_")[:32]
    return f"{base_id}-{stem_seguro}"


def _item_novedad(item: ItemIndice, act_id: str, doc_id: str) -> NovedadItem:
    return NovedadItem(
        orden=item.orden,
        fecha=item.fecha.isoformat() if item.fecha else None,
        descripcion=item.descripcion,
        archivo=item.archivo,
        actuacion_id=act_id,
        documento_id=doc_id,
    )


def detectar_novedades_captura(
    root: Path,
    jurisdiccion: str,
    numero: str,
    anio: int,
    fuente: FuenteCaptura,
) -> ResumenNovedades:
    """Compara una captura con el manifest local sin modificar archivos."""
    expediente_dir = crear_estructura(root, jurisdiccion, numero, anio)
    manifest_path = expediente_dir / "manifest.json"

    if manifest_path.exists():
        manifest: Manifest | None = cargar_manifest(manifest_path)
    else:
        manifest = None

    actuaciones_existentes = {act.id for act in manifest.actuaciones} if manifest else set()
    documentos_por_id = {doc.id: doc for doc in manifest.documentos} if manifest else {}

    actuaciones_nuevas: list[NovedadItem] = []
    documentos_nuevos: list[NovedadItem] = []

    for item in sorted(fuente.leer_indice(), key=lambda i: i.orden):
        origen = fuente.ruta_raw() / item.archivo
        if not origen.exists():
            raise FileNotFoundError(f"PDF no encontrado en captura: {origen}")

        act_id = crear_id_actuacion(item.orden)
        hash_sha256 = calcular_sha256(origen)
        doc_id = _doc_id_para_item(item, act_id, hash_sha256, documentos_por_id)
        novedad = _item_novedad(item, act_id, doc_id)

        if act_id not in actuaciones_existentes:
            actuaciones_nuevas.append(novedad)
        if doc_id not in documentos_por_id:
            documentos_nuevos.append(novedad)

    return ResumenNovedades(
        manifest_existe=manifest is not None,
        actuaciones_nuevas=actuaciones_nuevas,
        documentos_nuevos=documentos_nuevos,
    )
