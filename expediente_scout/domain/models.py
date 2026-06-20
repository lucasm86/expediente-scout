"""Modelos Pydantic del dominio."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .enums import Categoria, EstadoDescarga, Relevancia


class Documento(BaseModel):
    id: str
    nombre_archivo: str
    ruta_raw: str
    ruta_text: str | None = None
    ruta_selected: str | None = None
    fecha: date | None = None
    categoria: Categoria = Categoria.SIN_CLASIFICAR
    hash_sha256: str
    paginas: int | None = None
    estado_descarga: EstadoDescarga
    relevancia: Relevancia = Relevancia.REQUIERE_REVISION
    motivo_relevancia: str | None = None
    duplicado_de: str | None = None
    actuacion_id: str | None = None
    metodo_clasificacion: Literal["regla", "ia", "humano"] | None = None


class Actuacion(BaseModel):
    id: str
    orden: int
    fecha: date | None
    descripcion: str
    tipo_estimado: Categoria = Categoria.SIN_CLASIFICAR
    fuente_ref: str
    documentos: list[str] = Field(default_factory=list)


class Expediente(BaseModel):
    id: str
    jurisdiccion: str
    numero: str
    anio: int
    caratula: str | None = None
    organismo: str | None = None
    fuente: str


class Captura(BaseModel):
    captura_id: str
    fecha_captura: datetime
    adapter: str
    resultado: str
    actuaciones_nuevas: int
    documentos_nuevos: int
    log_ref: str | None = None


class EstadoAnalisis(BaseModel):
    etapa_procesal_estimada: str | None = None
    confianza_etapa: str | None = None
    ultima_actuacion_relevante: str | None = None
    ultimo_informe: str | None = None
    actualizado: datetime | None = None


class Manifest(BaseModel):
    schema_version: str = "1.0"
    expediente: Expediente
    capturas: list[Captura] = Field(default_factory=list)
    actuaciones: list[Actuacion] = Field(default_factory=list)
    documentos: list[Documento] = Field(default_factory=list)
    estado_analisis: EstadoAnalisis = Field(default_factory=EstadoAnalisis)
