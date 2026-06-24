from __future__ import annotations

import json
from pathlib import Path

from expediente_scout.pipeline.compactar_estado_actual import compactar_estado_actual


def bloque_doc(hito: str) -> str:
    fence = "```"
    return f"""# Bloque

## Documento orden 24 - 2026-05-11

{fence}text
Orden: 24
Fecha: 2026-05-11
Archivo: 0024.pdf
PDF: /tmp/0024.pdf
Texto: /tmp/0024.txt
Páginas: 1
Caracteres: 500
Hitos: {hito}
Descripción: Detalle: SOLICITA TRANSFERENCIA
{fence}

### Texto extraído

{fence}text
Solicita transferencia por $2.500.000.
CBU 0170026840000007269596.
{fence}
"""


def test_paso12_deduplica_documentos_repetidos_en_bloques_distintos(tmp_path: Path) -> None:
    prompt = tmp_path / "00_prompt_estado_actual.md"
    bloque_a = tmp_path / "01_ejecucion_sentencia.md"
    bloque_b = tmp_path / "02_honorarios.md"
    indice_estado = tmp_path / "indice_estado_actual.json"
    output_dir = tmp_path / "compacto"

    prompt.write_text("# Prompt", encoding="utf-8")
    bloque_a.write_text(bloque_doc("ejecucion_sentencia"), encoding="utf-8")
    bloque_b.write_text(bloque_doc("honorarios"), encoding="utf-8")

    indice_estado.write_text(
        json.dumps(
            {
                "prompt_path": str(prompt),
                "material_path": str(tmp_path / "material.md"),
                "bloques": [
                    {"hito": "ejecucion_sentencia", "archivo": str(bloque_a)},
                    {"hito": "honorarios", "archivo": str(bloque_b)},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resultado = compactar_estado_actual(
        indice_estado_path=indice_estado,
        output_dir=output_dir,
    )

    assert resultado.total_documentos == 1

    referencias = json.loads(resultado.referencias_path.read_text(encoding="utf-8"))
    assert len(referencias) == 1
    assert referencias[0]["orden"] == 24
    assert sorted(referencias[0]["hitos"]) == ["ejecucion_sentencia", "honorarios"]

    resumen = resultado.resumen_compacto_path.read_text(encoding="utf-8")
    assert resumen.count("## Orden 24") == 1
