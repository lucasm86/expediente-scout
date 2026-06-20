"""Pipeline para validar un JSON de análisis contra un manifest local."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from expediente_scout.analisis.contrato import AnalisisEstructurado
from expediente_scout.analisis.validador import ResultadoValidacion, validar_analisis
from expediente_scout.domain.manifest import cargar_manifest


@dataclass(frozen=True)
class ResultadoValidacionArchivo:
    manifest_path: Path
    analisis_path: Path
    salida_path: Path
    total_validos: int
    total_descartados: int


def _expediente_dir(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return Path(root).resolve() / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}"


def _serializar_resultado(resultado: ResultadoValidacion) -> dict:
    return {
        "hallazgos_validos": [h.model_dump(mode="json") for h in resultado.validos],
        "hallazgos_descartados": [h.model_dump(mode="json") for h in resultado.descartados],
        "total_validos": resultado.total_validos,
        "total_descartados": resultado.total_descartados,
    }


def validar_analisis_archivo(
    root: Path,
    jurisdiccion: str,
    numero: str,
    anio: int,
    analisis_path: Path,
) -> ResultadoValidacionArchivo:
    """Carga análisis JSON, valida referencias internas y escribe salida auditada."""
    expediente_dir = _expediente_dir(root, jurisdiccion, numero, anio)
    manifest_path = expediente_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No existe manifest: {manifest_path}")

    analisis_path = Path(analisis_path).resolve()
    if not analisis_path.exists():
        raise FileNotFoundError(f"No existe análisis JSON: {analisis_path}")

    manifest = cargar_manifest(manifest_path)
    data = json.loads(analisis_path.read_text(encoding="utf-8"))
    analisis = AnalisisEstructurado.model_validate(data)
    resultado = validar_analisis(analisis, manifest)

    reports_dir = expediente_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    salida_path = reports_dir / "analisis-validado.json"
    salida_path.write_text(
        json.dumps(_serializar_resultado(resultado), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return ResultadoValidacionArchivo(
        manifest_path=manifest_path,
        analisis_path=analisis_path,
        salida_path=salida_path,
        total_validos=resultado.total_validos,
        total_descartados=resultado.total_descartados,
    )
