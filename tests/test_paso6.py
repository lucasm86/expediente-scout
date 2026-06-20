from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.analisis.contrato import AnalisisEstructurado, Hallazgo
from expediente_scout.analisis.validador import ids_existentes, validar_analisis, validar_hallazgos
from expediente_scout.cli import app
from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.curar import curar_expediente
from expediente_scout.pipeline.ingerir import ingerir_captura
from expediente_scout.pipeline.normalizar import normalizar_expediente
from expediente_scout.pipeline.validar_analisis import validar_analisis_archivo

runner = CliRunner()


def _preparar_ampliado(tmp_path: Path) -> Path:
    manifest_path = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="ampliado"))
    normalizar_expediente(tmp_path, "pjn", "12345", 2024)
    curar_expediente(tmp_path, "pjn", "12345", 2024)
    return manifest_path


def _analisis_simulado(manifest_path: Path) -> AnalisisEstructurado:
    manifest = cargar_manifest(manifest_path)
    doc_id = manifest.documentos[0].id
    act_id = manifest.actuaciones[0].id
    return AnalisisEstructurado(
        hallazgos=[
            Hallazgo(
                tipo="etapa",
                afirmacion="Hay una actuación inicial identificada.",
                fuentes=[act_id],
                confianza="alta",
            ),
            Hallazgo(
                tipo="riesgo_probatorio",
                afirmacion="Existe una pieza documental relevante.",
                fuentes=[doc_id],
                confianza="media",
            ),
            Hallazgo(
                tipo="plazo",
                afirmacion="Este hallazgo cita algo inexistente.",
                fuentes=["doc-no-existe"],
                confianza="baja",
            ),
            Hallazgo(
                tipo="carga_actora",
                afirmacion="Este hallazgo no trae fuentes.",
                fuentes=[],
                confianza="media",
            ),
        ],
        no_determinable=["No se determina fuero real en datos mock."],
        requiere_revision=True,
    )


def test_ids_existentes_incluye_documentos_y_actuaciones(tmp_path):
    manifest_path = _preparar_ampliado(tmp_path)
    manifest = cargar_manifest(manifest_path)
    ids = ids_existentes(manifest)

    assert {doc.id for doc in manifest.documentos}.issubset(ids)
    assert {act.id for act in manifest.actuaciones}.issubset(ids)


def test_validador_descarta_refs_inexistentes_y_sin_fuentes(tmp_path):
    manifest_path = _preparar_ampliado(tmp_path)
    manifest = cargar_manifest(manifest_path)
    analisis = _analisis_simulado(manifest_path)

    resultado = validar_analisis(analisis, manifest)

    assert resultado.total_validos == 2
    assert resultado.total_descartados == 2
    assert all(h.fuentes for h in resultado.validos)


def test_validar_hallazgos_permite_multiples_fuentes_existentes(tmp_path):
    manifest_path = _preparar_ampliado(tmp_path)
    manifest = cargar_manifest(manifest_path)
    hallazgo = Hallazgo(
        tipo="etapa",
        afirmacion="Cita actuación y documento existentes.",
        fuentes=[manifest.actuaciones[0].id, manifest.documentos[0].id],
        confianza="alta",
    )

    resultado = validar_hallazgos([hallazgo], manifest)

    assert resultado.total_validos == 1
    assert resultado.total_descartados == 0


def test_pipeline_valida_archivo_y_escribe_salida(tmp_path):
    manifest_path = _preparar_ampliado(tmp_path)
    analisis = _analisis_simulado(manifest_path)
    analisis_path = tmp_path / "analisis-simulado.json"
    analisis_path.write_text(analisis.model_dump_json(indent=2), encoding="utf-8")

    resultado = validar_analisis_archivo(tmp_path, "pjn", "12345", 2024, analisis_path)

    assert resultado.total_validos == 2
    assert resultado.total_descartados == 2
    assert resultado.salida_path.exists()
    data = json.loads(resultado.salida_path.read_text(encoding="utf-8"))
    assert data["total_validos"] == 2
    assert data["total_descartados"] == 2
    assert len(data["hallazgos_validos"]) == 2
    assert len(data["hallazgos_descartados"]) == 2


def test_cli_validar_analisis(tmp_path):
    manifest_path = _preparar_ampliado(tmp_path)
    analisis = _analisis_simulado(manifest_path)
    analisis_path = tmp_path / "analisis-cli.json"
    analisis_path.write_text(analisis.model_dump_json(indent=2), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "validar-analisis",
            "--root",
            str(tmp_path),
            "--jurisdiccion",
            "pjn",
            "--numero",
            "12345",
            "--anio",
            "2024",
            "--analisis-json",
            str(analisis_path),
        ],
    )

    assert result.exit_code == 0
    assert "Hallazgos válidos: 2" in result.output
    assert "Hallazgos descartados: 2" in result.output
    assert "analisis-validado.json" in result.output
