from __future__ import annotations

from expediente_scout.analisis.clasificador_playbook import (
    clasificar_actuacion,
    clasificar_indice,
    normalizar_texto,
)
from expediente_scout.playbooks.loader import load_playbook


def test_paso12_normaliza_tildes_y_mayusculas() -> None:
    assert normalizar_texto("DACIÓN EN PAGO") == "dacion en pago"


def test_paso12_clasifica_demanda() -> None:
    playbook = load_playbook("ordinario_v1")

    item = {
        "orden": 1,
        "fecha": "2024-05-13",
        "descripcion": "Detalle: Promueve demanda ordinaria",
        "archivo": "001_demanda.pdf",
        "sha256": "abc",
    }

    result = clasificar_actuacion(item, playbook)

    assert "demanda_interpuesta" in result.hitos_detectados
    assert result.relevancia == "alta"
    assert result.leer_completo is True


def test_paso12_clasifica_ejecucion_y_honorarios() -> None:
    playbook = load_playbook("ordinario_v1")

    item = {
        "orden": 20,
        "fecha": "2026-06-19",
        "descripcion": "Detalle: Dación en pago. Solicita regulación y pago de honorarios",
        "archivo": "020_pago.pdf",
        "sha256": "abc",
    }

    result = clasificar_actuacion(item, playbook)

    assert "ejecucion_sentencia" in result.hitos_detectados
    assert "honorarios" in result.hitos_detectados
    assert result.relevancia == "alta"
    assert result.leer_completo is True


def test_paso12_clasifica_accesorio_si_no_hay_hito() -> None:
    playbook = load_playbook("ordinario_v1")

    item = {
        "orden": 2,
        "fecha": "2024-05-14",
        "descripcion": "Detalle: EN LETRA",
        "archivo": "002_en_letra.pdf",
        "sha256": "abc",
    }

    result = clasificar_actuacion(item, playbook)

    assert result.hitos_detectados == []
    assert result.relevancia == "accesoria"
    assert result.leer_completo is False


def test_paso12_clasifica_indice_completo() -> None:
    playbook = load_playbook("ordinario_v1")

    indice = [
        {
            "orden": 1,
            "fecha": "2024-05-13",
            "descripcion": "Promueve demanda",
            "archivo": "001.pdf",
            "sha256": "a",
        },
        {
            "orden": 2,
            "fecha": "2024-06-01",
            "descripcion": "Contesta demanda y opone excepciones",
            "archivo": "002.pdf",
            "sha256": "b",
        },
        {
            "orden": 3,
            "fecha": "2025-01-01",
            "descripcion": "EN DESPACHO",
            "archivo": "003.pdf",
            "sha256": "c",
        },
    ]

    result = clasificar_indice(indice, playbook)

    assert result["playbook_id"] == "ordinario_v1"
    assert result["total_actuaciones"] == 3
    assert result["total_con_hito"] == 2
    assert result["total_leer_completo"] == 2
    assert len(result["actuaciones"]) == 3
