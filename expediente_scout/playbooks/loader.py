from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class PlaybookError(Exception):
    """Error base de playbooks."""


class PlaybookNotFoundError(PlaybookError):
    """El playbook solicitado no existe."""


class PlaybookValidationError(PlaybookError):
    """El playbook existe pero no cumple el contrato mínimo."""


@dataclass(frozen=True)
class Playbook:
    """Playbook procesal cargado y validado."""

    id: str
    path: Path
    data: dict[str, Any]

    @property
    def nombre(self) -> str:
        return str(self.data.get("nombre", ""))

    @property
    def version(self) -> str:
        return str(self.data.get("version", ""))

    @property
    def hitos(self) -> list[dict[str, Any]]:
        hitos = self.data.get("hitos", [])
        return hitos if isinstance(hitos, list) else []

    @property
    def reglas_de_omision(self) -> list[dict[str, Any]]:
        reglas = self.data.get("reglas_de_omision", [])
        return reglas if isinstance(reglas, list) else []


DEFAULT_PLAYBOOKS_DIR = Path("config/playbooks")


def list_playbooks(base_dir: Path | str = DEFAULT_PLAYBOOKS_DIR) -> list[str]:
    """Lista IDs de playbooks disponibles en disco."""
    root = Path(base_dir)
    if not root.exists():
        return []

    return sorted(p.stem for p in root.glob("*.yaml") if p.is_file())


def load_playbook(
    playbook_id: str,
    base_dir: Path | str = DEFAULT_PLAYBOOKS_DIR,
) -> Playbook:
    """Carga un playbook por ID desde config/playbooks/<id>.yaml."""
    root = Path(base_dir)
    path = root / f"{playbook_id}.yaml"

    if not path.exists():
        raise PlaybookNotFoundError(f"No existe playbook: {path}")

    return load_playbook_file(path)


def load_playbook_file(path: Path | str) -> Playbook:
    """Carga un playbook desde un archivo YAML concreto."""
    p = Path(path)

    if not p.exists():
        raise PlaybookNotFoundError(f"No existe playbook: {p}")

    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    if data is None:
        data = {}

    if not isinstance(data, dict):
        raise PlaybookValidationError("El playbook debe ser un objeto YAML/dict.")

    validate_playbook(data)

    return Playbook(
        id=str(data["id"]),
        path=p,
        data=data,
    )


def validate_playbook(data: dict[str, Any]) -> None:
    """Valida contrato mínimo de un playbook procesal."""
    required_top_level = [
        "id",
        "nombre",
        "version",
        "principio_general",
        "preguntas_de_control",
        "hitos",
        "reglas_de_omision",
        "salidas",
    ]

    missing = [k for k in required_top_level if k not in data]
    if missing:
        raise PlaybookValidationError(
            f"Faltan claves principales en playbook: {', '.join(missing)}"
        )

    if not isinstance(data["id"], str) or not data["id"].strip():
        raise PlaybookValidationError("El playbook debe tener id string no vacío.")

    if not isinstance(data["hitos"], list) or not data["hitos"]:
        raise PlaybookValidationError("El playbook debe tener una lista no vacía de hitos.")

    if not isinstance(data["preguntas_de_control"], list) or not data["preguntas_de_control"]:
        raise PlaybookValidationError(
            "El playbook debe tener preguntas_de_control como lista no vacía."
        )

    if not isinstance(data["reglas_de_omision"], list):
        raise PlaybookValidationError("reglas_de_omision debe ser una lista.")

    if not isinstance(data["salidas"], dict):
        raise PlaybookValidationError("salidas debe ser un objeto/dict.")

    seen_hitos: set[str] = set()

    for idx, hito in enumerate(data["hitos"], start=1):
        if not isinstance(hito, dict):
            raise PlaybookValidationError(f"Hito #{idx} debe ser un objeto/dict.")

        for key in ("id", "nombre", "importancia"):
            if key not in hito:
                raise PlaybookValidationError(f"Hito #{idx} no tiene clave obligatoria: {key}")

        hito_id = str(hito["id"]).strip()
        if not hito_id:
            raise PlaybookValidationError(f"Hito #{idx} tiene id vacío.")

        if hito_id in seen_hitos:
            raise PlaybookValidationError(f"Hito duplicado: {hito_id}")

        seen_hitos.add(hito_id)

        importancia = str(hito["importancia"]).strip().lower()
        if importancia not in {"alta", "media", "baja"}:
            raise PlaybookValidationError(
                f"Hito {hito_id} tiene importancia inválida: {importancia}"
            )

    required_hitos = {
        "demanda_interpuesta",
        "litis_integrada",
        "contestacion_demanda",
        "apertura_prueba",
        "certificacion_prueba",
        "alegatos",
        "autos_para_sentencia",
        "sentencia",
        "apelacion",
        "ejecucion_sentencia",
        "honorarios",
    }

    missing_hitos = sorted(required_hitos - seen_hitos)
    if missing_hitos:
        raise PlaybookValidationError(
            f"Faltan hitos procesales mínimos: {', '.join(missing_hitos)}"
        )

    salidas = data["salidas"]
    if "informe_markdown" not in salidas:
        raise PlaybookValidationError("salidas debe incluir informe_markdown.")

    if "json_sistema" not in salidas:
        raise PlaybookValidationError("salidas debe incluir json_sistema.")
