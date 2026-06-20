"""Pipeline para ejecutar script de captura real y reconciliar manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.domain.paths import crear_estructura
from expediente_scout.ingesta.script_captura import ScriptCaptura
from expediente_scout.pipeline.ingerir import ingerir_captura


@dataclass(frozen=True)
class ResultadoCapturaPJN:
    manifest_path: Path
    indice_path: Path
    raw_dir: Path
    log_path: Path
    actuaciones_nuevas: int
    documentos_nuevos: int
    total_actuaciones: int
    total_documentos: int


def capturar_desde_script(
    root: Path,
    jurisdiccion: str,
    numero: str,
    anio: int,
    script_path: Path,
    env_path: Path | None = None,
    output_dir: Path | None = None,
    timeout: int = 300,
) -> ResultadoCapturaPJN:
    """Ejecuta script externo, ingiere su salida y escribe log sin secretos."""
    expediente_dir = crear_estructura(root, jurisdiccion, numero, anio)
    manifest_path = expediente_dir / "manifest.json"
    antes = cargar_manifest(manifest_path) if manifest_path.exists() else None
    actuaciones_antes = len(antes.actuaciones) if antes else 0
    documentos_antes = len(antes.documentos) if antes else 0

    if output_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = expediente_dir / "logs" / "capturas" / "script_pjn" / timestamp

    fuente = ScriptCaptura(script_path=script_path, output_dir=output_dir, env_path=env_path, timeout=timeout)
    ejecucion = fuente.ejecutar(jurisdiccion=jurisdiccion, numero=numero, anio=anio)

    manifest_path = ingerir_captura(
        root=root,
        jurisdiccion=jurisdiccion,
        numero=numero,
        anio=anio,
        fuente=fuente,
    )
    manifest = cargar_manifest(manifest_path)
    actuaciones_nuevas = len(manifest.actuaciones) - actuaciones_antes
    documentos_nuevos = len(manifest.documentos) - documentos_antes

    log_dir = expediente_dir / "logs" / "captura-pjn"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    log_data = {
        "jurisdiccion": jurisdiccion,
        "numero": numero,
        "anio": anio,
        "adapter": fuente.fuente_id,
        "script_path": str(Path(script_path).resolve()),
        "env_path_usado": bool(env_path),
        "output_dir": str(Path(output_dir).resolve()),
        "indice_path": str(ejecucion.indice_path.resolve()),
        "raw_dir": str(ejecucion.raw_dir.resolve()),
        "returncode": ejecucion.returncode,
        "actuaciones_nuevas": actuaciones_nuevas,
        "documentos_nuevos": documentos_nuevos,
        "total_actuaciones": len(manifest.actuaciones),
        "total_documentos": len(manifest.documentos),
        "nota": "No se guardan salidas del script externo ni secretos.",
    }
    log_path.write_text(json.dumps(log_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    return ResultadoCapturaPJN(
        manifest_path=manifest_path,
        indice_path=ejecucion.indice_path,
        raw_dir=ejecucion.raw_dir,
        log_path=log_path,
        actuaciones_nuevas=actuaciones_nuevas,
        documentos_nuevos=documentos_nuevos,
        total_actuaciones=len(manifest.actuaciones),
        total_documentos=len(manifest.documentos),
    )
