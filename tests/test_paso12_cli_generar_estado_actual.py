from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app


def test_paso12_cli_generar_estado_actual(tmp_path: Path) -> None:
    runner = CliRunner()

    mapa = tmp_path / "00_mapa_general.md"
    bloque = tmp_path / "01_ejecucion_sentencia.md"
    paquete_indice = tmp_path / "indice_paquete.json"
    output_dir = tmp_path / "estado_actual"

    mapa.write_text("# Mapa general\\n\\nOrden 1 | Dación en pago", encoding="utf-8")
    bloque.write_text("# Bloque: ejecucion_sentencia\\n\\nDación en pago acreditada", encoding="utf-8")

    paquete_indice.write_text(
        json.dumps(
            {
                "playbook_id": "ordinario_v1",
                "mapa_general": str(mapa),
                "bloques": [
                    {
                        "hito": "ejecucion_sentencia",
                        "archivo": str(bloque),
                        "documentos": 1,
                        "paginas": 1,
                        "caracteres": 100,
                        "tokens_aprox": 25,
                        "ordenes": [1],
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
            "generar-estado-actual",
            "--paquete-indice",
            str(paquete_indice),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Estado actual: ok" in result.output
    assert "Bloques: 1" in result.output

    indice_path = output_dir / "indice_estado_actual.json"
    prompt_path = output_dir / "00_prompt_estado_actual.md"
    material_path = output_dir / "01_material_estado_actual.md"

    assert indice_path.exists()
    assert prompt_path.exists()
    assert material_path.exists()

    indice = json.loads(indice_path.read_text(encoding="utf-8"))
    assert indice["hitos_incluidos"] == ["ejecucion_sentencia"]
    assert indice["total_bloques"] == 1

    material = material_path.read_text(encoding="utf-8")
    assert "Dación en pago acreditada" in material
    assert "Bloque incluido: ejecucion_sentencia" in material
