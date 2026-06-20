"""CLI de expediente-scout."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from expediente_scout.domain.enums import Relevancia
from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.curar import curar_expediente
from expediente_scout.pipeline.dashboard import generar_dashboard
from expediente_scout.pipeline.capturar import capturar_desde_script
from expediente_scout.pipeline.ingerir import (
    estado_expediente,
    ingerir_captura,
    listar_expedientes,
)
from expediente_scout.pipeline.normalizar import normalizar_expediente
from expediente_scout.pipeline.novedades import detectar_novedades_captura
from expediente_scout.pipeline.reportar import reportar_expediente
from expediente_scout.pipeline.validar_analisis import validar_analisis_archivo

app = typer.Typer(
    name="scout",
    help="Núcleo determinístico para organizar expedientes capturados.",
    no_args_is_help=True,
)


def _crear_fuente_mock(mock_estado: str) -> MockCaptura:
    return MockCaptura(estado=mock_estado)


def _manifest_path(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return Path(root) / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}" / "manifest.json"


def _validar_fuente_mock(fuente: str, mock_estado: str) -> None:
    if fuente != "mock":
        raise typer.BadParameter("En Paso 7 solo está implementada la fuente 'mock'.")
    if mock_estado not in {"base", "ampliado"}:
        raise typer.BadParameter("--mock-estado debe ser 'base' o 'ampliado'.")


@app.command("ingerir")
def ingerir_cmd(
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
    fuente: Annotated[str, typer.Option(help="Fuente de captura. En Paso 7 solo existe: mock.")] = "mock",
    mock_estado: Annotated[str, typer.Option("--mock-estado", help="Estado del mock: base o ampliado.")] = "base",
) -> None:
    """Ingiere una captura local y actualiza el manifest sin duplicar."""
    _validar_fuente_mock(fuente, mock_estado)

    path_antes = _manifest_path(root, jurisdiccion, numero, anio)
    manifest_antes = cargar_manifest(path_antes) if path_antes.exists() else None
    actuaciones_antes = len(manifest_antes.actuaciones) if manifest_antes else 0
    documentos_antes = len(manifest_antes.documentos) if manifest_antes else 0

    manifest_path = ingerir_captura(
        root=root,
        jurisdiccion=jurisdiccion,
        numero=numero,
        anio=anio,
        fuente=_crear_fuente_mock(mock_estado),
    )
    manifest = cargar_manifest(manifest_path)
    actuaciones_nuevas = len(manifest.actuaciones) - actuaciones_antes
    documentos_nuevos = len(manifest.documentos) - documentos_antes

    typer.echo(f"Manifest: {manifest_path}")
    typer.echo(f"Expediente: {manifest.expediente.id}")
    typer.echo(f"Actuaciones: {len(manifest.actuaciones)}")
    typer.echo(f"Documentos: {len(manifest.documentos)}")
    typer.echo(f"Actuaciones nuevas: {actuaciones_nuevas}")
    typer.echo(f"Documentos nuevos: {documentos_nuevos}")


@app.command("novedades")
def novedades_cmd(
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
    fuente: Annotated[str, typer.Option(help="Fuente de captura. En Paso 7 solo existe: mock.")] = "mock",
    mock_estado: Annotated[str, typer.Option("--mock-estado", help="Estado del mock: base o ampliado.")] = "ampliado",
) -> None:
    """Detecta novedades de una captura contra el manifest local sin ingerirlas."""
    _validar_fuente_mock(fuente, mock_estado)
    resumen = detectar_novedades_captura(
        root=root,
        jurisdiccion=jurisdiccion,
        numero=numero,
        anio=anio,
        fuente=_crear_fuente_mock(mock_estado),
    )

    typer.echo(f"Manifest existente: {'sí' if resumen.manifest_existe else 'no'}")
    typer.echo(f"Actuaciones nuevas: {resumen.total_actuaciones_nuevas}")
    typer.echo(f"Documentos nuevos: {resumen.total_documentos_nuevos}")
    for item in resumen.actuaciones_nuevas:
        fecha = item.fecha or "sin fecha"
        typer.echo(f"- {item.actuacion_id} | {fecha} | {item.descripcion} | {item.archivo}")


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


@app.command("curar")
def curar_cmd(
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
) -> None:
    """Clasifica por reglas y copia documentos relevantes a selected/."""
    try:
        resultado = curar_expediente(root=root, jurisdiccion=jurisdiccion, numero=numero, anio=anio)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Manifest: {resultado.manifest_path}")
    typer.echo(f"Documentos curados: {resultado.documentos_curados}")
    typer.echo(f"Seleccionados: {resultado.seleccionados}")
    typer.echo(f"Alta: {resultado.alta}")
    typer.echo(f"Media: {resultado.media}")
    typer.echo(f"Baja: {resultado.baja}")
    typer.echo(f"Requiere revisión: {resultado.requiere_revision}")
    typer.echo(f"Duplicados: {resultado.duplicados}")


@app.command("validar-analisis")
def validar_analisis_cmd(
    analisis_json: Annotated[Path, typer.Option("--analisis-json", help="Ruta al JSON de análisis simulado.")],
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
) -> None:
    """Valida un JSON de análisis contra IDs reales del manifest."""
    try:
        resultado = validar_analisis_archivo(
            root=root,
            jurisdiccion=jurisdiccion,
            numero=numero,
            anio=anio,
            analisis_path=analisis_json,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Manifest: {resultado.manifest_path}")
    typer.echo(f"Análisis: {resultado.analisis_path}")
    typer.echo(f"Hallazgos válidos: {resultado.total_validos}")
    typer.echo(f"Hallazgos descartados: {resultado.total_descartados}")
    typer.echo(f"Salida: {resultado.salida_path}")


@app.command("reportar")
def reportar_cmd(
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
) -> None:
    """Genera reports/informe.md desde manifest y análisis validado."""
    try:
        resultado = reportar_expediente(root=root, jurisdiccion=jurisdiccion, numero=numero, anio=anio)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Manifest: {resultado.manifest_path}")
    typer.echo(f"Análisis validado: {resultado.analisis_validado_path}")
    typer.echo(f"Informe: {resultado.informe_path}")
    typer.echo(f"Secciones: {resultado.secciones}")
    typer.echo(f"Hallazgos incluidos: {resultado.hallazgos_incluidos}")



@app.command("capturar")
def capturar_cmd(
    script_path: Annotated[Path, typer.Option("--script-path", help="Script externo de captura PJN.")],
    jurisdiccion: Annotated[str, typer.Option(help="Jurisdicción, por ejemplo: pjn.")] = "pjn",
    numero: Annotated[str, typer.Option(help="Número del expediente.")] = "12345",
    anio: Annotated[int, typer.Option("--anio", help="Año del expediente.")] = 2024,
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
    env_path: Annotated[Path | None, typer.Option("--env-path", help="Archivo .env con credenciales, permisos 600.")] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir", help="Carpeta de salida para el script externo.")] = None,
    timeout: Annotated[int, typer.Option("--timeout", help="Timeout en segundos para el script externo.")] = 300,
) -> None:
    """Ejecuta un script externo de captura y reconcilia su salida con manifest.json."""
    try:
        resultado = capturar_desde_script(
            root=root,
            jurisdiccion=jurisdiccion,
            numero=numero,
            anio=anio,
            script_path=script_path,
            env_path=env_path,
            output_dir=output_dir,
            timeout=timeout,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Captura: ok")
    typer.echo(f"Manifest: {resultado.manifest_path}")
    typer.echo(f"Índice: {resultado.indice_path}")
    typer.echo(f"Raw: {resultado.raw_dir}")
    typer.echo(f"Log: {resultado.log_path}")
    typer.echo(f"Actuaciones: {resultado.total_actuaciones}")
    typer.echo(f"Documentos: {resultado.total_documentos}")
    typer.echo(f"Actuaciones nuevas: {resultado.actuaciones_nuevas}")
    typer.echo(f"Documentos nuevos: {resultado.documentos_nuevos}")

@app.command("dashboard")
def dashboard_cmd(
    root: Annotated[Path, typer.Option(help="Raíz local del proyecto/datos.")] = Path("."),
    output: Annotated[Path | None, typer.Option("--output", help="Ruta de salida del dashboard HTML.")] = None,
) -> None:
    """Genera un dashboard HTML estático de solo lectura."""
    resultado = generar_dashboard(root=root, output=output)
    typer.echo(f"Dashboard: {resultado.output_path}")
    typer.echo(f"Expedientes: {resultado.expedientes}")
    typer.echo("Solo lectura: sí")


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


# --- Paso 10: entrega y PDF ---

@app.command("exportar-pdf")
def exportar_pdf(
    root: Path = typer.Option(Path("."), "--root"),
    jurisdiccion: str = typer.Option(..., "--jurisdiccion"),
    numero: str = typer.Option(..., "--numero"),
    anio: int = typer.Option(..., "--anio"),
) -> None:
    from expediente_scout.pipeline.entregar import exportar_pdf_informe

    pdf = exportar_pdf_informe(root, jurisdiccion, numero, anio)
    typer.echo(f"PDF: {pdf}")


@app.command("entregar")
def entregar(
    root: Path = typer.Option(Path("."), "--root"),
    jurisdiccion: str = typer.Option(..., "--jurisdiccion"),
    numero: str = typer.Option(..., "--numero"),
    anio: int = typer.Option(..., "--anio"),
    destino: str = typer.Option("whatsapp://preview", "--destino"),
    limite_mensaje: int = typer.Option(1200, "--limite-mensaje"),
) -> None:
    from expediente_scout.pipeline.entregar import lock_expediente, preparar_entrega

    with lock_expediente(root, jurisdiccion, numero, anio):
        entrega = preparar_entrega(root, jurisdiccion, numero, anio, destino, limite_mensaje)
    typer.echo("Entrega preparada: sí")
    typer.echo("Enviado: no")
    typer.echo(f"Destino: {entrega.destino}")
    typer.echo(f"Chunks: {entrega.chunks}")
    typer.echo(f"PDF: {entrega.ruta_pdf}")
    typer.echo(f"Log: {entrega.ruta_json}")
