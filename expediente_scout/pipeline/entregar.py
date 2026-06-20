"""Exportación y entrega local de informes."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import fitz


class LockActivo(RuntimeError):
    """Señala que otro proceso ya trabaja sobre el mismo expediente."""


@dataclass(frozen=True)
class EntregaPreparada:
    """Resultado de preparar una entrega."""

    ruta_json: Path
    ruta_pdf: Path
    chunks: int
    destino: str


def _expediente_dir(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return Path(root) / "data" / "expedientes" / jurisdiccion / f"{numero}-{anio}"


def _reports_dir(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return _expediente_dir(root, jurisdiccion, numero, anio) / "reports"


def _logs_dir(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return _expediente_dir(root, jurisdiccion, numero, anio) / "logs"


def _informe_md(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return _reports_dir(root, jurisdiccion, numero, anio) / "informe.md"


def _informe_pdf(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return _reports_dir(root, jurisdiccion, numero, anio) / "informe.pdf"


def _lock_path(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    return _logs_dir(root, jurisdiccion, numero, anio) / "locks" / "expediente.lock"


def adquirir_lock(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    """Crea un lock exclusivo por expediente."""
    lock = _lock_path(root, jurisdiccion, numero, anio)
    lock.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "jurisdiccion": jurisdiccion,
        "numero": numero,
        "anio": anio,
        "pid": os.getpid(),
        "creado": datetime.now(timezone.utc).isoformat(),
    }
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise LockActivo(f"Ya existe un proceso activo para {jurisdiccion}-{numero}-{anio}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return lock


def liberar_lock(lock: Path) -> None:
    """Elimina un lock previamente adquirido."""
    try:
        Path(lock).unlink()
    except FileNotFoundError:
        pass


@contextmanager
def lock_expediente(root: Path, jurisdiccion: str, numero: str, anio: int) -> Iterator[Path]:
    """Context manager de lock por expediente."""
    lock = adquirir_lock(root, jurisdiccion, numero, anio)
    try:
        yield lock
    finally:
        liberar_lock(lock)


def partir_mensaje(texto: str, limite: int = 1200) -> list[str]:
    """Parte texto largo en chunks aptos para mensajería."""
    if limite < 50:
        raise ValueError("El límite mínimo razonable es 50 caracteres")
    texto = texto.strip()
    if not texto:
        return []

    partes: list[str] = []
    actual = ""
    bloques = texto.split("\n\n")
    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
        candidato = bloque if not actual else f"{actual}\n\n{bloque}"
        if len(candidato) <= limite:
            actual = candidato
            continue
        if actual:
            partes.append(actual)
            actual = ""
        while len(bloque) > limite:
            corte = bloque.rfind(" ", 0, limite)
            if corte < limite // 2:
                corte = limite
            partes.append(bloque[:corte].strip())
            bloque = bloque[corte:].strip()
        if bloque:
            actual = bloque
    if actual:
        partes.append(actual)
    return partes


def exportar_pdf_informe(root: Path, jurisdiccion: str, numero: str, anio: int) -> Path:
    """Exporta reports/informe.md a reports/informe.pdf usando PyMuPDF."""
    md = _informe_md(root, jurisdiccion, numero, anio)
    if not md.exists():
        raise FileNotFoundError(f"No existe informe Markdown: {md}")
    pdf = _informe_pdf(root, jurisdiccion, numero, anio)
    pdf.parent.mkdir(parents=True, exist_ok=True)

    texto = md.read_text(encoding="utf-8")
    doc = fitz.open()
    page_width, page_height = 595, 842
    margin = 42
    fontsize = 10
    line_height = 13
    usable_width = page_width - (margin * 2)
    max_lines = int((page_height - (margin * 2)) / line_height)

    def wrap_line(line: str) -> list[str]:
        if not line:
            return [""]
        approx_chars = max(40, int(usable_width / (fontsize * 0.52)))
        wrapped: list[str] = []
        current = line
        while len(current) > approx_chars:
            cut = current.rfind(" ", 0, approx_chars)
            if cut < approx_chars // 2:
                cut = approx_chars
            wrapped.append(current[:cut])
            current = current[cut:].lstrip()
        wrapped.append(current)
        return wrapped

    lines: list[str] = []
    for raw_line in texto.splitlines():
        lines.extend(wrap_line(raw_line))

    for start in range(0, max(1, len(lines)), max_lines):
        page = doc.new_page(width=page_width, height=page_height)
        y = margin
        for line in lines[start : start + max_lines]:
            page.insert_text((margin, y), line, fontsize=fontsize, fontname="helv")
            y += line_height
    if doc.page_count == 0:
        page = doc.new_page(width=page_width, height=page_height)
        page.insert_text((margin, margin), "Informe vacío", fontsize=fontsize, fontname="helv")
    doc.save(pdf)
    doc.close()
    return pdf


def preparar_entrega(
    root: Path,
    jurisdiccion: str,
    numero: str,
    anio: int,
    destino: str,
    limite_mensaje: int = 1200,
) -> EntregaPreparada:
    """Prepara un JSON de entrega para OpenClaw/WhatsApp sin enviar nada."""
    md = _informe_md(root, jurisdiccion, numero, anio)
    if not md.exists():
        raise FileNotFoundError(f"No existe informe Markdown: {md}")
    pdf = exportar_pdf_informe(root, jurisdiccion, numero, anio)
    texto = md.read_text(encoding="utf-8")
    chunks = partir_mensaje(texto, limite=limite_mensaje)
    logs = _logs_dir(root, jurisdiccion, numero, anio) / "entregas"
    logs.mkdir(parents=True, exist_ok=True)
    ruta_json = logs / f"entrega-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    root_path = Path(root).resolve()
    try:
        adjunto = str(pdf.resolve().relative_to(root_path))
    except ValueError:
        adjunto = str(pdf)
    payload = {
        "tipo": "whatsapp_preparado",
        "enviado": False,
        "destino": destino,
        "jurisdiccion": jurisdiccion,
        "numero": numero,
        "anio": anio,
        "creado": datetime.now(timezone.utc).isoformat(),
        "mensaje_chunks": chunks,
        "adjuntos": [adjunto],
        "nota": "Entrega preparada para adaptador externo. No se envió WhatsApp real.",
    }
    ruta_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return EntregaPreparada(ruta_json=ruta_json, ruta_pdf=pdf, chunks=len(chunks), destino=destino)
