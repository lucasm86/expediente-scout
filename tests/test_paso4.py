from __future__ import annotations

from typer.testing import CliRunner

from expediente_scout.cli import app
from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.ingerir import ingerir_captura
from expediente_scout.pipeline.novedades import detectar_novedades_captura

runner = CliRunner()


def test_mock_expone_estado_base_y_ampliado(tmp_path):
    base = MockCaptura(base_dir=tmp_path / "base", estado="base")
    ampliado = MockCaptura(base_dir=tmp_path / "ampliado", estado="ampliado")

    assert len(base.leer_indice()) == 5
    assert len(ampliado.leer_indice()) == 7
    assert [item.orden for item in ampliado.leer_indice()][-2:] == [6, 7]


def test_detectar_novedades_sin_modificar_manifest(tmp_path):
    manifest_path = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="base"))
    contenido_antes = manifest_path.read_text(encoding="utf-8")

    resumen = detectar_novedades_captura(
        tmp_path,
        "pjn",
        "12345",
        2024,
        MockCaptura(estado="ampliado"),
    )

    assert resumen.manifest_existe is True
    assert resumen.total_actuaciones_nuevas == 2
    assert resumen.total_documentos_nuevos == 2
    assert [n.actuacion_id for n in resumen.actuaciones_nuevas] == ["act-0006", "act-0007"]
    assert manifest_path.read_text(encoding="utf-8") == contenido_antes


def test_reingerir_estado_ampliado_agrega_solo_nuevo(tmp_path):
    manifest_path = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="base"))
    manifest_base = cargar_manifest(manifest_path)

    manifest_path_2 = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="ampliado"))
    manifest_ampliado = cargar_manifest(manifest_path_2)

    assert len(manifest_base.actuaciones) == 5
    assert len(manifest_base.documentos) == 5
    assert len(manifest_ampliado.actuaciones) == 7
    assert len(manifest_ampliado.documentos) == 7
    assert manifest_ampliado.capturas[-1].actuaciones_nuevas == 2
    assert manifest_ampliado.capturas[-1].documentos_nuevos == 2
    assert manifest_ampliado.actuaciones[-1].descripcion == "Acompaña documental complementaria"


def test_reingerir_ampliado_dos_veces_no_duplica(tmp_path):
    manifest_path = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="base"))
    ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="ampliado"))
    contenido_antes = manifest_path.read_text(encoding="utf-8")

    ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="ampliado"))
    contenido_despues = manifest_path.read_text(encoding="utf-8")
    manifest = cargar_manifest(manifest_path)

    assert len(manifest.actuaciones) == 7
    assert len(manifest.documentos) == 7
    assert len(manifest.capturas) == 2
    assert contenido_antes == contenido_despues


def test_cli_novedades_y_ingerir_ampliado(tmp_path):
    base = runner.invoke(app, ["ingerir", "--root", str(tmp_path), "--mock-estado", "base"])
    assert base.exit_code == 0, base.output
    assert "Actuaciones nuevas: 5" in base.output

    novedades = runner.invoke(app, ["novedades", "--root", str(tmp_path), "--mock-estado", "ampliado"])
    assert novedades.exit_code == 0, novedades.output
    assert "Actuaciones nuevas: 2" in novedades.output
    assert "act-0006" in novedades.output
    assert "act-0007" in novedades.output

    ampliado = runner.invoke(app, ["ingerir", "--root", str(tmp_path), "--mock-estado", "ampliado"])
    assert ampliado.exit_code == 0, ampliado.output
    assert "Actuaciones: 7" in ampliado.output
    assert "Documentos: 7" in ampliado.output
    assert "Actuaciones nuevas: 2" in ampliado.output
    assert "Documentos nuevos: 2" in ampliado.output
