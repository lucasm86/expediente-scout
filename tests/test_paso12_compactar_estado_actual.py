from __future__ import annotations

import json
from pathlib import Path

import yaml

from expediente_scout.pipeline.compactar_estado_actual import (
    DocumentoEstadoActual,
    compactar_estado_actual,
    decidir_modo_inclusion,
)


def doc(descripcion: str) -> DocumentoEstadoActual:
    return DocumentoEstadoActual(
        orden=1,
        fecha="2026-06-19",
        descripcion=descripcion,
        archivo="doc.pdf",
        pdf="/tmp/doc.pdf",
        texto_path="/tmp/doc.txt",
        paginas=1,
        caracteres=100,
        hitos=["ejecucion_sentencia"],
        texto="Solicito se intime al pago de $2.500.000. CBU 0170026840000007269596. Banco BBVA.",
        bloque_hito="ejecucion_sentencia",
    )


def test_paso12_decide_modo_por_descripcion() -> None:
    policy = yaml.safe_load(
        Path("config/document_policies/estado_actual_v1.yaml").read_text(encoding="utf-8")
    )

    assert decidir_modo_inclusion(doc("Detalle: DEMANDA FIRMADA"), policy) == "texto_completo"
    assert decidir_modo_inclusion(doc("Detalle: LIBRAMIENTO DE GIRO ACTOR"), policy) == "extracto_relevante"
    assert decidir_modo_inclusion(doc("Detalle: SOLICITA SE INTIME"), policy) == "resumen_operativo"
    assert decidir_modo_inclusion(doc("Detalle: ENVIO DEO: BBVA"), policy) == "solo_metadata"


def test_paso12_compactar_estado_actual(tmp_path: Path) -> None:
    prompt = tmp_path / "00_prompt_estado_actual.md"
    bloque = tmp_path / "01_ejecucion_sentencia.md"
    indice_estado = tmp_path / "indice_estado_actual.json"
    output_dir = tmp_path / "compacto"

    prompt.write_text("# Prompt\n\nAnalizar estado actual.", encoding="utf-8")

    bloque.write_text(
        """# Bloque: ejecucion_sentencia

## Documento orden 1 - 2026-06-19

```text
Orden: 1
Fecha: 2026-06-19
Archivo: 0001.pdf
PDF: /tmp/0001.pdf
Texto: /tmp/0001.txt
Páginas: 1
Caracteres: 500
Hitos: ejecucion_sentencia
Descripción: Detalle: SOLICITA SE INTIME
```

### Texto extraído

```text id="gjf1em"
SOLICITA SE INTIME
Solicito se intime al pago de $2.500.000.
CBU: 0170026840000007269596
Banco BBVA.
```

## Documento orden 2 - 2026-06-20

```text id="ng3uga"
Orden: 2
Fecha: 2026-06-20
Archivo: 0002.pdf
PDF: /tmp/0002.pdf
Texto: /tmp/0002.txt
Páginas: 1
Caracteres: 700
Hitos: ejecucion_sentencia
Descripción: Detalle: LIBRAMIENTO DE GIRO ACTOR
```

### Texto extraído

```text id="nd7t8j"
Líbrese giro electrónico a la orden del actor por la suma de $2.500.000 en concepto de capital.
```
""",
        encoding="utf-8",
    )

    indice_estado.write_text(
        json.dumps(
            {
                "prompt_path": str(prompt),
                "material_path": str(tmp_path / "material.md"),
                "bloques": [{"hito": "ejecucion_sentencia", "archivo": str(bloque)}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resultado = compactar_estado_actual(
        indice_estado_path=indice_estado,
        output_dir=output_dir,
    )

    assert resultado.total_documentos == 2
    assert resultado.total_resumen_operativo == 1
    assert resultado.total_extracto_relevante == 1

    resumen = resultado.resumen_compacto_path.read_text(encoding="utf-8")
    assert "SOLICITA SE INTIME" in resumen
    assert "0170026840000007269596" in resumen
    assert "Extracto relevante" in resumen
    assert "Líbrese giro electrónico" in resumen

    referencias = json.loads(resultado.referencias_path.read_text(encoding="utf-8"))
    assert referencias[0]["modo_inclusion"] == "resumen_operativo"
    assert referencias[1]["modo_inclusion"] == "extracto_relevante"

    input_compacto = resultado.input_llm_compacto_path.read_text(encoding="utf-8")
    assert "Input compacto para LLM" in input_compacto
    assert "Material compacto" in input_compacto
