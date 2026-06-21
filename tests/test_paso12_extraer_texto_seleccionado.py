from __future__ import annotations

import json
from pathlib import Path

import fitz

from expediente_scout.pipeline.extraer_texto_seleccionado import (
    cargar_plan_resuelto,
    extraer_texto_pdf,
    generar_extraccion_texto,
)


def crear_pdf(path: Path, texto: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), texto)
    doc.save(path)
    doc.close()


def test_paso12_extrae_texto_de_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "documento.pdf"
    crear_pdf(pdf_path, "Hola expediente")

    paginas, texto = extraer_texto_pdf(pdf_path)

    assert paginas == 1
    assert "Hola expediente" in texto
    assert "--- Página 1 ---" in texto


def test_paso12_genera_extraccion_desde_plan_resuelto(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    pdf_path = raw_dir / "001.pdf"
    crear_pdf(pdf_path, "Dación en pago acreditada")

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

    resultado = generar_extraccion_texto(
        plan_path=plan_path,
        output_dir=output_dir,
    )

    assert resultado.total_seleccionadas == 1
    assert resultado.total_extraidas == 1
    assert resultado.total_errores == 0
    assert resultado.indice_path.exists()

    data = json.loads(resultado.indice_path.read_text(encoding="utf-8"))
    doc = data["documentos"][0]

    assert doc["extraido"] is True
    assert doc["paginas"] == 1
    assert doc["caracteres"] > 0
    assert Path(doc["texto_path"]).exists()
    assert "Dación en pago acreditada" in Path(doc["texto_path"]).read_text(encoding="utf-8")


def test_paso12_rechaza_plan_sin_seleccionadas(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text("{}", encoding="utf-8")

    try:
        cargar_plan_resuelto(path)
    except ValueError as exc:
        assert "seleccionadas" in str(exc)
    else:
        raise AssertionError("Debió rechazar plan sin seleccionadas.")


def test_paso12_strict_rechaza_pdf_faltante(tmp_path: Path) -> None:
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
                        "pdf_path": str(tmp_path / "faltante.pdf"),
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

    try:
        generar_extraccion_texto(
            plan_path=plan_path,
            output_dir=output_dir,
            strict=True,
        )
    except FileNotFoundError as exc:
        assert "PDF no encontrado" in str(exc)
    else:
        raise AssertionError("Debió fallar por PDF faltante.")
