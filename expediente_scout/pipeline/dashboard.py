"""Dashboard HTML estático y de solo lectura para manifests locales."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from expediente_scout.domain.manifest import cargar_manifest


@dataclass(frozen=True)
class ExpedienteDashboard:
    """Fila resumida del dashboard."""

    expediente_id: str
    jurisdiccion: str
    numero: str
    anio: int
    actuaciones: int
    documentos: int
    seleccionados: int
    ultima_actuacion: str
    manifest_rel: str
    informe_rel: str | None
    pdf_rel: str | None


@dataclass(frozen=True)
class DashboardResultado:
    """Resultado de generación del dashboard."""

    output_path: Path
    expedientes: int
    generated_at: str


def descubrir_manifests(root: Path) -> list[Path]:
    """Busca manifests dentro de data/expedientes sin leer credenciales ni raw."""
    base = Path(root) / "data" / "expedientes"
    if not base.exists():
        return []
    return sorted(base.glob("*/*/manifest.json"))


def _relativo(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _ultima_actuacion(manifest) -> str:
    if not manifest.actuaciones:
        return "Sin actuaciones"
    ordenadas = sorted(manifest.actuaciones, key=lambda act: act.orden)
    ultima = ordenadas[-1]
    fecha = ultima.fecha.isoformat() if ultima.fecha else "sin fecha"
    return f"{fecha} - {ultima.descripcion}"


def cargar_filas_dashboard(root: Path) -> list[ExpedienteDashboard]:
    """Carga datos mínimos de cada manifest, sin modificar archivos fuente."""
    root = Path(root)
    filas: list[ExpedienteDashboard] = []
    for manifest_path in descubrir_manifests(root):
        manifest = cargar_manifest(manifest_path)
        exp = manifest.expediente
        expediente_dir = manifest_path.parent
        informe = expediente_dir / "reports" / "informe.md"
        pdf = expediente_dir / "reports" / "informe.pdf"
        seleccionados = sum(1 for doc in manifest.documentos if doc.ruta_selected)
        filas.append(
            ExpedienteDashboard(
                expediente_id=exp.id,
                jurisdiccion=exp.jurisdiccion,
                numero=exp.numero,
                anio=exp.anio,
                actuaciones=len(manifest.actuaciones),
                documentos=len(manifest.documentos),
                seleccionados=seleccionados,
                ultima_actuacion=_ultima_actuacion(manifest),
                manifest_rel=_relativo(manifest_path, root),
                informe_rel=_relativo(informe, root) if informe.exists() else None,
                pdf_rel=_relativo(pdf, root) if pdf.exists() else None,
            )
        )
    return filas


def _render_link(label: str, rel_path: str | None) -> str:
    if not rel_path:
        return "<span class='muted'>No generado</span>"
    safe = escape(rel_path, quote=True)
    return f"<a href='{safe}'>{escape(label)}</a>"


def render_dashboard_html(filas: list[ExpedienteDashboard], generated_at: str) -> str:
    """Renderiza HTML simple, sin JavaScript ni lectura de datos sensibles."""
    rows: list[str] = []
    for fila in filas:
        rows.append(
            "<tr>"
            f"<td>{escape(fila.expediente_id)}</td>"
            f"<td>{escape(fila.jurisdiccion)}</td>"
            f"<td>{escape(fila.numero)}</td>"
            f"<td>{fila.anio}</td>"
            f"<td>{fila.actuaciones}</td>"
            f"<td>{fila.documentos}</td>"
            f"<td>{fila.seleccionados}</td>"
            f"<td>{escape(fila.ultima_actuacion)}</td>"
            f"<td>{_render_link('manifest', fila.manifest_rel)}</td>"
            f"<td>{_render_link('informe.md', fila.informe_rel)}</td>"
            f"<td>{_render_link('informe.pdf', fila.pdf_rel)}</td>"
            "</tr>"
        )

    cuerpo = "\n".join(rows) if rows else "<tr><td colspan='11'>No hay expedientes locales.</td></tr>"
    return f"""<!doctype html>
<html lang="es">
<head>
 <meta charset="utf-8">
 <title>expediente-scout - Dashboard</title>
 <style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1f2937; }}
 h1 {{ margin-bottom: 0.25rem; }}
 .muted {{ color: #6b7280; }}
 table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
 th, td {{ border: 1px solid #d1d5db; padding: 0.5rem; text-align: left; vertical-align: top; }}
 th {{ background: #f3f4f6; }}
 code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
 </style>
</head>
<body>
 <h1>expediente-scout</h1>
 <p class="muted">Dashboard estático de solo lectura. Generado: {escape(generated_at)}</p>
 <p>Expedientes locales detectados: <strong>{len(filas)}</strong></p>
 <table>
 <thead>
 <tr>
 <th>Expediente</th>
 <th>Jurisdicción</th>
 <th>Número</th>
 <th>Año</th>
 <th>Actuaciones</th>
 <th>Documentos</th>
 <th>Seleccionados</th>
 <th>Última actuación</th>
 <th>Manifest</th>
 <th>Informe MD</th>
 <th>Informe PDF</th>
 </tr>
 </thead>
 <tbody>
 {cuerpo}
 </tbody>
 </table>
 <p class="muted">No incluye credenciales, contenido de PDFs ni datos de archivos <code>.env</code>.</p>
</body>
</html>
"""


def generar_dashboard(root: Path, output: Path | None = None) -> DashboardResultado:
    """Genera un dashboard HTML estático. No modifica manifests ni documentos."""
    root = Path(root)
    if output is None:
        output = root / "data" / "dashboard" / "index.html"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    filas = cargar_filas_dashboard(root)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    html = render_dashboard_html(filas, generated_at)
    output.write_text(html, encoding="utf-8")
    return DashboardResultado(output_path=output, expedientes=len(filas), generated_at=generated_at)
