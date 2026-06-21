from __future__ import annotations

import json
from pathlib import Path

from expediente_scout.pipeline.generar_paquete_analisis import (
    cargar_extraccion_texto,
    generar_paquete_analisis,
)


def test_paso12_generar_paquete_analisis(tmp_path: Path) -> None:
    texto_path = tmp_path / "texto_001.txt"
    texto_path.write_text("--- Página 1 ---\nDación en pago acreditada", encoding="utf-8")

    extraccion_path = tmp_path / "extraccion_texto.json"
    output_dir = tmp_path / "paquete"

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

    resultado = generar_paquete_analisis(
        extraccion_path=extraccion_path,
        output_dir=output_dir,
    )

    assert resultado.total_documentos == 1
    assert resultado.total_bloques == 1
    assert resultado.indice_path.exists()
    assert resultado.mapa_path.exists()

    indice = json.loads(resultado.indice_path.read_text(encoding="utf-8"))
    assert indice["total_documentos"] == 1
    assert indice["bloques"][0]["hito"] == "ejecucion_sentencia"

    bloque_path = Path(indice["bloques"][0]["archivo"])
    assert bloque_path.exists()
    bloque = bloque_path.read_text(encoding="utf-8")
    assert "Dación en pago acreditada" in bloque
    assert "Orden: 1" in bloque


def test_paso12_rechaza_extraccion_sin_documentos(tmp_path: Path) -> None:
    path = tmp_path / "extraccion.json"
    path.write_text("{}", encoding="utf-8")

    try:
        cargar_extraccion_texto(path)
    except ValueError as exc:
        assert "documentos" in str(exc)
    else:
        raise AssertionError("Debió rechazar extracción sin documentos.")
