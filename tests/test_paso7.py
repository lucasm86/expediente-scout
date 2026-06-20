from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.analisis.contrato import AnalisisEstructurado, Hallazgo
from expediente_scout.cli import app
from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.curar import curar_expediente
from expediente_scout.pipeline.ingerir import ingerir_captura
from expediente_scout.pipeline.normalizar import normalizar_expediente
from expediente_scout.pipeline.reportar import reportar_expediente
from expediente_scout.pipeline.validar_analisis import validar_analisis_archivo

runner = CliRunner()


def _preparar_con_analisis(tmp_path: Path) -> Path:
    manifest_path = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="ampliado"))
    normalizar_expediente(tmp_path, "pjn", "12345", 2024)
    curar_expediente(tmp_path, "pjn", "12345", 2024)
    manifest = cargar_manifest(manifest_path)
    analisis = AnalisisEstructurado(
        hallazgos=[
            Hallazgo(
                tipo="etapa",
                afirmacion="La etapa procesal surge de la actuación inicial.",
                fuentes=[manifest.actuaciones[0].id],
                confianza="alta",
            ),
            Hallazgo(
                tipo="carga_actora",
                afirmacion="Debe revisarse la documental de mayor relevancia.",
                fuentes=[manifest.documentos[0].id],
                confianza="media",
            ),
            Hallazgo(
                tipo="riesgo_probatorio",
                afirmacion="La pericia debe controlarse contra el resto de constancias.",
                fuentes=[manifest.documentos[3].id],
                confianza="media",
            ),
            Hallazgo(
                tipo="plazo",
                afirmacion="Este plazo no debe aparecer porque cita una fuente falsa.",
                fuentes=["doc-no-existe"],
                confianza="baja",
            ),
            Hallazgo(
                tipo="riesgo_procesal",
                afirmacion="Este riesgo tampoco debe aparecer porque no tiene fuentes.",
                fuentes=[],
                confianza="baja",
            ),
        ],
        no_determinable=["No se determina un vencimiento real con datos mock."],
        requiere_revision=True,
    )
    analisis_path = tmp_path / "analisis-simulado-paso7.json"
    analisis_path.write_text(analisis.model_dump_json(indent=2), encoding="utf-8")
    validar_analisis_archivo(tmp_path, "pjn", "12345", 2024, analisis_path)
    return manifest_path


def test_reportar_genera_markdown_con_14_secciones(tmp_path):
    _preparar_con_analisis(tmp_path)

    resultado = reportar_expediente(tmp_path, "pjn", "12345", 2024)
    texto = resultado.informe_path.read_text(encoding="utf-8")

    assert resultado.secciones == 14
    assert texto.count("\n## ") == 14
    assert resultado.informe_path.name == "informe.md"


def test_informe_incluye_validos_y_excluye_descartados(tmp_path):
    _preparar_con_analisis(tmp_path)

    resultado = reportar_expediente(tmp_path, "pjn", "12345", 2024)
    texto = resultado.informe_path.read_text(encoding="utf-8")

    assert "La etapa procesal surge de la actuación inicial" in texto
    assert "Debe revisarse la documental de mayor relevancia" in texto
    assert "Este plazo no debe aparecer" not in texto
    assert "Este riesgo tampoco debe aparecer" not in texto


def test_hallazgos_del_informe_tienen_fuentes_existentes(tmp_path):
    manifest_path = _preparar_con_analisis(tmp_path)
    manifest = cargar_manifest(manifest_path)
    ids = {doc.id for doc in manifest.documentos} | {act.id for act in manifest.actuaciones}

    resultado = reportar_expediente(tmp_path, "pjn", "12345", 2024)
    texto = resultado.informe_path.read_text(encoding="utf-8")
    lineas_fuente = [linea for linea in texto.splitlines() if "Fuentes:" in linea]

    assert lineas_fuente
    for linea in lineas_fuente:
        fuentes = linea.split("Fuentes:", 1)[1].rstrip(".").strip()
        for fuente in [f.strip() for f in fuentes.split(",")]:
            assert fuente in ids


def test_secciones_sin_datos_dicen_informacion_insuficiente(tmp_path):
    _preparar_con_analisis(tmp_path)

    resultado = reportar_expediente(tmp_path, "pjn", "12345", 2024)
    texto = resultado.informe_path.read_text(encoding="utf-8")

    assert "## 8. Plazos y vencimientos\nInformación insuficiente." in texto
    assert "## 12. Novedades detectadas\nInformación insuficiente." in texto


def test_cli_reportar_funciona(tmp_path):
    _preparar_con_analisis(tmp_path)

    result = runner.invoke(
        app,
        [
            "reportar",
            "--root",
            str(tmp_path),
            "--jurisdiccion",
            "pjn",
            "--numero",
            "12345",
            "--anio",
            "2024",
        ],
    )

    assert result.exit_code == 0
    assert "Informe:" in result.output
    assert "Secciones: 14" in result.output
    assert "Hallazgos incluidos: 3" in result.output
