"""Contrato para fuentes de captura ya descargadas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ItemIndice:
    orden: int
    fecha: date | None
    descripcion: str
    archivo: str


class FuenteCaptura(Protocol):
    fuente_id: str

    def ruta_raw(self) -> Path:
        """Devuelve la carpeta donde están los PDFs capturados."""
        ...

    def leer_indice(self) -> list[ItemIndice]:
        """Devuelve el índice cronológico de actuaciones/documentos."""
        ...
