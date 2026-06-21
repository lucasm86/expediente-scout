from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app
from expediente_scout.pipeline.clasificar_playbook import (
    cargar_indice_pjn,
    clasificar_indice_playbook,
)


def test_paso12_pipeline_clasifica_indice_y_escribe_json(tmp_path: Path) -> None:
    indice_path = tmp_path / "indice.json"
    output_path = tmp_path / "clasificacion_playbook.json"

    indice_path.write_text(
        json.dumps(
            [
                {
                    "orden": 1,
                    "fecha": "2024-05-13",
                    "descripcion": "Promueve demanda",
                    "archivo": "001.pdf",
                    "sha256": "a",
                },
                {
                    "orden": 2,
                    "fecha": "2026-06-19",
                    "descripcion": "Dación en pago y solicita transferencia",
                    "archivo": "002.pdf",
                    "sha256": "b",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resultado = clasificar_indice_playbook(
        indice_path=indice_path,
        playbook_id="ordinario_v1",
        output_path=output_path,
    )

    assert resultado.total_actuaciones == 2
    assert resultado.total_con_hito == 2
    assert resultado.total_leer_completo == 2
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["playbook_id"] == "ordinario_v1"
    assert len(data["actuaciones"]) == 2


def test_paso12_cargar_indice_rechaza_raiz_no_lista(tmp_path: Path) -> None:
    indice_path = tmp_path / "indice.json"
    indice_path.write_text('{"documentos": []}', encoding="utf-8")

    try:
        cargar_indice_pjn(indice_path)
    except ValueError as exc:
        assert "debe ser una lista" in str(exc)
    else:
        raise AssertionError("Debió rechazar índice con raíz no lista.")


def test_paso12_cli_clasificar_playbook(tmp_path: Path) -> None:
    runner = CliRunner()

    indice_path = tmp_path / "indice.json"
    output_path = tmp_path / "salida" / "clasificacion_playbook.json"

    indice_path.write_text(
        json.dumps(
            [
                {
                    "orden": 1,
                    "fecha": "2024-05-13",
                    "descripcion": "Contesta demanda",
                    "archivo": "001.pdf",
                    "sha256": "a",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "clasificar-playbook",
            "--indice",
            str(indice_path),
            "--output",
            str(output_path),
            "--playbook",
            "ordinario_v1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Clasificación playbook: ok" in result.output
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["total_actuaciones"] == 1
    assert data["total_con_hito"] == 1
