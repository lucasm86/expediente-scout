from __future__ import annotations

import json
from pathlib import Path

import fitz
from typer.testing import CliRunner

from expediente_scout.cli import app


def crear_pdf(path: Path, texto: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), texto)
    doc.save(path)
    doc.close()


def test_paso12_cli_extraer_texto_seleccionado(tmp_path: Path) -> None:
    runner = CliRunner()

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    pdf_path = raw_dir / "001.pdf"
    crear_pdf(pdf_path, "Texto procesal extraído")

    plan_path = tmp_path / "plan_lectura_resuelto.json"
    output_dir = tmp_path / "extraccion"

    plan_path.write_text(
        json.dumps(
            {
                "playbook_id": "ordinario_v1",
                "seleccionadas": [
                    {
                        "orden": 1,
                        "fecha": "2026-06-19",
                        "descripcion": "Dación en pago",
                        "archivo": "001.pdf",
                        "pdf_path": str(pdf_path),
                        "hitos_detectados": ["ejecucion_sentencia"],
                        "relevancia": "alta",
                        "leer_completo": True,
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
            "extraer-texto-seleccionado",
            "--plan",
            str(plan_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Extracción de texto seleccionado: ok" in result.output
    assert "Seleccionadas: 1" in result.output
    assert "Extraídas: 1" in result.output
    assert "Errores: 0" in result.output

    indice_path = output_dir / "extraccion_texto.json"
    assert indice_path.exists()

    data = json.loads(indice_path.read_text(encoding="utf-8"))
    assert data["total_seleccionadas"] == 1
    assert data["total_extraidas"] == 1
    assert data["total_errores"] == 0

    texto_path = Path(data["documentos"][0]["texto_path"])
    assert texto_path.exists()
    assert "Texto procesal extraído" in texto_path.read_text(encoding="utf-8")
