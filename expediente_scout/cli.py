"""CLI de expediente-scout."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from expediente_scout.domain.enums import Relevancia
from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.ingerir import (
    estado_expediente,
    ingerir_captura,
    listar_expedientes,
)
from expediente_scout.pipeline.normalizar import normalizar_expediente

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
    fuente: Annotated[str, typer.Option(help="Fuente de captura. En Paso 3 solo existe: mock.")] = "mock",
) -> None:
    """Ingiere una captura local y actualiza el manifest sin duplicar."""
    if fuente != "mock":
        raise typer.BadParameter("En Paso 3 solo está implementada la fuente 'mock'.")

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


@app.command("normalizar")
def normalizar_cmd(
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
) -> None:
    """Extrae texto, cuenta páginas y marca duplicados exactos por hash."""
    try:
        manifest_path = normalizar_expediente(root=root, jurisdiccion=jurisdiccion, numero=numero, anio=anio)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    manifest = cargar_manifest(manifest_path)
    normalizados = sum(1 for doc in manifest.documentos if doc.ruta_text and doc.paginas is not None)
    duplicados = sum(1 for doc in manifest.documentos if doc.relevancia == Relevancia.DUPLICADO)
    typer.echo(f"Manifest: {manifest_path}")
    typer.echo(f"Expediente: {manifest.expediente.id}")
    typer.echo(f"Documentos normalizados: {normalizados}")
    typer.echo(f"Duplicados: {duplicados}")


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
