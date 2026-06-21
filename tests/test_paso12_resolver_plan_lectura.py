from __future__ import annotations

import json
from pathlib import Path

from expediente_scout.pipeline.resolver_plan_lectura import (
    cargar_plan_lectura,
    generar_plan_lectura_resuelto,
    indexar_pdfs_por_nombre,
)


def test_paso12_resuelve_rutas_de_pdfs(tmp_path: Path) -> None:
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

    resultado = generar_plan_lectura_resuelto(
        plan_path=plan_path,
        raw_dir=raw_dir,
        output_path=output_path,
    )

    assert resultado.total_seleccionadas == 1
    assert resultado.total_accesorias == 1
    assert resultado.total_faltantes == 0
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["total_pdfs_raw"] == 2
    assert data["seleccionadas"][0]["pdf_existe"] is True
    assert data["seleccionadas"][0]["pdf_path"].endswith("001.pdf")
    assert data["accesorias"][0]["pdf_existe"] is True
    assert data["accesorias"][0]["pdf_path"].endswith("002.pdf")


def test_paso12_strict_rechaza_pdf_faltante(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    plan_path = tmp_path / "plan_lectura.json"
    output_path = tmp_path / "plan_lectura_resuelto.json"

    plan_path.write_text(
        json.dumps(
            {
                "playbook_id": "ordinario_v1",
                "total_actuaciones": 1,
                "seleccionadas": [
                    {
                        "orden": 1,
                        "fecha": "2026-06-19",
                        "descripcion": "Dación en pago",
                        "archivo": "faltante.pdf",
                        "sha256": "a",
                        "hitos_detectados": ["ejecucion_sentencia"],
                        "relevancia": "alta",
                        "leer_completo": True,
                    }
                ],
                "accesorias": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    try:
        generar_plan_lectura_resuelto(
            plan_path=plan_path,
            raw_dir=raw_dir,
            output_path=output_path,
            strict=True,
        )
    except FileNotFoundError as exc:
        assert "PDFs faltantes" in str(exc)
    else:
        raise AssertionError("Debió fallar por PDF faltante.")


def test_paso12_cargar_plan_rechaza_sin_seleccionadas(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text('{"accesorias": []}', encoding="utf-8")

    try:
        cargar_plan_lectura(path)
    except ValueError as exc:
        assert "seleccionadas" in str(exc)
    else:
        raise AssertionError("Debió rechazar plan sin seleccionadas.")


def test_paso12_indexar_rechaza_raw_inexistente(tmp_path: Path) -> None:
    try:
        indexar_pdfs_por_nombre(tmp_path / "raw_inexistente")
    except FileNotFoundError as exc:
        assert "No existe carpeta raw" in str(exc)
    else:
        raise AssertionError("Debió rechazar raw inexistente.")
