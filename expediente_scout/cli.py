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
from expediente_scout.pipeline.clasificar_playbook import clasificar_indice_playbook
from expediente_scout.pipeline.ingerir import (
    estado_expediente,
    ingerir_captura,
    listar_expedientes,
)
from expediente_scout.pipeline.normalizar import normalizar_expediente
from expediente_scout.pipeline.novedades import detectar_novedades_captura
from expediente_scout.pipeline.reportar import reportar_expediente
from expediente_scout.pipeline.seleccionar_lectura import generar_plan_lectura
from expediente_scout.pipeline.resolver_plan_lectura import generar_plan_lectura_resuelto
from expediente_scout.pipeline.extraer_texto_seleccionado import generar_extraccion_texto
from expediente_scout.pipeline.generar_paquete_analisis import generar_paquete_analisis
from expediente_scout.pipeline.preanalisis import ejecutar_preanalisis
from expediente_scout.pipeline.generar_estado_actual import generar_estado_actual
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


@app.command("clasificar-playbook")
def clasificar_playbook_cmd(
    indice: Annotated[Path, typer.Option("--indice", help="Ruta al indice.json generado por el capturador PJN.")],
    output: Annotated[Path, typer.Option("--output", help="Ruta de salida para clasificacion_playbook.json.")],
    playbook: Annotated[str, typer.Option("--playbook", help="ID del playbook procesal a usar.")] = "ordinario_v1",
) -> None:
    """Clasifica actuaciones de un índice PJN usando un playbook procesal."""
    try:
        resultado = clasificar_indice_playbook(
            indice_path=indice,
            playbook_id=playbook,
            output_path=output,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Clasificación playbook: ok")
    typer.echo(f"Playbook: {resultado.playbook_id}")
    typer.echo(f"Índice: {resultado.indice_path}")
    typer.echo(f"Salida: {resultado.output_path}")
    typer.echo(f"Actuaciones: {resultado.total_actuaciones}")
    typer.echo(f"Con hito: {resultado.total_con_hito}")
    typer.echo(f"Leer completo: {resultado.total_leer_completo}")



@app.command("seleccionar-lectura")
def seleccionar_lectura_cmd(
    clasificacion: Annotated[Path, typer.Option("--clasificacion", help="Ruta a clasificacion_playbook.json.")],
    output: Annotated[Path, typer.Option("--output", help="Ruta de salida para plan_lectura.json.")],
) -> None:
    """Genera un plan de lectura a partir de una clasificación por playbook."""
    try:
        resultado = generar_plan_lectura(
            clasificacion_path=clasificacion,
            output_path=output,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Plan de lectura: ok")
    typer.echo(f"Clasificación: {resultado.clasificacion_path}")
    typer.echo(f"Salida: {resultado.output_path}")
    typer.echo(f"Actuaciones: {resultado.total_actuaciones}")
    typer.echo(f"Seleccionadas: {resultado.total_seleccionadas}")
    typer.echo(f"Accesorias: {resultado.total_accesorias}")



@app.command("resolver-plan-lectura")
def resolver_plan_lectura_cmd(
    plan: Annotated[Path, typer.Option("--plan", help="Ruta a plan_lectura.json.")],
    raw_dir: Annotated[Path, typer.Option("--raw-dir", help="Carpeta raw con PDFs descargados.")],
    output: Annotated[Path, typer.Option("--output", help="Ruta de salida para plan_lectura_resuelto.json.")],
    no_strict: Annotated[bool, typer.Option("--no-strict", help="No fallar si hay PDFs faltantes.")] = False,
) -> None:
    """Resuelve rutas físicas de PDFs para un plan de lectura."""
    try:
        resultado = generar_plan_lectura_resuelto(
            plan_path=plan,
            raw_dir=raw_dir,
            output_path=output,
            strict=not no_strict,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Plan de lectura resuelto: ok")
    typer.echo(f"Plan: {resultado.plan_path}")
    typer.echo(f"Raw: {resultado.raw_dir}")
    typer.echo(f"Salida: {resultado.output_path}")
    typer.echo(f"Seleccionadas: {resultado.total_seleccionadas}")
    typer.echo(f"Accesorias: {resultado.total_accesorias}")
    typer.echo(f"Faltantes: {resultado.total_faltantes}")



@app.command("extraer-texto-seleccionado")
def extraer_texto_seleccionado_cmd(
    plan: Annotated[Path, typer.Option("--plan", help="Ruta a plan_lectura_resuelto.json.")],
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Carpeta de salida para textos_seleccionados/ y extraccion_texto.json.")],
    no_strict: Annotated[bool, typer.Option("--no-strict", help="No fallar si un PDF seleccionado no puede leerse.")] = False,
) -> None:
    """Extrae texto de los PDFs seleccionados en un plan de lectura resuelto."""
    try:
        resultado = generar_extraccion_texto(
            plan_path=plan,
            output_dir=output_dir,
            strict=not no_strict,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Extracción de texto seleccionado: ok")
    typer.echo(f"Plan: {resultado.plan_path}")
    typer.echo(f"Output dir: {resultado.output_dir}")
    typer.echo(f"Índice: {resultado.indice_path}")
    typer.echo(f"Seleccionadas: {resultado.total_seleccionadas}")
    typer.echo(f"Extraídas: {resultado.total_extraidas}")
    typer.echo(f"Sin texto: {resultado.total_sin_texto}")
    typer.echo(f"Errores: {resultado.total_errores}")



@app.command("generar-paquete-analisis")
def generar_paquete_analisis_cmd(
    extraccion: Annotated[Path, typer.Option("--extraccion", help="Ruta a extraccion_texto.json.")],
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Carpeta de salida para el paquete de análisis.")],
) -> None:
    """Genera un paquete Markdown/JSON por hitos desde la extracción de texto."""
    try:
        resultado = generar_paquete_analisis(
            extraccion_path=extraccion,
            output_dir=output_dir,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Paquete de análisis: ok")
    typer.echo(f"Extracción: {resultado.extraccion_path}")
    typer.echo(f"Output dir: {resultado.output_dir}")
    typer.echo(f"Índice: {resultado.indice_path}")
    typer.echo(f"Mapa: {resultado.mapa_path}")
    typer.echo(f"Documentos: {resultado.total_documentos}")
    typer.echo(f"Bloques: {resultado.total_bloques}")
    typer.echo(f"Caracteres: {resultado.total_caracteres}")
    typer.echo(f"Tokens aprox: {round(resultado.total_caracteres / 4)}")



@app.command("preanalisis")
def preanalisis_cmd(
    indice: Annotated[Path, typer.Option("--indice", help="Ruta al indice.json generado por la captura PJN.")],
    raw_dir: Annotated[Path, typer.Option("--raw-dir", help="Carpeta raw con los PDFs descargados.")],
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Carpeta de salida del preanálisis.")],
    playbook: Annotated[str, typer.Option("--playbook", help="ID del playbook procesal a usar.")] = "ordinario_v1",
    no_strict: Annotated[bool, typer.Option("--no-strict", help="No fallar si algún PDF no puede resolverse o leerse.")] = False,
) -> None:
    """Ejecuta clasificación, selección, extracción y paquete de análisis en un solo paso."""
    try:
        resultado = ejecutar_preanalisis(
            indice_path=indice,
            raw_dir=raw_dir,
            output_dir=output_dir,
            playbook_id=playbook,
            strict=not no_strict,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Preanálisis: ok")
    typer.echo(f"Índice: {resultado.indice_path}")
    typer.echo(f"Raw: {resultado.raw_dir}")
    typer.echo(f"Output dir: {resultado.output_dir}")
    typer.echo(f"Playbook: {resultado.playbook_id}")
    typer.echo(f"Clasificación: {resultado.clasificacion_path}")
    typer.echo(f"Plan lectura: {resultado.plan_lectura_path}")
    typer.echo(f"Plan resuelto: {resultado.plan_lectura_resuelto_path}")
    typer.echo(f"Extracción índice: {resultado.extraccion_indice_path}")
    typer.echo(f"Paquete índice: {resultado.paquete_indice_path}")
    typer.echo(f"Mapa general: {resultado.mapa_general_path}")
    typer.echo(f"Actuaciones: {resultado.total_actuaciones}")
    typer.echo(f"Con hito: {resultado.total_con_hito}")
    typer.echo(f"Seleccionadas: {resultado.total_seleccionadas}")
    typer.echo(f"Extraídas: {resultado.total_extraidas}")
    typer.echo(f"Bloques: {resultado.total_bloques}")
    typer.echo(f"Caracteres: {resultado.total_caracteres}")
    typer.echo(f"Tokens aprox: {round(resultado.total_caracteres / 4)}")



@app.command("generar-estado-actual")
def generar_estado_actual_cmd(
    paquete_indice: Annotated[Path, typer.Option("--paquete-indice", help="Ruta a paquete_analisis/indice_paquete.json.")],
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Carpeta de salida para estado_actual.")],
) -> None:
    """Genera prompt y material reducido para analizar el estado procesal actual."""
    try:
        resultado = generar_estado_actual(
            paquete_indice_path=paquete_indice,
            output_dir=output_dir,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Estado actual: ok")
    typer.echo(f"Paquete índice: {resultado.paquete_indice_path}")
    typer.echo(f"Output dir: {resultado.output_dir}")
    typer.echo(f"Índice: {resultado.indice_path}")
    typer.echo(f"Prompt: {resultado.prompt_path}")
    typer.echo(f"Material: {resultado.material_path}")
    typer.echo(f"Input LLM: {resultado.input_llm_path}")
    typer.echo(f"Bloques: {resultado.total_bloques}")
    typer.echo(f"Caracteres material: {resultado.total_caracteres_material}")
    typer.echo(f"Tokens aprox material: {round(resultado.total_caracteres_material / 4)}")


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

from pathlib import Path as _CompactPath


@app.command("compactar-estado-actual")
def compactar_estado_actual_cmd(
    indice_estado: _CompactPath = typer.Option(
        ...,
        "--indice-estado",
        help="Ruta al indice_estado_actual.json generado por generar-estado-actual.",
    ),
    output_dir: _CompactPath = typer.Option(
        ...,
        "--output-dir",
        help="Directorio de salida para el estado actual compacto.",
    ),
    policy: _CompactPath = typer.Option(
        _CompactPath("config/document_policies/estado_actual_v1.yaml"),
        "--policy",
        help="Política documental para compactar el estado actual.",
    ),
) -> None:
    from expediente_scout.pipeline.compactar_estado_actual import compactar_estado_actual

    resultado = compactar_estado_actual(
        indice_estado_path=indice_estado,
        output_dir=output_dir,
        policy_path=policy,
    )

    typer.echo("Compactación estado actual: ok")
    typer.echo(f"Documentos: {resultado.total_documentos}")
    typer.echo(f"Texto completo: {resultado.total_texto_completo}")
    typer.echo(f"Extracto relevante: {resultado.total_extracto_relevante}")
    typer.echo(f"Resumen operativo: {resultado.total_resumen_operativo}")
    typer.echo(f"Solo metadata: {resultado.total_solo_metadata}")
    typer.echo(f"Input compacto: {resultado.input_llm_compacto_path}")
    typer.echo(f"Caracteres input compacto: {resultado.caracteres_input_compacto}")
    typer.echo(f"Tokens aprox input compacto: {round(resultado.caracteres_input_compacto / 4)}")

@app.command("estudiar-pjn-local")
def estudiar_pjn_local_cmd(
    indice: Path = typer.Option(
        ...,
        "--indice",
        help="Ruta al indice.json ya capturado desde PJN.",
    ),
    raw_dir: Path = typer.Option(
        ...,
        "--raw-dir",
        help="Directorio raw/ con PDFs ya descargados.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Directorio de salida para el estudio completo.",
    ),
    playbook: str = typer.Option(
        "ordinario_v1",
        "--playbook",
        help="Playbook procesal a utilizar.",
    ),
    policy: Path = typer.Option(
        Path("config/document_policies/estado_actual_v1.yaml"),
        "--policy",
        help="Política documental para compactar estado actual.",
    ),
) -> None:
    import json
    import subprocess

    output_dir.mkdir(parents=True, exist_ok=True)

    preanalisis_dir = output_dir / "preanalisis"
    estado_dir = output_dir / "estado_actual"
    compacto_dir = output_dir / "estado_actual_compacto"

    subprocess.run(
        [
            "scout",
            "preanalisis",
            "--indice",
            str(indice),
            "--raw-dir",
            str(raw_dir),
            "--output-dir",
            str(preanalisis_dir),
            "--playbook",
            playbook,
        ],
        check=True,
    )

    paquete_indice = preanalisis_dir / "paquete_analisis" / "indice_paquete.json"

    subprocess.run(
        [
            "scout",
            "generar-estado-actual",
            "--paquete-indice",
            str(paquete_indice),
            "--output-dir",
            str(estado_dir),
        ],
        check=True,
    )

    indice_estado = estado_dir / "indice_estado_actual.json"

    subprocess.run(
        [
            "scout",
            "compactar-estado-actual",
            "--indice-estado",
            str(indice_estado),
            "--output-dir",
            str(compacto_dir),
            "--policy",
            str(policy),
        ],
        check=True,
    )

    input_llm_md = compacto_dir / "04_input_llm_estado_actual_compacto.md"
    resumen_md = compacto_dir / "01_estado_actual_compacto.md"
    referencias_json = compacto_dir / "02_referencias_estado_actual.json"
    resultado_path = output_dir / "resultado_openclaw.json"

    caracteres = len(input_llm_md.read_text(encoding="utf-8")) if input_llm_md.exists() else 0

    resultado = {
        "ok": True,
        "tipo": "pjn_local",
        "indice": str(indice),
        "raw_dir": str(raw_dir),
        "output_dir": str(output_dir),
        "playbook": playbook,
        "policy": str(policy),
        "preanalisis_dir": str(preanalisis_dir),
        "estado_actual_dir": str(estado_dir),
        "estado_actual_compacto_dir": str(compacto_dir),
        "input_llm_md": str(input_llm_md),
        "estado_actual_compacto_md": str(resumen_md),
        "referencias_json": str(referencias_json),
        "caracteres_input_llm": caracteres,
        "tokens_aprox_input_llm": round(caracteres / 4),
    }

    resultado_path.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    typer.echo("Estudio PJN local: ok")
    typer.echo(f"Resultado OpenClaw: {resultado_path}")
    typer.echo(f"Input LLM MD: {input_llm_md}")
    typer.echo(f"Tokens aprox: {round(caracteres / 4)}")
