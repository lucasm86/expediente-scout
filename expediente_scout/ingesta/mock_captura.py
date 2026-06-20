"""Fuente mock determinística para desarrollar sin PJN."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import fitz

from .fuente_captura import ItemIndice


class MockCaptura:
    fuente_id = "mock"

    _items = (
        (1, date(2024, 3, 10), "Presenta demanda", "demanda.pdf", 3),
        (2, date(2024, 4, 5), "Contesta demanda", "contestacion.pdf", 2),
        (3, date(2024, 4, 10), "Provee traslado", "proveido_traslado.pdf", 1),
        (4, date(2024, 5, 20), "Acompaña pericia médica", "pericia_medica.pdf", 4),
        (5, date(2024, 6, 15), "Resolución interlocutoria", "interlocutoria.pdf", 2),
    )

    def __init__(self, base_dir: Path | None = None) -> None:
        self._tempdir: TemporaryDirectory[str] | None = None
        if base_dir is None:
            self._tempdir = TemporaryDirectory(prefix="expediente_scout_mock_")
            self._base_dir = Path(self._tempdir.name)
        else:
            self._base_dir = Path(base_dir)
        self._raw_dir = self._base_dir / "raw"
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._generar_pdfs()

    def ruta_raw(self) -> Path:
        """Devuelve la carpeta raw del mock."""
        return self._raw_dir

    def leer_indice(self) -> list[ItemIndice]:
        """Devuelve cinco actuaciones determinísticas."""
        return [
            ItemIndice(orden=orden, fecha=fecha, descripcion=descripcion, archivo=archivo)
            for orden, fecha, descripcion, archivo, _paginas in self._items
        ]

    def _generar_pdfs(self) -> None:
        for orden, fecha, descripcion, archivo, paginas in self._items:
            self._crear_pdf(self._raw_dir / archivo, orden, fecha, descripcion, archivo, paginas)

    @staticmethod
    def _crear_pdf(path: Path, orden: int, fecha: date, descripcion: str, archivo: str, paginas: int) -> None:
        doc = fitz.open()
        for pagina in range(1, paginas + 1):
            page = doc.new_page(width=595, height=842)
            texto = (
                f"expediente-scout mock\n"
                f"orden: {orden}\n"
                f"fecha: {fecha.isoformat()}\n"
                f"descripcion: {descripcion}\n"
                f"archivo: {archivo}\n"
                f"pagina: {pagina}/{paginas}\n"
            )
            page.insert_text((72, 72), texto, fontsize=11)
        doc.set_metadata({
            "format": "PDF 1.7",
            "title": archivo,
            "author": "expediente-scout",
            "subject": "mock deterministico",
            "keywords": "expediente-scout,paso1,mock",
            "creator": "expediente-scout",
            "producer": "expediente-scout",
            "creationDate": "D:20240101000000-03'00'",
            "modDate": "D:20240101000000-03'00'",
        })
        if path.exists():
            path.unlink()
        doc.save(path, garbage=4, deflate=True, no_new_id=True)
        doc.close()
