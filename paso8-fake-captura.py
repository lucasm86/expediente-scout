from __future__ import annotations
import argparse
import json
from pathlib import Path
import fitz

parser = argparse.ArgumentParser()
parser.add_argument("--jurisdiccion", required=True)
parser.add_argument("--numero", required=True)
parser.add_argument("--anio", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

out = Path(args.output)
raw = out / "raw"
raw.mkdir(parents=True, exist_ok=True)

def pdf(path: Path, texto: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), texto)
    doc.save(path)
    doc.close()

pdf(raw / "captura_real_demanda.pdf", "Presenta demanda desde script externo")
pdf(raw / "captura_real_proveido.pdf", "Provee traslado desde script externo")
(out / "indice.json").write_text(json.dumps([
    {"orden": 1, "fecha": "2024-01-10", "descripcion": "Presenta demanda desde script externo", "archivo": "captura_real_demanda.pdf"},
    {"orden": 2, "fecha": "2024-01-20", "descripcion": "Provee traslado desde script externo", "archivo": "captura_real_proveido.pdf"}
], ensure_ascii=False), encoding="utf-8")
