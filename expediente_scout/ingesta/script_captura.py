"""Fuente de captura basada en un script externo determinístico."""

from __future__ import annotations

import csv
import json
import os
import shlex
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from expediente_scout.ingesta.fuente_captura import ItemIndice


@dataclass(frozen=True)
class ResultadoEjecucionScript:
    """Resultado mínimo de ejecutar el script externo, sin stdout/stderr persistidos."""

    returncode: int
    indice_path: Path
    raw_dir: Path


class ScriptCaptura:
    """Adapta un script externo que produce PDFs + índice."""

    fuente_id = "script_pjn"

    def __init__(
        self,
        script_path: Path,
        output_dir: Path,
        env_path: Path | None = None,
        timeout: int = 300,
    ) -> None:
        self.script_path = Path(script_path)
        self.output_dir = Path(output_dir)
        self.env_path = Path(env_path) if env_path else None
        self.timeout = timeout

    def ruta_raw(self) -> Path:
        """Devuelve raw/ si existe; si no, la carpeta de salida completa."""
        raw = self.output_dir / "raw"
        return raw if raw.exists() else self.output_dir

    def leer_indice(self) -> list[ItemIndice]:
        """Lee indice.json/indice.csv emitido por el script externo."""
        indice = self._buscar_indice()
        if indice.suffix.lower() == ".json":
            return self._leer_indice_json(indice)
        if indice.suffix.lower() == ".csv":
            return self._leer_indice_csv(indice)
        raise ValueError(f"Formato de índice no soportado: {indice}")

    def ejecutar(self, jurisdiccion: str, numero: str, anio: int) -> ResultadoEjecucionScript:
        """Ejecuta el script externo con un contrato fijo de argumentos."""
        if not self.script_path.exists():
            raise FileNotFoundError(f"No existe script de captura: {self.script_path}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        env = _entorno_con_env_file(self.env_path)
        cmd = _comando_script(self.script_path) + [
            "--jurisdiccion",
            jurisdiccion,
            "--numero",
            numero,
            "--anio",
            str(anio),
            "--output",
            str(self.output_dir),
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(self.script_path.parent),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=self.timeout,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "Script de captura falló "
                f"con código {proc.returncode}. "
                "No se persiste stdout/stderr para evitar filtrar secretos. "
                f"Comando: {shlex.join(cmd)}"
            )
        indice = self._buscar_indice()
        raw_dir = self.ruta_raw()
        return ResultadoEjecucionScript(returncode=proc.returncode, indice_path=indice, raw_dir=raw_dir)

    def _buscar_indice(self) -> Path:
        candidatos = [
            self.output_dir / "indice.json",
            self.output_dir / "index.json",
            self.output_dir / "indice.csv",
            self.output_dir / "index.csv",
            self.output_dir / "raw" / "indice.json",
            self.output_dir / "raw" / "index.json",
            self.output_dir / "raw" / "indice.csv",
            self.output_dir / "raw" / "index.csv",
        ]
        for candidato in candidatos:
            if candidato.exists():
                return candidato
        raise FileNotFoundError(
            "No se encontró índice. Esperado: indice.json, index.json, indice.csv o index.csv."
        )

    def _leer_indice_json(self, path: Path) -> list[ItemIndice]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            items = data.get("items") or data.get("actuaciones") or data.get("documentos")
        else:
            items = data
        if not isinstance(items, list):
            raise ValueError("El índice JSON debe ser una lista o contener items/actuaciones/documentos.")
        return [_item_desde_dict(item) for item in items]

    def _leer_indice_csv(self, path: Path) -> list[ItemIndice]:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return [_item_desde_dict(row) for row in reader]


def _comando_script(script_path: Path) -> list[str]:
    if script_path.suffix.lower() == ".py":
        return [sys.executable, str(script_path)]
    return [str(script_path)]


def _entorno_con_env_file(env_path: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    if env_path is None:
        return env
    env_path = Path(env_path)
    if not env_path.exists():
        raise FileNotFoundError(f"No existe env file: {env_path}")
    _validar_permisos_env(env_path)
    env.update(_parse_env_file(env_path))
    return env


def _validar_permisos_env(env_path: Path) -> None:
    """Exige permisos 600/400 en POSIX para no dejar credenciales regaladas."""
    if os.name != "posix":
        return
    mode = stat.S_IMODE(env_path.stat().st_mode)
    if mode & 0o077:
        raise PermissionError(f"Permisos inseguros en {env_path}: usar chmod 600 {env_path}")


def _parse_env_file(env_path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Línea .env inválida: {raw_line!r}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            raise ValueError("Clave vacía en .env")
        result[key] = value
    return result


def _item_desde_dict(data: dict[str, Any]) -> ItemIndice:
    try:
        orden = int(str(data["orden"]).strip())
        descripcion = str(data["descripcion"]).strip()
        archivo = str(data["archivo"]).strip()
    except KeyError as exc:
        raise ValueError(f"Falta campo obligatorio en índice: {exc.args[0]}") from exc
    fecha_raw = data.get("fecha")
    fecha = _parse_fecha(fecha_raw)
    return ItemIndice(orden=orden, fecha=fecha, descripcion=descripcion, archivo=archivo)


def _parse_fecha(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text)
