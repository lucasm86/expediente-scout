from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from expediente_scout.pipeline.clasificar_playbook import clasificar_indice_playbook
from expediente_scout.pipeline.seleccionar_lectura import generar_plan_lectura
from expediente_scout.pipeline.resolver_plan_lectura import generar_plan_lectura_resuelto
from expediente_scout.pipeline.extraer_texto_seleccionado import generar_extraccion_texto
from expediente_scout.pipeline.generar_paquete_analisis import generar_paquete_analisis


@dataclass(frozen=True)
class ResultadoPreanalisis:
    indice_path: Path
    raw_dir: Path
    output_dir: Path
    playbook_id: str
    clasificacion_path: Path
    plan_lectura_path: Path
    plan_lectura_resuelto_path: Path
    extraccion_dir: Path
    extraccion_indice_path: Path
    paquete_dir: Path
    paquete_indice_path: Path
    mapa_general_path: Path
    total_actuaciones: int
    total_con_hito: int
    total_seleccionadas: int
    total_extraidas: int
    total_bloques: int
    total_caracteres: int


def ejecutar_preanalisis(
    *,
    indice_path: Path,
    raw_dir: Path,
    output_dir: Path,
    playbook_id: str = "ordinario_v1",
    strict: bool = True,
) -> ResultadoPreanalisis:
    output_dir.mkdir(parents=True, exist_ok=True)

    clasificacion_path = output_dir / "clasificacion_playbook.json"
    plan_lectura_path = output_dir / "plan_lectura.json"
    plan_lectura_resuelto_path = output_dir / "plan_lectura_resuelto.json"
    extraccion_dir = output_dir / "extraccion_texto_seleccionados"
    paquete_dir = output_dir / "paquete_analisis"

    clasificacion = clasificar_indice_playbook(
        indice_path=indice_path,
        playbook_id=playbook_id,
        output_path=clasificacion_path,
    )

    plan_lectura = generar_plan_lectura(
        clasificacion_path=clasificacion_path,
        output_path=plan_lectura_path,
    )

    generar_plan_lectura_resuelto(
        plan_path=plan_lectura_path,
        raw_dir=raw_dir,
        output_path=plan_lectura_resuelto_path,
        strict=strict,
    )

    extraccion = generar_extraccion_texto(
        plan_path=plan_lectura_resuelto_path,
        output_dir=extraccion_dir,
        strict=strict,
    )

    paquete = generar_paquete_analisis(
        extraccion_path=extraccion.indice_path,
        output_dir=paquete_dir,
    )

    return ResultadoPreanalisis(
        indice_path=indice_path,
        raw_dir=raw_dir,
        output_dir=output_dir,
        playbook_id=playbook_id,
        clasificacion_path=clasificacion_path,
        plan_lectura_path=plan_lectura_path,
        plan_lectura_resuelto_path=plan_lectura_resuelto_path,
        extraccion_dir=extraccion_dir,
        extraccion_indice_path=extraccion.indice_path,
        paquete_dir=paquete_dir,
        paquete_indice_path=paquete.indice_path,
        mapa_general_path=paquete.mapa_path,
        total_actuaciones=clasificacion.total_actuaciones,
        total_con_hito=clasificacion.total_con_hito,
        total_seleccionadas=plan_lectura.total_seleccionadas,
        total_extraidas=extraccion.total_extraidas,
        total_bloques=paquete.total_bloques,
        total_caracteres=paquete.total_caracteres,
    )
