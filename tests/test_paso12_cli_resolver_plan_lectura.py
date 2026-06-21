from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app


def test_paso12_cli_resolver_plan_lectura(tmp_path: Path) -> None:
    runner = CliRunner()

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "001.pdf").write_bytes(b"%PDF fake selected")
    (raw_dir / "002.pdf").write_bytes(b"%PDF fake accessory")

    plan_path = tmp_path / "plan_lectura.json"
    output_path = tmp_path / "plan_lectura_resuelto.json"

    plan_path.write_text(
        json.dumps(
            {
                "playbook_id": "ordinario_v1",
                "total_actuaciones": 2,
                "seleccionadas": [
                    {
                        "orden": 1,
                        "fecha": "2026-06-19",
                        "descripcion": "Dación en pago",
                        "archivo": "001.pdf",
                        "sha256": "a",
                        "hitos_detectados": ["ejecucion_sentencia"],
                        "relevancia": "alta",
                        "leer_completo": True,
                    }
                ],
                "accesorias": [
                    {
                        "orden": 2,
                        "fecha": "2026-06-19",
                        "descripcion": "Comprobante",
                        "archivo": "002.pdf",
                        "sha256": "b",
                        "hitos_detectados": [],
                        "relevancia": "accesoria",
                        "leer_completo": False,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "resolver-plan-lectura",
            "--plan",
            str(plan_path),
            "--raw-dir",
            str(raw_dir),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Plan de lectura resuelto: ok" in result.output
    assert "Seleccionadas: 1" in result.output
    assert "Accesorias: 1" in result.output
    assert "Faltantes: 0" in result.output
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["total_seleccionadas"] == 1
    assert data["total_accesorias"] == 1
    assert data["total_faltantes"] == 0
    assert data["seleccionadas"][0]["pdf_existe"] is True
    assert data["seleccionadas"][0]["pdf_path"].endswith("001.pdf")
