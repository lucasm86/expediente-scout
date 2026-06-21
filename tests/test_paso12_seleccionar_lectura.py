from __future__ import annotations

import json
from pathlib import Path

from expediente_scout.pipeline.seleccionar_lectura import (
    cargar_clasificacion_playbook,
    generar_plan_lectura,
    seleccionar_lectura_desde_clasificacion,
)


def test_paso12_selecciona_altas_y_accesorias() -> None:
    clasificacion = {
        "playbook_id": "ordinario_v1",
        "actuaciones": [
            {
                "orden": 1,
                "fecha": "2026-06-19",
                "descripcion": "Dación en pago",
                "archivo": "001.pdf",
                "sha256": "a",
                "hitos_detectados": ["ejecucion_sentencia"],
                "relevancia": "alta",
                "leer_completo": True,
                "motivo": "match",
            },
            {
                "orden": 2,
                "fecha": "2026-06-19",
                "descripcion": "EN LETRA",
                "archivo": "002.pdf",
                "sha256": "b",
                "hitos_detectados": [],
                "relevancia": "accesoria",
                "leer_completo": False,
                "motivo": "sin match",
            },
        ],
    }

    plan = seleccionar_lectura_desde_clasificacion(clasificacion)

    assert plan["total_actuaciones"] == 2
    assert plan["total_seleccionadas"] == 1
    assert plan["total_accesorias"] == 1
    assert plan["seleccionadas"][0]["archivo"] == "001.pdf"
    assert plan["accesorias"][0]["archivo"] == "002.pdf"


def test_paso12_generar_plan_lectura_escribe_json(tmp_path: Path) -> None:
    clasificacion_path = tmp_path / "clasificacion.json"
    output_path = tmp_path / "plan_lectura.json"

    clasificacion_path.write_text(
        json.dumps(
            {
                "playbook_id": "ordinario_v1",
                "actuaciones": [
                    {
                        "orden": 1,
                        "fecha": "2024-05-13",
                        "descripcion": "Promueve demanda",
                        "archivo": "001.pdf",
                        "sha256": "a",
                        "hitos_detectados": ["demanda_interpuesta"],
                        "relevancia": "alta",
                        "leer_completo": True,
                        "motivo": "match",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resultado = generar_plan_lectura(
        clasificacion_path=clasificacion_path,
        output_path=output_path,
    )

    assert resultado.total_actuaciones == 1
    assert resultado.total_seleccionadas == 1
    assert resultado.total_accesorias == 0
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["seleccionadas"][0]["archivo"] == "001.pdf"


def test_paso12_cargar_clasificacion_rechaza_sin_actuaciones(tmp_path: Path) -> None:
    path = tmp_path / "clasificacion.json"
    path.write_text('{"playbook_id": "ordinario_v1"}', encoding="utf-8")

    try:
        cargar_clasificacion_playbook(path)
    except ValueError as exc:
        assert "actuaciones" in str(exc)
    else:
        raise AssertionError("Debió rechazar clasificación sin actuaciones.")
