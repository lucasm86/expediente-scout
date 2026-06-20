"""Curaduría por reglas: categoría, relevancia y selección de documentos."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from expediente_scout.domain.enums import Categoria, Relevancia
from expediente_scout.domain.manifest import cargar_manifest, guardar_manifest
from expediente_scout.domain.models import Actuacion, Documento


@dataclass(frozen=True)
class Clasificacion:
    categoria: Categoria
    relevancia: Relevancia
    motivo: str
    seleccionar: bool


@dataclass(frozen=True)
class ResultadoCuraduria:
    manifest_path: Path
    documentos_curados: int
    seleccionados: int
    alta: int
    media: int
    baja: int
    requiere_revision: int
    duplicados: int


def _expediente_dir(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return Path(root).resolve() / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}"


def _resolver_ruta_segura(base: Path, ruta_relativa: str) -> Path:
    ruta = (base / ruta_relativa).resolve()
    if not ruta.is_relative_to(base.resolve()):
        raise ValueError(f"Ruta fuera del expediente: {ruta_relativa}")
    return ruta


def _normalizar(texto: str) -> str:
    return texto.casefold()


def clasificar_documento(documento: Documento, actuacion: Actuacion | None, texto: str = "") -> Clasificacion:
    """Clasifica un documento con reglas conservadoras y auditables."""
    if documento.relevancia == Relevancia.DUPLICADO or documento.categoria == Categoria.DUPLICADO or documento.duplicado_de:
        return Clasificacion(
            categoria=Categoria.DUPLICADO,
            relevancia=Relevancia.DUPLICADO,
            motivo=documento.motivo_relevancia or f"Duplicado exacto de {documento.duplicado_de}",
            seleccionar=False,
        )

    descripcion = actuacion.descripcion if actuacion else ""
    corpus = _normalizar("\n".join([documento.nombre_archivo, descripcion, texto]))

    # Orden deliberado: "contestación" debe evaluarse antes que "demanda",
    # porque la frase "contesta demanda" contiene la palabra demanda.
    if any(p in corpus for p in ("contestacion", "contestación", "contesta demanda")):
        return Clasificacion(Categoria.CONTESTACION, Relevancia.ALTA, "Contestación de demanda: pieza estructural", True)

    if any(p in corpus for p in ("demanda.pdf", "presenta demanda", " demanda\n", "demanda ")):
        return Clasificacion(Categoria.DEMANDA, Relevancia.ALTA, "Demanda: pieza estructural", True)

    if any(p in corpus for p in ("pericia", "pericial")):
        return Clasificacion(Categoria.PERICIA, Relevancia.ALTA, "Pericia: prueba técnica relevante", True)

    if any(p in corpus for p in ("interlocutoria", "resolución interlocutoria", "resolucion interlocutoria")):
        return Clasificacion(Categoria.INTERLOCUTORIA, Relevancia.ALTA, "Resolución interlocutoria", True)

    if any(p in corpus for p in ("documental", "documentación", "documentacion")):
        return Clasificacion(Categoria.DOCUMENTAL, Relevancia.MEDIA, "Documental acompañada", True)

    if any(p in corpus for p in ("proveido", "proveído", "provee traslado", "provee intimación", "provee intimacion")):
        return Clasificacion(Categoria.PROVEIDO_SIMPLE, Relevancia.MEDIA, "Proveído con posible efecto procesal", True)

    return Clasificacion(
        Categoria.SIN_CLASIFICAR,
        Relevancia.REQUIERE_REVISION,
        "No se detectó una regla confiable; requiere revisión humana",
        False,
    )


def _leer_texto_si_existe(expediente_dir: Path, documento: Documento) -> str:
    if not documento.ruta_text:
        return ""
    text_path = _resolver_ruta_segura(expediente_dir, documento.ruta_text)
    if not text_path.exists():
        return ""
    return text_path.read_text(encoding="utf-8", errors="replace")


def _limpiar_selected(selected_dir: Path) -> None:
    selected_dir.mkdir(parents=True, exist_ok=True)
    for item in selected_dir.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()


def curar_expediente(root: Path, jurisdiccion: str, numero: str, anio: int) -> ResultadoCuraduria:
    """Clasifica documentos por reglas y copia los relevantes a selected/."""
    expediente_dir = _expediente_dir(root, jurisdiccion, numero, anio)
    manifest_path = expediente_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No existe manifest: {manifest_path}")

    manifest = cargar_manifest(manifest_path)
    selected_dir = expediente_dir / "selected"
    _limpiar_selected(selected_dir)

    actuaciones_por_id = {act.id: act for act in manifest.actuaciones}
    seleccionados = 0

    for documento in manifest.documentos:
        actuacion = actuaciones_por_id.get(documento.actuacion_id or "")
        texto = _leer_texto_si_existe(expediente_dir, documento)
        clasificacion = clasificar_documento(documento, actuacion, texto)

        documento.categoria = clasificacion.categoria
        documento.relevancia = clasificacion.relevancia
        documento.motivo_relevancia = clasificacion.motivo
        documento.metodo_clasificacion = "regla"

        if clasificacion.seleccionar:
            raw_path = _resolver_ruta_segura(expediente_dir, documento.ruta_raw)
            if not raw_path.exists():
                raise FileNotFoundError(f"No existe PDF raw: {raw_path}")
            destino = selected_dir / documento.nombre_archivo
            shutil.copy2(raw_path, destino)
            documento.ruta_selected = f"selected/{documento.nombre_archivo}"
            seleccionados += 1
        else:
            documento.ruta_selected = None

    manifest.documentos = sorted(manifest.documentos, key=lambda doc: (doc.actuacion_id or "", doc.id))
    guardar_manifest(manifest, manifest_path)

    return ResultadoCuraduria(
        manifest_path=manifest_path,
        documentos_curados=len(manifest.documentos),
        seleccionados=seleccionados,
        alta=sum(1 for doc in manifest.documentos if doc.relevancia == Relevancia.ALTA),
        media=sum(1 for doc in manifest.documentos if doc.relevancia == Relevancia.MEDIA),
        baja=sum(1 for doc in manifest.documentos if doc.relevancia == Relevancia.BAJA),
        requiere_revision=sum(1 for doc in manifest.documentos if doc.relevancia == Relevancia.REQUIERE_REVISION),
        duplicados=sum(1 for doc in manifest.documentos if doc.relevancia == Relevancia.DUPLICADO),
    )
