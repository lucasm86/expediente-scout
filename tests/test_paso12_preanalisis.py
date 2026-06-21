from __future__ import annotations

import json
from pathlib import Path

import fitz

from expediente_scout.pipeline.preanalisis import ejecutar_preanalisis


def crear_pdf(path: Path, texto: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), texto)
    doc.save(path)
    doc.close()


def test_paso12_ejecutar_preanalisis_completo(tmp_path: Path) -> None:
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

    resultado = ejecutar_preanalisis(
        indice_path=indice_path,
        raw_dir=raw_dir,
        output_dir=output_dir,
        playbook_id="ordinario_v1",
    )

    assert resultado.total_actuaciones == 2
    assert resultado.total_con_hito == 2
    assert resultado.total_seleccionadas == 2
    assert resultado.total_extraidas == 2
    assert resultado.total_bloques >= 1

    assert resultado.clasificacion_path.exists()
    assert resultado.plan_lectura_path.exists()
    assert resultado.plan_lectura_resuelto_path.exists()
    assert resultado.extraccion_indice_path.exists()
    assert resultado.paquete_indice_path.exists()
    assert resultado.mapa_general_path.exists()

    indice_paquete = json.loads(resultado.paquete_indice_path.read_text(encoding="utf-8"))

    assert indice_paquete["total_documentos"] == 2
    assert indice_paquete["total_bloques"] >= 1

    mapa = resultado.mapa_general_path.read_text(encoding="utf-8")
    assert "Mapa general del paquete de análisis" in mapa
