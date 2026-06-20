from pathlib import Path

import fitz

from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.ingerir import ingerir_captura


def _ingestar(tmp_path: Path):
    fuente = MockCaptura(base_dir=tmp_path / "captura")
    manifest_path = ingerir_captura(
        root=tmp_path / "proyecto",
        jurisdiccion="pjn",
        numero="12345",
        anio=2024,
        fuente=fuente,
    )
    return manifest_path, cargar_manifest(manifest_path)


def test_crea_estructura_completa(tmp_path: Path):
    manifest_path, _manifest = _ingestar(tmp_path)
    expediente_dir = manifest_path.parent

    assert (expediente_dir / "raw").is_dir()
    assert (expediente_dir / "selected").is_dir()
    assert (expediente_dir / "text").is_dir()
    assert (expediente_dir / "reports").is_dir()
    assert (expediente_dir / "logs").is_dir()
    assert (expediente_dir / "manifest.json").is_file()


def test_manifest_carga_y_valida(tmp_path: Path):
    _manifest_path, manifest = _ingestar(tmp_path)

    assert manifest.schema_version == "1.0"
    assert len(manifest.actuaciones) == 5
    assert len(manifest.documentos) == 5


def test_ids_deterministicos(tmp_path: Path):
    fuente_1 = MockCaptura(base_dir=tmp_path / "captura_1")
    fuente_2 = MockCaptura(base_dir=tmp_path / "captura_2")

    manifest_path_1 = ingerir_captura(tmp_path / "run_1", "pjn", "12345", 2024, fuente_1)
    manifest_path_2 = ingerir_captura(tmp_path / "run_2", "pjn", "12345", 2024, fuente_2)

    manifest_1 = cargar_manifest(manifest_path_1)
    manifest_2 = cargar_manifest(manifest_path_2)

    assert [a.id for a in manifest_1.actuaciones] == [a.id for a in manifest_2.actuaciones]
    assert [d.id for d in manifest_1.documentos] == [d.id for d in manifest_2.documentos]


def test_pdfs_mock_tienen_paginas(tmp_path: Path):
    fuente = MockCaptura(base_dir=tmp_path / "captura")

    for item in fuente.leer_indice():
        pdf_path = fuente.ruta_raw() / item.archivo
        with fitz.open(pdf_path) as doc:
            assert doc.page_count > 0


def test_documentos_referencian_actuaciones_existentes(tmp_path: Path):
    _manifest_path, manifest = _ingestar(tmp_path)
    actuaciones_ids = {a.id for a in manifest.actuaciones}

    for documento in manifest.documentos:
        assert documento.actuacion_id in actuaciones_ids
