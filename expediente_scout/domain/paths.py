"""Construcción segura de rutas del expediente."""

from pathlib import Path

_SUBCARPETAS = ("raw", "selected", "text", "reports", "logs")


def _validar_segmento(nombre: str, valor: str) -> None:
    if not valor or "/" in valor or "\\" in valor or ".." in valor:
        raise ValueError(f"{nombre} inválido: no puede contener separadores ni '..'")


def crear_estructura(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    """Crea data/expedientes/<jurisdiccion>/<numero>-<anio>/ y subcarpetas."""
    _validar_segmento("jurisdiccion", jurisdiccion)
    _validar_segmento("numero", numero)
    if not isinstance(anio, int) or anio < 1900 or anio > 2200:
        raise ValueError("anio inválido: debe ser un entero razonable")

    base_root = Path(root).resolve()
    expediente_dir = base_root / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}"
    expediente_dir.mkdir(parents=True, exist_ok=True)

    resolved = expediente_dir.resolve()
    if not resolved.is_relative_to(base_root):
        raise ValueError("ruta inválida: posible path traversal")

    for subcarpeta in _SUBCARPETAS:
        (resolved / subcarpeta).mkdir(parents=True, exist_ok=True)

    return resolved
