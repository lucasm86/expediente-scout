from __future__ import annotations

import json
from pathlib import Path

from expediente_scout.pipeline.generar_estado_actual import (
    cargar_indice_paquete,
    generar_estado_actual,
    seleccionar_bloques,
)


def test_paso12_generar_estado_actual(tmp_path: Path) -> None:
    mapa = tmp_path / "00_mapa_general.md"
    bloque = tmp_path / "01_ejecucion_sentencia.md"
    indice_paquete = tmp_path / "indice_paquete.json"
    output_dir = tmp_path / "estado_actual"

    mapa.write_text("# Mapa general\n\nOrden 1 | Dación en pago", encoding="utf-8")
    bloque.write_text("# Bloque: ejecucion_sentencia\n\nDación en pago acreditada", encoding="utf-8")

    indice_paquete.write_text(
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

    resultado = generar_estado_actual(
        paquete_indice_path=indice_paquete,
        output_dir=output_dir,
    )

    assert resultado.total_bloques == 1
    assert resultado.indice_path.exists()
    assert resultado.prompt_path.exists()
    assert resultado.material_path.exists()
    assert resultado.input_llm_path.exists()

    material = resultado.material_path.read_text(encoding="utf-8")
    assert "Mapa general" in material
    assert "Dación en pago acreditada" in material
    assert "Bloque incluido: ejecucion_sentencia" in material

    input_llm = resultado.input_llm_path.read_text(encoding="utf-8")
    assert "Input completo para LLM" in input_llm
    assert "Prompt de análisis" in input_llm
    assert r"\n\n## Prompt de análisis" not in input_llm
    assert "expediente\n\n## Prompt de análisis" in input_llm
    assert "Material documental" in input_llm
    assert "Dación en pago acreditada" in input_llm

    indice = json.loads(resultado.indice_path.read_text(encoding="utf-8"))
    assert indice["hitos_incluidos"] == ["ejecucion_sentencia"]
    assert indice["total_bloques"] == 1


def test_paso12_seleccionar_bloques_respeta_orden() -> None:
    indice = {
        "bloques": [
            {"hito": "honorarios", "archivo": "/tmp/honorarios.md"},
            {"hito": "ejecucion_sentencia", "archivo": "/tmp/ejecucion.md"},
            {"hito": "apelacion", "archivo": "/tmp/apelacion.md"},
        ]
    }

    seleccionados = seleccionar_bloques(
        indice,
        hitos=["ejecucion_sentencia", "honorarios"],
    )

    assert [b["hito"] for b in seleccionados] == ["ejecucion_sentencia", "honorarios"]


def test_paso12_rechaza_indice_sin_bloques(tmp_path: Path) -> None:
    path = tmp_path / "indice.json"
    path.write_text('{"mapa_general": "/tmp/mapa.md"}', encoding="utf-8")

    try:
        cargar_indice_paquete(path)
    except ValueError as exc:
        assert "bloques" in str(exc)
    else:
        raise AssertionError("Debió rechazar índice sin bloques.")
