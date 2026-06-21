from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app


def test_paso12_cli_generar_paquete_analisis(tmp_path: Path) -> None:
    runner = CliRunner()

    texto_path = tmp_path / "texto_001.txt"
    texto_path.write_text("--- Página 1 ---\\nDación en pago acreditada", encoding="utf-8")

    extraccion_path = tmp_path / "extraccion_texto.json"
    output_dir = tmp_path / "paquete_analisis"

    extraccion_path.write_text(
        json.dumps(
            {
                "playbook_id": "ordinario_v1",
                "documentos": [
                    {
                        "orden": 1,
                        "fecha": "2026-06-19",
                        "descripcion": "Dación en pago",
                        "archivo": "001.pdf",
                        "pdf_path": "/tmp/raw/001.pdf",
                        "texto_path": str(texto_path),
                        "paginas": 1,
                        "caracteres": 40,
                        "hitos_detectados": ["ejecucion_sentencia"],
                        "relevancia": "alta",
                        "leer_completo": True,
                        "extraido": True,
                        "sin_texto": False,
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
            "generar-paquete-analisis",
            "--extraccion",
            str(extraccion_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Paquete de análisis: ok" in result.output
    assert "Documentos: 1" in result.output
    assert "Bloques: 1" in result.output

    indice_path = output_dir / "indice_paquete.json"
    mapa_path = output_dir / "00_mapa_general.md"

    assert indice_path.exists()
    assert mapa_path.exists()

    indice = json.loads(indice_path.read_text(encoding="utf-8"))
    assert indice["total_documentos"] == 1
    assert indice["total_bloques"] == 1
    assert indice["bloques"][0]["hito"] == "ejecucion_sentencia"

    bloque_path = Path(indice["bloques"][0]["archivo"])
    assert bloque_path.exists()
    assert "Dación en pago acreditada" in bloque_path.read_text(encoding="utf-8")
