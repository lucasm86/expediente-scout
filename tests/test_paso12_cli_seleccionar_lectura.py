from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app


def test_paso12_cli_seleccionar_lectura(tmp_path: Path) -> None:
    runner = CliRunner()

    clasificacion_path = tmp_path / "clasificacion_playbook.json"
    output_path = tmp_path / "plan_lectura.json"

    clasificacion_path.write_text(
        json.dumps(
            {
                "playbook_id": "ordinario_v1",
                "actuaciones": [
                    {
                        "orden": 1,
                        "fecha": "2026-06-19",
                        "descripcion": "Dación en pago",
                        "archivo": "001.pdf",
                        "sha256": "a",
                        "hitos_detectados": ["ejecucion_sentencia"],
                        "relevancia": "alta",
                        "leer_completo": True,
                        "motivo": "match",
                    },
                    {
                        "orden": 2,
                        "fecha": "2026-06-19",
                        "descripcion": "Comprobante",
                        "archivo": "002.pdf",
                        "sha256": "b",
                        "hitos_detectados": [],
                        "relevancia": "accesoria",
                        "leer_completo": False,
                        "motivo": "sin match",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "seleccionar-lectura",
            "--clasificacion",
            str(clasificacion_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Plan de lectura: ok" in result.output
    assert "Seleccionadas: 1" in result.output
    assert "Accesorias: 1" in result.output
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["total_actuaciones"] == 2
    assert data["total_seleccionadas"] == 1
    assert data["total_accesorias"] == 1
    assert data["seleccionadas"][0]["archivo"] == "001.pdf"
    assert data["accesorias"][0]["archivo"] == "002.pdf"
