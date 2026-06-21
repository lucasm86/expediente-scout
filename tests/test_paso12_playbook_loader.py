from __future__ import annotations

from pathlib import Path

import pytest

from expediente_scout.playbooks.loader import (
    PlaybookValidationError,
    list_playbooks,
    load_playbook,
    validate_playbook,
)


def test_paso12_lista_playbook_ordinario() -> None:
    assert "ordinario_v1" in list_playbooks()


def test_paso12_carga_playbook_ordinario() -> None:
    playbook = load_playbook("ordinario_v1")

    assert playbook.id == "ordinario_v1"
    assert playbook.nombre
    assert playbook.version == "0.1"
    assert len(playbook.hitos) >= 10
    assert playbook.reglas_de_omision


def test_paso12_playbook_tiene_hitos_clave() -> None:
    playbook = load_playbook("ordinario_v1")
    hito_ids = {h["id"] for h in playbook.hitos}

    expected = {
        "demanda_interpuesta",
        "litis_integrada",
        "contestacion_demanda",
        "apertura_prueba",
        "certificacion_prueba",
        "alegatos",
        "autos_para_sentencia",
        "sentencia",
        "apelacion",
        "ejecucion_sentencia",
        "honorarios",
    }

    assert expected.issubset(hito_ids)


def test_paso12_validador_rechaza_playbook_incompleto() -> None:
    with pytest.raises(PlaybookValidationError):
        validate_playbook({"id": "roto"})


def test_paso12_carga_desde_directorio_temporal(tmp_path: Path) -> None:
    original = load_playbook("ordinario_v1")
    target_dir = tmp_path / "playbooks"
    target_dir.mkdir()
    target = target_dir / "ordinario_v1.yaml"
    target.write_text(original.path.read_text(encoding="utf-8"), encoding="utf-8")

    loaded = load_playbook("ordinario_v1", base_dir=target_dir)

    assert loaded.id == "ordinario_v1"
    assert loaded.path == target
