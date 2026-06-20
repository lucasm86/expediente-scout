"""CLI de expediente-scout.

Paso 2: comandos locales mínimos para operar sobre capturas mock.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.ingerir import (
    estado_expediente,
    ingerir_captura,
    listar_expedientes,
)

app = typer.Typer(
    name="scout",
    help="Núcleo determinístico para organizar expedientes capturados.",
    no_args_is_help=True,
)


def _crear_fuente_mock() -> MockCaptura:
    return MockCaptura()


@app.command("ingerir")
def ingerir_cmd(
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
    fuente: Annotated[str, typer.Option(help="Fuente de captura. En Paso 2 solo existe: mock.")] = "mock",
) -> None:
    """Ingiere una captura local y actualiza el manifest sin duplicar."""
    if fuente != "mock":
        raise typer.BadParameter("En Paso 2 solo está implementada la fuente 'mock'.")

    manifest_path = ingerir_captura(
        root=root,
        jurisdiccion=jurisdiccion,
        numero=numero,
        anio=anio,
        fuente=_crear_fuente_mock(),
    )
    manifest = cargar_manifest(manifest_path)
    typer.echo(f"Manifest: {manifest_path}")
    typer.echo(f"Expediente: {manifest.expediente.id}")
    typer.echo(f"Actuaciones: {len(manifest.actuaciones)}")
    typer.echo(f"Documentos: {len(manifest.documentos)}")


@app.command("listar")
def listar_cmd(
    root: Annotated[Path, typer.Option(help="Raíz local donde buscar data/expedientes.")] = Path("."),
) -> None:
    """Lista expedientes locales ya ingeridos."""
    manifests = listar_expedientes(root)
    if not manifests:
        typer.echo("No hay expedientes locales.")
        return

    typer.echo("expediente_id\tjurisdiccion\tnumero\tanio\tactuaciones\tdocumentos")
    for manifest_path in manifests:
        manifest = cargar_manifest(manifest_path)
        exp = manifest.expediente
        typer.echo(
            f"{exp.id}\t{exp.jurisdiccion}\t{exp.numero}\t{exp.anio}\t"
            f"{len(manifest.actuaciones)}\t{len(manifest.documentos)}"
        )


@app.command("estado")
def estado_cmd(
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
) -> None:
    """Muestra un parte breve del expediente local."""
    try:
        estado = estado_expediente(root=root, jurisdiccion=jurisdiccion, numero=numero, anio=anio)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Expediente: {estado['expediente_id']}")
    typer.echo(f"Manifest: {estado['manifest_path']}")
    typer.echo(f"Actuaciones: {estado['actuaciones']}")
    typer.echo(f"Documentos: {estado['documentos']}")
    typer.echo(f"Última actuación: {estado['ultima_actuacion']}")


if __name__ == "__main__":
    app()
