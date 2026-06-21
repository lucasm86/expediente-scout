from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


HITOS_ESTADO_ACTUAL_DEFAULT = [
    "ejecucion_sentencia",
    "honorarios",
    "apelacion",
]


PROMPT_ESTADO_ACTUAL = """# Instrucciones para análisis de estado actual

Actuá como asistente jurídico para revisión de expediente judicial argentino.

Tu tarea es analizar exclusivamente el material provisto y producir un informe de estado actual del expediente.

## Reglas

1. No inventes datos que no estén en el material.
2. Si falta información, indicá expresamente qué falta.
3. Priorizá el estado procesal actual por sobre antecedentes remotos.
4. Diferenciá claramente:
   - hechos procesales verificados;
   - inferencias razonables;
   - dudas o puntos a revisar.
5. Citá siempre el documento, fecha y orden de actuación cuando fundes una conclusión.
6. No analices en profundidad demanda, contestación o prueba salvo que sea indispensable para explicar el estado actual.

## Salida esperada

Generá un informe con estas secciones:

1. Estado procesal actual.
2. Últimos movimientos relevantes.
3. Pagos, giros, transferencias, CBU y dación en pago.
4. Honorarios y apelaciones de honorarios.
5. Riesgos o pendientes inmediatos.
6. Próximos pasos sugeridos.
7. Checklist operativo.
"""


@dataclass(frozen=True)
class ResultadoEstadoActual:
    paquete_indice_path: Path
    output_dir: Path
    indice_path: Path
    prompt_path: Path
    material_path: Path
    input_llm_path: Path
    total_bloques: int
    total_caracteres_material: int


def cargar_indice_paquete(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe índice de paquete de análisis: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("El índice del paquete debe ser un objeto JSON.")

    if not isinstance(data.get("bloques"), list):
        raise ValueError("El índice del paquete debe incluir una lista 'bloques'.")

    if not data.get("mapa_general"):
        raise ValueError("El índice del paquete debe incluir 'mapa_general'.")

    return data


def seleccionar_bloques(
    indice_paquete: dict[str, Any],
    *,
    hitos: list[str] | None = None,
) -> list[dict[str, Any]]:
    hitos_objetivo = hitos or HITOS_ESTADO_ACTUAL_DEFAULT
    bloques = indice_paquete["bloques"]

    seleccionados: list[dict[str, Any]] = []

    for hito in hitos_objetivo:
        for bloque in bloques:
            if bloque.get("hito") == hito:
                seleccionados.append(bloque)
                break

    return seleccionados


def _leer_archivo(path_raw: str | Path) -> str:
    path = Path(path_raw)
    if not path.exists():
        raise FileNotFoundError(f"No existe archivo del paquete: {path}")
    return path.read_text(encoding="utf-8")


def generar_material_estado_actual(
    indice_paquete: dict[str, Any],
    *,
    bloques: list[dict[str, Any]],
) -> str:
    partes = [
        "# Material para análisis de estado actual",
        "",
        "Este archivo reúne el mapa general y los bloques prioritarios para determinar el estado procesal actual.",
        "",
        "---",
        "",
        "# Mapa general",
        "",
        _leer_archivo(indice_paquete["mapa_general"]).strip(),
        "",
        "---",
        "",
        "# Bloques prioritarios",
        "",
    ]

    for bloque in bloques:
        partes.extend(
            [
                "---",
                "",
                f"# Bloque incluido: {bloque.get('hito')}",
                "",
                f"- Archivo fuente: {bloque.get('archivo')}",
                f"- Documentos: {bloque.get('documentos')}",
                f"- Páginas: {bloque.get('paginas')}",
                f"- Caracteres: {bloque.get('caracteres')}",
                f"- Tokens aproximados: {bloque.get('tokens_aprox')}",
                "",
                _leer_archivo(bloque["archivo"]).strip(),
                "",
            ]
        )

    return "\n".join(partes).strip() + "\n"


def generar_estado_actual(
    *,
    paquete_indice_path: Path,
    output_dir: Path,
    hitos: list[str] | None = None,
) -> ResultadoEstadoActual:
    indice_paquete = cargar_indice_paquete(paquete_indice_path)
    bloques = seleccionar_bloques(indice_paquete, hitos=hitos)

    if not bloques:
        raise ValueError("No se encontraron bloques para estado actual.")

    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = output_dir / "00_prompt_estado_actual.md"
    material_path = output_dir / "01_material_estado_actual.md"
    input_llm_path = output_dir / "02_input_llm_estado_actual.md"
    indice_path = output_dir / "indice_estado_actual.json"

    prompt_path.write_text(PROMPT_ESTADO_ACTUAL.strip() + "\n", encoding="utf-8")

    material = generar_material_estado_actual(
        indice_paquete,
        bloques=bloques,
    )
    material_path.write_text(material, encoding="utf-8")

    input_llm = (
        "# Input completo para LLM - Estado actual del expediente\n\n"
        "## Prompt de análisis\n\n"
        + PROMPT_ESTADO_ACTUAL.strip()
        + "\n\n---\n\n"
        "## Material documental\n\n"
        + material.strip()
        + "\n"
    )
    input_llm_path.write_text(input_llm, encoding="utf-8")

    indice_estado = {
        "paquete_indice_path": str(paquete_indice_path),
        "output_dir": str(output_dir),
        "prompt_path": str(prompt_path),
        "material_path": str(material_path),
        "input_llm_path": str(input_llm_path),
        "hitos_incluidos": [b.get("hito") for b in bloques],
        "total_bloques": len(bloques),
        "total_caracteres_material": len(material),
        "tokens_aprox_material": round(len(material) / 4),
        "bloques": bloques,
    }

    indice_path.write_text(
        json.dumps(indice_estado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ResultadoEstadoActual(
        paquete_indice_path=paquete_indice_path,
        output_dir=output_dir,
        indice_path=indice_path,
        prompt_path=prompt_path,
        material_path=material_path,
        input_llm_path=input_llm_path,
        total_bloques=len(bloques),
        total_caracteres_material=len(material),
    )
