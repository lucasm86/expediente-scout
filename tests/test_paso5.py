from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app
from expediente_scout.domain.enums import Categoria, Relevancia
from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.domain.models import Documento
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.curar import clasificar_documento, curar_expediente
from expediente_scout.pipeline.ingerir import ingerir_captura
from expediente_scout.pipeline.normalizar import normalizar_expediente

runner = CliRunner()


def _preparar_ampliado(tmp_path: Path) -> Path:
    manifest_path = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura(estado="ampliado"))
    normalizar_expediente(tmp_path, "pjn", "12345", 2024)
    return manifest_path


def test_curar_clasifica_categorias_del_mock_ampliado(tmp_path):
    manifest_path = _preparar_ampliado(tmp_path)
    curar_expediente(tmp_path, "pjn", "12345", 2024)
    manifest = cargar_manifest(manifest_path)

    por_archivo = {doc.nombre_archivo: doc for doc in manifest.documentos}

    assert por_archivo["demanda.pdf"].categoria == Categoria.DEMANDA
    assert por_archivo["contestacion.pdf"].categoria == Categoria.CONTESTACION
    assert por_archivo["proveido_traslado.pdf"].categoria == Categoria.PROVEIDO_SIMPLE
    assert por_archivo["pericia_medica.pdf"].categoria == Categoria.PERICIA
    assert por_archivo["interlocutoria.pdf"].categoria == Categoria.INTERLOCUTORIA
    assert por_archivo["proveido_intimacion.pdf"].categoria == Categoria.PROVEIDO_SIMPLE
    assert por_archivo["documental_complementaria.pdf"].categoria == Categoria.DOCUMENTAL

    assert por_archivo["demanda.pdf"].relevancia == Relevancia.ALTA
    assert por_archivo["proveido_traslado.pdf"].relevancia == Relevancia.MEDIA
    assert por_archivo["documental_complementaria.pdf"].relevancia == Relevancia.MEDIA
    assert all(doc.metodo_clasificacion == "regla" for doc in manifest.documentos)


def test_curar_copia_relevantes_a_selected(tmp_path):
    manifest_path = _preparar_ampliado(tmp_path)
    resultado = curar_expediente(tmp_path, "pjn", "12345", 2024)
    manifest = cargar_manifest(manifest_path)
    expediente_dir = tmp_path / "data" / "expedientes" / "pjn" / "12345-2024"

    assert resultado.documentos_curados == 7
    assert resultado.seleccionados == 7
    assert resultado.alta == 4
    assert resultado.media == 3
    assert resultado.requiere_revision == 0

    for doc in manifest.documentos:
        assert doc.ruta_selected is not None
        assert (expediente_dir / doc.ruta_selected).exists()


def test_regla_desconocida_queda_para_revision_humana():
    documento = Documento(
        id="doc-test",
        nombre_archivo="archivo_neutro.pdf",
        ruta_raw="raw/archivo_neutro.pdf",
        hash_sha256="0" * 64,
        estado_descarga="completo",
    )

    clasificacion = clasificar_documento(documento, actuacion=None, texto="contenido sin palabras clave")

    assert clasificacion.categoria == Categoria.SIN_CLASIFICAR
    assert clasificacion.relevancia == Relevancia.REQUIERE_REVISION
    assert clasificacion.seleccionar is False


def test_documento_duplicado_no_se_selecciona():
    documento = Documento(
        id="doc-dup",
        nombre_archivo="copia.pdf",
        ruta_raw="raw/copia.pdf",
        hash_sha256="1" * 64,
        estado_descarga="completo",
        categoria=Categoria.DUPLICADO,
        relevancia=Relevancia.DUPLICADO,
        duplicado_de="doc-original",
    )

    clasificacion = clasificar_documento(documento, actuacion=None, texto="demanda")

    assert clasificacion.categoria == Categoria.DUPLICADO
    assert clasificacion.relevancia == Relevancia.DUPLICADO
    assert clasificacion.seleccionar is False


def test_cli_curar(tmp_path):
    result_ing = runner.invoke(
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
            "--mock-estado",
            "ampliado",
        ],
    )
    assert result_ing.exit_code == 0

    result_norm = runner.invoke(
        app,
        ["normalizar", "--root", str(tmp_path), "--jurisdiccion", "pjn", "--numero", "12345", "--anio", "2024"],
    )
    assert result_norm.exit_code == 0

    result = runner.invoke(
        app,
        ["curar", "--root", str(tmp_path), "--jurisdiccion", "pjn", "--numero", "12345", "--anio", "2024"],
    )

    assert result.exit_code == 0
    assert "Documentos curados: 7" in result.output
    assert "Seleccionados: 7" in result.output
    assert "Alta: 4" in result.output
    assert "Media: 3" in result.output
