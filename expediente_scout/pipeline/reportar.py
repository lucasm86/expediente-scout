"""Generación de informe Markdown trazable a fuentes internas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from expediente_scout.analisis.contrato import Hallazgo
from expediente_scout.domain.manifest import cargar_manifest, guardar_manifest
from expediente_scout.domain.models import Manifest


@dataclass(frozen=True)
class ResultadoReporte:
    """Resultado de crear el informe Markdown."""

    manifest_path: Path
    analisis_validado_path: Path
    informe_path: Path
    secciones: int
    hallazgos_incluidos: int


SECCIONES: tuple[str, ...] = (
    "Identificación del expediente",
    "Resumen ejecutivo",
    "Cronología de actuaciones",
    "Documentos curados y seleccionados",
    "Hallazgos validados",
    "Etapa procesal estimada",
    "Cargas pendientes",
    "Plazos y vencimientos",
    "Riesgos procesales",
    "Riesgos probatorios",
    "Documental relevante",
    "Novedades detectadas",
    "Información insuficiente / no determinable",
    "Próximos pasos sugeridos",
)

MAPEO_TIPO_SECCION: dict[str, int] = {
    "etapa": 6,
    "etapa_procesal": 6,
    "carga": 7,
    "carga_actora": 7,
    "carga_demandada": 7,
    "plazo": 8,
    "vencimiento": 8,
    "riesgo": 9,
    "riesgo_procesal": 9,
    "riesgo_probatorio": 10,
    "documental": 11,
    "documental_relevante": 11,
    "novedad": 12,
}


def _expediente_dir(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return Path(root).resolve() / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}"


def _cargar_analisis_validado(path: Path) -> tuple[list[Hallazgo], list[dict]]:
    if not path.exists():
        raise FileNotFoundError(f"No existe análisis validado: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validos = [Hallazgo.model_validate(item) for item in data.get("hallazgos_validos", [])]
    descartados = list(data.get("hallazgos_descartados", []))
    return validos, descartados


def _fuentes(hallazgo: Hallazgo) -> str:
    return ", ".join(hallazgo.fuentes)


def _linea_hallazgo(hallazgo: Hallazgo) -> str:
    return f"- {hallazgo.afirmacion} (confianza: {hallazgo.confianza}). Fuentes: {_fuentes(hallazgo)}."


def _hallazgos_por_seccion(hallazgos: list[Hallazgo]) -> dict[int, list[Hallazgo]]:
    por_seccion: dict[int, list[Hallazgo]] = {}
    for hallazgo in hallazgos:
        seccion = MAPEO_TIPO_SECCION.get(hallazgo.tipo, 5)
        por_seccion.setdefault(seccion, []).append(hallazgo)
    return por_seccion


def _documento_por_id(manifest: Manifest) -> dict[str, object]:
    return {doc.id: doc for doc in manifest.documentos}


def _actuacion_por_id(manifest: Manifest) -> dict[str, object]:
    return {act.id: act for act in manifest.actuaciones}


def _render_identificacion(manifest: Manifest) -> str:
    exp = manifest.expediente
    return "\n".join(
        [
            f"- Expediente interno: `{exp.id}`.",
            f"- Jurisdicción: `{exp.jurisdiccion}`.",
            f"- Número/año: `{exp.numero}/{exp.anio}`.",
            f"- Fuente: `{exp.fuente}`.",
            "- Trazabilidad base: `manifest.json`.",
        ]
    )


def _render_resumen(manifest: Manifest, hallazgos: list[Hallazgo]) -> str:
    altas = sum(1 for doc in manifest.documentos if getattr(doc.relevancia, "value", doc.relevancia) == "alta")
    medias = sum(1 for doc in manifest.documentos if getattr(doc.relevancia, "value", doc.relevancia) == "media")
    return "\n".join(
        [
            f"- Actuaciones registradas: {len(manifest.actuaciones)}.",
            f"- Documentos registrados: {len(manifest.documentos)}.",
            f"- Documentos de relevancia alta: {altas}.",
            f"- Documentos de relevancia media: {medias}.",
            f"- Hallazgos validados incorporados: {len(hallazgos)}.",
            "- Trazabilidad base: `manifest.json` y `reports/analisis-validado.json`.",
        ]
    )


def _render_cronologia(manifest: Manifest) -> str:
    if not manifest.actuaciones:
        return "Información insuficiente."
    lineas = []
    for act in sorted(manifest.actuaciones, key=lambda a: a.orden):
        fecha = act.fecha.isoformat() if act.fecha else "sin fecha"
        docs = ", ".join(act.documentos) if act.documentos else "sin documentos"
        lineas.append(f"- `{act.id}` | {fecha} | {act.descripcion}. Documentos: {docs}.")
    return "\n".join(lineas)


def _render_documentos(manifest: Manifest) -> str:
    seleccionados = [doc for doc in manifest.documentos if doc.ruta_selected]
    if not seleccionados:
        return "Información insuficiente."
    lineas = []
    for doc in seleccionados:
        categoria = getattr(doc.categoria, "value", doc.categoria)
        relevancia = getattr(doc.relevancia, "value", doc.relevancia)
        lineas.append(
            f"- `{doc.id}` | {doc.nombre_archivo} | categoría: {categoria} | "
            f"relevancia: {relevancia} | actuación: {doc.actuacion_id}."
        )
    return "\n".join(lineas)


def _render_hallazgos_generales(hallazgos: list[Hallazgo]) -> str:
    if not hallazgos:
        return "Información insuficiente."
    return "\n".join(_linea_hallazgo(h) for h in hallazgos)


def _render_seccion_hallazgos(hallazgos: list[Hallazgo]) -> str:
    if not hallazgos:
        return "Información insuficiente."
    return "\n".join(_linea_hallazgo(h) for h in hallazgos)


def _render_no_determinable(descartados: list[dict], por_seccion: dict[int, list[Hallazgo]]) -> str:
    lineas = []
    secciones_sin_datos = [idx for idx in range(6, 13) if not por_seccion.get(idx)]
    if secciones_sin_datos:
        nombres = ", ".join(f"{idx}. {SECCIONES[idx - 1]}" for idx in secciones_sin_datos)
        lineas.append(f"- Información insuficiente en secciones: {nombres}.")
    if descartados:
        lineas.append(f"- Hallazgos descartados por falta de fuente válida: {len(descartados)}.")
    if not lineas:
        return "Información insuficiente."
    return "\n".join(lineas)


def _render_proximos_pasos(hallazgos: list[Hallazgo]) -> str:
    if not hallazgos:
        return "Información insuficiente."
    return "\n".join(
        [
            "- Revisar manualmente los hallazgos validados antes de usarlos como criterio jurídico.",
            "- Priorizar los documentos de relevancia alta en `selected/`.",
            "- Verificar plazos y cargas contra el expediente real antes de cualquier decisión procesal.",
            "- Trazabilidad base: hallazgos validados con fuentes internas existentes.",
        ]
    )


def construir_informe_markdown(manifest: Manifest, hallazgos: list[Hallazgo], descartados: list[dict]) -> str:
    """Construye un informe Markdown de 14 secciones."""
    por_seccion = _hallazgos_por_seccion(hallazgos)
    partes = [
        f"# Informe expediente-scout — {manifest.expediente.id}",
        "",
        "Informe generado por el núcleo determinístico. No reemplaza revisión profesional humana.",
        "",
    ]

    contenido_por_indice: dict[int, str] = {
        1: _render_identificacion(manifest),
        2: _render_resumen(manifest, hallazgos),
        3: _render_cronologia(manifest),
        4: _render_documentos(manifest),
        5: _render_hallazgos_generales(hallazgos),
        13: _render_no_determinable(descartados, por_seccion),
        14: _render_proximos_pasos(hallazgos),
    }

    for idx, titulo in enumerate(SECCIONES, start=1):
        partes.append(f"## {idx}. {titulo}")
        if 6 <= idx <= 12:
            partes.append(_render_seccion_hallazgos(por_seccion.get(idx, [])))
        else:
            partes.append(contenido_por_indice[idx])
        partes.append("")

    return "\n".join(partes).rstrip() + "\n"


def reportar_expediente(root: Path, jurisdiccion: str, numero: str, anio: int) -> ResultadoReporte:
    """Genera reports/informe.md desde manifest y análisis validado."""
    expediente_dir = _expediente_dir(root, jurisdiccion, numero, anio)
    manifest_path = expediente_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No existe manifest: {manifest_path}")

    analisis_validado_path = expediente_dir / "reports" / "analisis-validado.json"
    manifest = cargar_manifest(manifest_path)
    hallazgos, descartados = _cargar_analisis_validado(analisis_validado_path)

    informe = construir_informe_markdown(manifest, hallazgos, descartados)
    reports_dir = expediente_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    informe_path = reports_dir / "informe.md"
    informe_path.write_text(informe, encoding="utf-8")

    manifest.estado_analisis.ultimo_informe = str(informe_path.relative_to(expediente_dir))
    manifest.estado_analisis.actualizado = datetime.now(timezone.utc)
    guardar_manifest(manifest, manifest_path)

    return ResultadoReporte(
        manifest_path=manifest_path,
        analisis_validado_path=analisis_validado_path,
        informe_path=informe_path,
        secciones=len(SECCIONES),
        hallazgos_incluidos=len(hallazgos),
    )
