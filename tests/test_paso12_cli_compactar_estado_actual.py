from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app


def test_paso12_cli_compactar_estado_actual(tmp_path: Path) -> None:
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

```text
SOLICITA SE INTIME
Solicito se intime al pago de $2.500.000.
CBU: 0170026840000007269596
Banco BBVA.
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

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "compactar-estado-actual",
            "--indice-estado",
            str(indice_estado),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Compactación estado actual: ok" in result.output
    assert "Documentos: 1" in result.output
    assert "Resumen operativo: 1" in result.output
    assert (output_dir / "04_input_llm_estado_actual_compacto.md").exists()
