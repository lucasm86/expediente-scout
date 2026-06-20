from __future__ import annotations

from typer.testing import CliRunner

from expediente_scout.cli import app
from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.ingerir import ingerir_captura

runner = CliRunner()


def test_cli_ingerir_crea_manifest(tmp_path):
    result = runner.invoke(
        app,
        [
            "ingerir",
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

    assert result.exit_code == 0, result.output
    manifest_path = tmp_path / "data" / "expedientes" / "pjn" / "12345-2024" / "manifest.json"
    assert manifest_path.exists()
    assert "Expediente: pjn-12345-2024" in result.output


def test_reingerir_no_duplica(tmp_path):
    manifest_path = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura())
    contenido_primera = manifest_path.read_text(encoding="utf-8")

    manifest_path_2 = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura())
    contenido_segunda = manifest_path_2.read_text(encoding="utf-8")

    manifest = cargar_manifest(manifest_path_2)
    assert len(manifest.actuaciones) == 5
    assert len(manifest.documentos) == 5
    assert len(manifest.capturas) == 1
    assert contenido_primera == contenido_segunda


def test_listar_enumera_expediente_local(tmp_path):
    ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura())

    result = runner.invoke(app, ["listar", "--root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "pjn-12345-2024" in result.output
    assert "actuaciones" in result.output
    assert "documentos" in result.output


def test_estado_devuelve_parte_breve(tmp_path):
    ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura())

    result = runner.invoke(
        app,
        [
            "estado",
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

    assert result.exit_code == 0, result.output
    assert "Expediente: pjn-12345-2024" in result.output
    assert "Actuaciones: 5" in result.output
    assert "Documentos: 5" in result.output
    assert "Resolución interlocutoria" in result.output
