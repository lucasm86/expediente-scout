from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from expediente_scout.cli import app
from expediente_scout.pipeline.entregar import (
    LockActivo,
    adquirir_lock,
    exportar_pdf_informe,
    liberar_lock,
    partir_mensaje,
    preparar_entrega,
)


def _crear_informe(root: Path, jurisdiccion: str = "pjn", numero: str = "1010", anio: int = 2024) -> Path:
    reports = root / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    texto = "\n\n".join(
        [
            "# Informe del expediente",
            "## 1. Identificación del expediente\nExpediente pjn-1010-2024.",
            "## 2. Resumen ejecutivo\nTexto de prueba con fuentes internas [act-0001].",
            "## 3. Información insuficiente / no determinable\nInformación insuficiente.",
        ]
    )
    md = reports / "informe.md"
    md.write_text(texto, encoding="utf-8")
    return md


def test_exportar_pdf_genera_archivo(tmp_path: Path) -> None:
    _crear_informe(tmp_path)
    pdf = exportar_pdf_informe(tmp_path, "pjn", "1010", 2024)
    assert pdf.exists()
    assert pdf.suffix == ".pdf"
    assert pdf.stat().st_size > 0


def test_partir_mensaje_respeta_limite() -> None:
    texto = "A" * 90 + " " + "B" * 90 + "\n\n" + "C" * 90
    partes = partir_mensaje(texto, limite=100)
    assert len(partes) >= 3
    assert all(len(p) <= 100 for p in partes)


def test_lock_impide_concurrencia(tmp_path: Path) -> None:
    lock = adquirir_lock(tmp_path, "pjn", "1010", 2024)
    try:
        with pytest.raises(LockActivo):
            adquirir_lock(tmp_path, "pjn", "1010", 2024)
    finally:
        liberar_lock(lock)
    assert not lock.exists()


def test_preparar_entrega_crea_json(tmp_path: Path) -> None:
    _crear_informe(tmp_path)
    entrega = preparar_entrega(tmp_path, "pjn", "1010", 2024, "whatsapp://preview", limite_mensaje=120)
    assert entrega.ruta_json.exists()
    assert entrega.ruta_pdf.exists()
    data = json.loads(entrega.ruta_json.read_text(encoding="utf-8"))
    assert data["enviado"] is False
    assert data["destino"] == "whatsapp://preview"
    assert data["mensaje_chunks"]
    assert all(len(chunk) <= 120 for chunk in data["mensaje_chunks"])


def test_cli_exportar_y_entregar(tmp_path: Path) -> None:
    _crear_informe(tmp_path)
    runner = CliRunner()
    r1 = runner.invoke(app, ["exportar-pdf", "--root", str(tmp_path), "--jurisdiccion", "pjn", "--numero", "1010", "--anio", "2024"])
    assert r1.exit_code == 0, r1.output
    assert "PDF:" in r1.output
    r2 = runner.invoke(app, ["entregar", "--root", str(tmp_path), "--jurisdiccion", "pjn", "--numero", "1010", "--anio", "2024", "--destino", "whatsapp://preview", "--limite-mensaje", "120"])
    assert r2.exit_code == 0, r2.output
    assert "Entrega preparada: sí" in r2.output
    assert "Enviado: no" in r2.output
