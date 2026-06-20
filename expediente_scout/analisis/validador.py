"""Validador anti-alucinación: solo pasan hallazgos con referencias existentes."""

from __future__ import annotations

from dataclasses import dataclass

from expediente_scout.analisis.contrato import AnalisisEstructurado, Hallazgo
from expediente_scout.domain.models import Manifest


@dataclass(frozen=True)
class ResultadoValidacion:
    """Resultado puro de validar hallazgos contra el manifest."""

    validos: list[Hallazgo]
    descartados: list[Hallazgo]

    @property
    def total_validos(self) -> int:
        return len(self.validos)

    @property
    def total_descartados(self) -> int:
        return len(self.descartados)


def ids_existentes(manifest: Manifest) -> set[str]:
    """Devuelve todos los IDs internos que pueden ser citados."""
    ids = {doc.id for doc in manifest.documentos}
    ids.update(act.id for act in manifest.actuaciones)
    return ids


def validar_hallazgos(hallazgos: list[Hallazgo], manifest: Manifest) -> ResultadoValidacion:
    """Descarta hallazgos sin fuentes o con fuentes inexistentes."""
    ids = ids_existentes(manifest)
    validos: list[Hallazgo] = []
    descartados: list[Hallazgo] = []

    for hallazgo in hallazgos:
        if hallazgo.fuentes and all(fuente in ids for fuente in hallazgo.fuentes):
            validos.append(hallazgo)
        else:
            descartados.append(hallazgo)

    return ResultadoValidacion(validos=validos, descartados=descartados)


def validar_analisis(analisis: AnalisisEstructurado, manifest: Manifest) -> ResultadoValidacion:
    """Valida una salida estructurada completa contra el manifest."""
    return validar_hallazgos(analisis.hallazgos, manifest)
