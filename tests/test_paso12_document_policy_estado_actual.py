from __future__ import annotations

from pathlib import Path
import yaml


def test_paso12_document_policy_estado_actual_existe_y_es_valida() -> None:
    path = Path("config/document_policies/estado_actual_v1.yaml")

    assert path.exists()

    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert data["id"] == "estado_actual_v1"
    assert "modos_inclusion" in data
    assert "texto_completo" in data["modos_inclusion"]
    assert "extracto_relevante" in data["modos_inclusion"]
    assert "resumen_operativo" in data["modos_inclusion"]
    assert "solo_metadata" in data["modos_inclusion"]

    assert "reglas_por_descripcion" in data
    assert "solicita se intime" in data["reglas_por_descripcion"]["resumen_operativo"]
    assert "cbu actor" in data["reglas_por_descripcion"]["resumen_operativo"]
    assert "demanda firmada" in data["reglas_por_descripcion"]["texto_completo"]

    assert data["salidas"]["input_llm_compacto_md"] == "04_input_llm_estado_actual_compacto.md"
