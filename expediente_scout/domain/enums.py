"""Enumeraciones del dominio de expediente-scout."""

from enum import StrEnum


class Categoria(StrEnum):
    DEMANDA = "demanda"
    CONTESTACION = "contestacion"
    RECONVENCION = "reconvencion"
    ESCRITO_PARTE = "escrito_parte"
    PROVEIDO_SIMPLE = "proveido_simple"
    INTERLOCUTORIA = "interlocutoria"
    SENTENCIA = "sentencia"
    RECURSO = "recurso"
    CEDULA = "cedula"
    NOTIFICACION = "notificacion"
    OFICIO = "oficio"
    PERICIA = "pericia"
    LIQUIDACION = "liquidacion"
    EMBARGO = "embargo"
    CAUTELAR = "cautelar"
    AUDIENCIA = "audiencia"
    DOCUMENTAL = "documental"
    CONSTANCIA_AUTOMATICA = "constancia_automatica"
    DUPLICADO = "duplicado"
    IRRELEVANTE = "irrelevante"
    SIN_CLASIFICAR = "sin_clasificar"


class Relevancia(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
    DUPLICADO = "duplicado"
    REQUIERE_REVISION = "requiere_revision"


class EstadoDescarga(StrEnum):
    COMPLETO = "completo"
    PARCIAL = "parcial"
    FALLIDO = "fallido"
    PENDIENTE = "pendiente"
