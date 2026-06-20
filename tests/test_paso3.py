from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app
from expediente_scout.domain.enums import Categoria, Relevancia
from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.fuente_captura import ItemIndice
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.ingerir import ingerir_captura
from expediente_scout.pipeline.normalizar import normalizar_expediente

runner = CliRunner()


class FuenteConDuplicado:
    fuente_id = "duplicado"

    def __init__(self, base_dir: Path) -> None:
        mock = MockCaptura(base_dir / "mock")
        self._raw_dir = base_dir / "raw_duplicado"
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mock.ruta_raw() / "demanda.pdf", self._raw_dir / "demanda.pdf")
        shutil.copy2(mock.ruta_raw() / "demanda.pdf", self._raw_dir / "demanda_copia.pdf")

    def ruta_raw(self) -> Path:
        return self._raw_dir

    def leer_indice(self) -> list[ItemIndice]:
        return [
            ItemIndice(orden=1, fecha=date(2024, 3, 10), descripcion="Presenta demanda", archivo="demanda.pdf"),
            ItemIndice(orden=2, fecha=date(2024, 3, 11), descripcion="Presenta copia de demanda", archivo="demanda_copia.pdf"),
        ]


def test_normalizar_extrae_texto_y_paginas(tmp_path):
    manifest_path = ingerir_captura(tmp_path, "pjn", "12345", 2024, MockCaptura())

    normalizar_expediente(tmp_path, "pjn", "12345", 2024)

    manifest = cargar_manifest(manifest_path)
    assert len(manifest.documentos) == 5
    for documento in manifest.documentos:
        assert documento.paginas is not None
        assert documento.paginas > 0
        assert documento.ruta_text is not None
        text_path = tmp_path / "data" / "expedientes" / "pjn" / "12345-2024" / documento.ruta_text
        assert text_path.exists()
        assert "expediente-scout mock" in text_path.read_text(encoding="utf-8")


def test_normalizar_marca_duplicados_por_hash(tmp_path):
    manifest_path = ingerir_captura(tmp_path, "pjn", "777", 2024, FuenteConDuplicado(tmp_path / "fuente"))

    normalizar_expediente(tmp_path, "pjn", "777", 2024)

    manifest = cargar_manifest(manifest_path)
    assert len(manifest.documentos) == 2
    duplicados = [doc for doc in manifest.documentos if doc.relevancia == Relevancia.DUPLICADO]
    originales = [doc for doc in manifest.documentos if doc.relevancia != Relevancia.DUPLICADO]
    assert len(duplicados) == 1
    assert len(originales) == 1
    assert duplicados[0].categoria == Categoria.DUPLICADO
    assert duplicados[0].duplicado_de == originales[0].id


def test_cli_normalizar_funciona(tmp_path):
    result_ingerir = runner.invoke(app, ["ingerir", "--root", str(tmp_path), "--jurisdiccion", "pjn", "--numero", "12345", "--anio", "2024"])
    assert result_ingerir.exit_code == 0, result_ingerir.output

    result_normalizar = runner.invoke(app, ["normalizar", "--root", str(tmp_path), "--jurisdiccion", "pjn", "--numero", "12345", "--anio", "2024"])

    assert result_normalizar.exit_code == 0, result_normalizar.output
    assert "Documentos normalizados: 5" in result_normalizar.output
    assert "Duplicados: 0" in result_normalizar.output


def test_normalizar_falla_si_no_existe_manifest(tmp_path):
    result = runner.invoke(app, ["normalizar", "--root", str(tmp_path), "--jurisdiccion", "pjn", "--numero", "999", "--anio", "2024"])

    assert result.exit_code == 1
    assert "No existe manifest" in result.output
