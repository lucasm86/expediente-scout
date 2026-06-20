from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from expediente_scout.domain.manifest import cargar_manifest
from expediente_scout.ingesta.script_captura import ScriptCaptura
from expediente_scout.pipeline.capturar import capturar_desde_script


FAKE_SCRIPT = r'''
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

pdf(raw / "real_demanda.pdf", "Presenta demanda real PJN")
pdf(raw / "real_proveido.pdf", "Provee traslado real PJN")
items = [
    {"orden": 1, "fecha": "2024-01-10", "descripcion": "Presenta demanda real", "archivo": "real_demanda.pdf"},
    {"orden": 2, "fecha": "2024-01-20", "descripcion": "Provee traslado real", "archivo": "real_proveido.pdf"},
]
(out / "indice.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
'''


def _crear_fake_script(tmp_path: Path) -> Path:
    script = tmp_path / "fake_captura.py"
    script.write_text(FAKE_SCRIPT, encoding="utf-8")
    return script


def test_script_captura_parsea_indice_json(tmp_path: Path) -> None:
    output = tmp_path / "salida"
    raw = output / "raw"
    raw.mkdir(parents=True)
    (output / "indice.json").write_text(
        json.dumps([
            {"orden": 1, "fecha": "2024-01-10", "descripcion": "Presenta demanda", "archivo": "a.pdf"}
        ]),
        encoding="utf-8",
    )
    fuente = ScriptCaptura(script_path=Path("dummy.py"), output_dir=output)
    items = fuente.leer_indice()
    assert len(items) == 1
    assert items[0].orden == 1
    assert items[0].archivo == "a.pdf"
    assert fuente.ruta_raw() == raw


def test_script_captura_parsea_indice_csv(tmp_path: Path) -> None:
    output = tmp_path / "salida"
    output.mkdir()
    (output / "indice.csv").write_text(
        "orden,fecha,descripcion,archivo\n1,2024-02-01,Presenta escrito,b.pdf\n",
        encoding="utf-8",
    )
    fuente = ScriptCaptura(script_path=Path("dummy.py"), output_dir=output)
    items = fuente.leer_indice()
    assert len(items) == 1
    assert items[0].descripcion == "Presenta escrito"


def test_capturar_desde_script_ingiere_manifest(tmp_path: Path) -> None:
    script = _crear_fake_script(tmp_path)
    env = tmp_path / ".env"
    env.write_text("PJN_USER=usuario\nPJN_PASS=secreto-super-reservado\n", encoding="utf-8")
    if os.name == "posix":
        env.chmod(stat.S_IRUSR | stat.S_IWUSR)

    resultado = capturar_desde_script(
        root=tmp_path,
        jurisdiccion="pjn",
        numero="999",
        anio=2024,
        script_path=script,
        env_path=env,
        timeout=30,
    )
    manifest = cargar_manifest(resultado.manifest_path)
    assert resultado.actuaciones_nuevas == 2
    assert resultado.documentos_nuevos == 2
    assert len(manifest.actuaciones) == 2
    assert len(manifest.documentos) == 2
    assert resultado.indice_path.name == "indice.json"


def test_log_no_persiste_secretos(tmp_path: Path) -> None:
    script = _crear_fake_script(tmp_path)
    env = tmp_path / ".env"
    env.write_text("PJN_PASS=secreto-super-reservado\n", encoding="utf-8")
    if os.name == "posix":
        env.chmod(stat.S_IRUSR | stat.S_IWUSR)

    resultado = capturar_desde_script(
        root=tmp_path,
        jurisdiccion="pjn",
        numero="1000",
        anio=2024,
        script_path=script,
        env_path=env,
        timeout=30,
    )
    log_text = resultado.log_path.read_text(encoding="utf-8")
    assert "secreto-super-reservado" not in log_text
    assert "stdout" not in log_text.lower()
    assert "stderr" not in log_text.lower()


@pytest.mark.skipif(os.name != "posix", reason="permiso POSIX")
def test_env_con_permisos_inseguros_falla(tmp_path: Path) -> None:
    script = _crear_fake_script(tmp_path)
    env = tmp_path / ".env"
    env.write_text("PJN_PASS=secreto\n", encoding="utf-8")
    env.chmod(0o644)

    with pytest.raises(PermissionError):
        capturar_desde_script(
            root=tmp_path,
            jurisdiccion="pjn",
            numero="1001",
            anio=2024,
            script_path=script,
            env_path=env,
            timeout=30,
        )
