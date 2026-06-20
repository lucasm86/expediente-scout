"""Contrato estructurado de análisis producido por una skill externa."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Hallazgo(BaseModel):
    """Hallazgo atómico con fuentes internas obligatorias para validación."""

    model_config = ConfigDict(extra="forbid")

    tipo: str = Field(min_length=1)
    afirmacion: str = Field(min_length=1)
    fuentes: list[str] = Field(default_factory=list)
    confianza: Literal["alta", "media", "baja"]


class AnalisisEstructurado(BaseModel):
    """Salida JSON esperada de la etapa de análisis."""

    model_config = ConfigDict(extra="forbid")

    hallazgos: list[Hallazgo] = Field(default_factory=list)
    no_determinable: list[str] = Field(default_factory=list)
    requiere_revision: bool = False
