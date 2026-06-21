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


def test_paso12_cli_preanalisis(tmp_path: Path) -> None:
    runner = CliRunner()

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    pdf1 = raw_dir / "001_demanda.pdf"
    pdf2 = raw_dir / "002_dacion_pago.pdf"

    crear_pdf(pdf1, "Texto de demanda laboral")
    crear_pdf(pdf2, "Texto de dación en pago")

    indice_path = tmp_path / "indice.json"
    output_dir = tmp_path / "preanalisis"

    indice_path.write_text(
        json.dumps(
            [
                {
                    "orden": 1,
                    "fecha": "2024-06-06",
                    "descripcion": "Detalle: DEMANDA FIRMADA",
                    "archivo": pdf1.name,
                    "sha256": "a",
                },
                {
                    "orden": 2,
                    "fecha": "2026-06-19",
                    "descripcion": "Detalle: DACION EN PAGO",
                    "archivo": pdf2.name,
                    "sha256": "b",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "preanalisis",
            "--indice",
            str(indice_path),
            "--raw-dir",
            str(raw_dir),
            "--output-dir",
            str(output_dir),
            "--playbook",
            "ordinario_v1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Preanálisis: ok" in result.output
    assert "Actuaciones: 2" in result.output
    assert "Con hito: 2" in result.output
    assert "Seleccionadas: 2" in result.output
    assert "Extraídas: 2" in result.output

    assert (output_dir / "clasificacion_playbook.json").exists()
    assert (output_dir / "plan_lectura.json").exists()
    assert (output_dir / "plan_lectura_resuelto.json").exists()
    assert (output_dir / "extraccion_texto_seleccionados" / "extraccion_texto.json").exists()
    assert (output_dir / "paquete_analisis" / "indice_paquete.json").exists()
    assert (output_dir / "paquete_analisis" / "00_mapa_general.md").exists()

    indice_paquete = json.loads(
        (output_dir / "paquete_analisis" / "indice_paquete.json").read_text(encoding="utf-8")
    )

    assert indice_paquete["total_documentos"] == 2
    assert indice_paquete["total_bloques"] >= 1
