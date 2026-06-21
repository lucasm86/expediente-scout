from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from expediente_scout.analisis.clasificador_playbook import clasificar_indice
from expediente_scout.playbooks.loader import load_playbook


@dataclass(frozen=True)
class ResultadoClasificacionPlaybook:
    indice_path: Path
    output_path: Path
    playbook_id: str
    total_actuaciones: int
    total_con_hito: int
    total_leer_completo: int


def cargar_indice_pjn(indice_path: Path) -> list[dict[str, Any]]:
    if not indice_path.exists():
        raise FileNotFoundError(f"No existe índice PJN: {indice_path}")

    data = json.loads(indice_path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("El índice PJN debe ser una lista de actuaciones.")

    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"La actuación #{i} del índice no es un objeto.")

    return data


def clasificar_indice_playbook(
    *,
    indice_path: Path,
    playbook_id: str,
    output_path: Path,
) -> ResultadoClasificacionPlaybook:
    indice = cargar_indice_pjn(indice_path)
    playbook = load_playbook(playbook_id)

    resultado = clasificar_indice(indice, playbook)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ResultadoClasificacionPlaybook(
        indice_path=indice_path,
        output_path=output_path,
        playbook_id=playbook.id,
        total_actuaciones=int(resultado["total_actuaciones"]),
        total_con_hito=int(resultado["total_con_hito"]),
        total_leer_completo=int(resultado["total_leer_completo"]),
    )
