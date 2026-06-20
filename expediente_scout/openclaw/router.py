"""Router determinístico para comandos que OpenClaw recibirá por WhatsApp."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path


@dataclass(frozen=True)
class CommandPlan:
    """Plan seguro y auditable que OpenClaw puede ejecutar por shell."""

    autorizado: bool
    comando: str | None = None
    jurisdiccion: str | None = None
    numero: str | None = None
    anio: int | None = None
    comandos_shell: list[str] = field(default_factory=list)
    requiere_gpt: bool = False
    motivo: str = ""


_RE_EXPEDIENTE = re.compile(
    r"^Expediente:\s+"
    r"(?P<comando>listar|estado|capturar|novedades|informe)"
    r"(?:\s+(?P<jurisdiccion>[a-zA-Z0-9_-]+)\s+(?P<numero>[0-9A-Za-z_.-]+)\/(?P<anio>\d{4}))?"
    r"\s*$",
    re.IGNORECASE,
)


def _base_args(root: str, jurisdiccion: str, numero: str, anio: int) -> str:
    return f"--root {root} --jurisdiccion {jurisdiccion} --numero {numero} --anio {anio}"


def _ruta_analisis(root: str, jurisdiccion: str, numero: str, anio: int) -> str:
    return str(
        Path(root)
        / "data"
        / "expedientes"
        / jurisdiccion
        / f"{numero}-{anio}"
        / "reports"
        / "analisis-gpt.json"
    )


def construir_plan_desde_mensaje(
    remitente: str,
    mensaje: str,
    allowlist: set[str] | list[str] | tuple[str, ...],
    *,
    root: str = ".",
    script_path: str = "/opt/expediente-scout/scripts/pjn.py",
    env_path: str = ".env",
) -> CommandPlan:
    """Traduce un mensaje WhatsApp autorizado a comandos shell de `scout`."""

    permitidos = set(allowlist)
    if remitente not in permitidos:
        return CommandPlan(autorizado=False, motivo="Remitente no autorizado")

    match = _RE_EXPEDIENTE.match(mensaje.strip())
    if not match:
        return CommandPlan(autorizado=False, motivo="Formato de comando inválido")

    comando = match.group("comando").lower()
    jurisdiccion = match.group("jurisdiccion")
    numero = match.group("numero")
    anio_raw = match.group("anio")

    if comando == "listar":
        return CommandPlan(
            autorizado=True,
            comando=comando,
            comandos_shell=[f"scout listar --root {root}"],
            motivo="Listado local; no toca PJN",
        )

    if not (jurisdiccion and numero and anio_raw):
        return CommandPlan(autorizado=False, comando=comando, motivo="Faltan jurisdicción, número o año")

    anio = int(anio_raw)
    args = _base_args(root, jurisdiccion, numero, anio)

    if comando == "estado":
        comandos = [f"scout estado {args}"]
        requiere_gpt = False
    elif comando == "capturar":
        comandos = [
            f"scout capturar --script-path {script_path} --env-path {env_path} {args}",
        ]
        requiere_gpt = False
    elif comando == "novedades":
        comandos = [
            f"scout capturar --script-path {script_path} --env-path {env_path} {args}",
            f"scout estado {args}",
        ]
        requiere_gpt = False
    elif comando == "informe":
        analisis_json = _ruta_analisis(root, jurisdiccion, numero, anio)
        comandos = [
            f"scout capturar --script-path {script_path} --env-path {env_path} {args}",
            f"scout normalizar {args}",
            f"scout curar {args}",
            f"GPT_ANALISIS_JSON={analisis_json}",
            f"scout validar-analisis {args} --analisis-json {analisis_json}",
            f"scout reportar {args}",
        ]
        requiere_gpt = True
    else:  # cobertura defensiva
        return CommandPlan(autorizado=False, comando=comando, motivo="Comando no reconocido")

    return CommandPlan(
        autorizado=True,
        comando=comando,
        jurisdiccion=jurisdiccion,
        numero=numero,
        anio=anio,
        comandos_shell=comandos,
        requiere_gpt=requiere_gpt,
        motivo="Comando aceptado",
    )
