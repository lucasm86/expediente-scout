from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from expediente_scout.cli import app
from expediente_scout.ingesta.mock_captura import MockCaptura
from expediente_scout.pipeline.curar import curar_expediente
from expediente_scout.pipeline.dashboard import cargar_filas_dashboard, generar_dashboard
from expediente_scout.pipeline.ingerir import ingerir_captura
from expediente_scout.pipeline.normalizar import normalizar_expediente

runner = CliRunner()


def _preparar_expediente(root: Path, numero: str = "1111") -> Path:
 manifest_path = ingerir_captura(
 root=root,
 jurisdiccion="pjn",
 numero=numero,
 anio=2024,
 fuente=MockCaptura(estado="ampliado"),
 )
 normalizar_expediente(root=root, jurisdiccion="pjn", numero=numero, anio=2024)
 curar_expediente(root=root, jurisdiccion="pjn", numero=numero, anio=2024)
 return manifest_path


def test_dashboard_genera_html_con_expediente(tmp_path: Path) -> None:
 _preparar_expediente(tmp_path)

 resultado = generar_dashboard(root=tmp_path)

 assert resultado.expedientes == 1
 assert resultado.output_path.exists()
 html = resultado.output_path.read_text(encoding="utf-8")
 assert "pjn-1111-2024" in html
 assert "Dashboard estático de solo lectura" in html
 assert "Actuaciones" in html


def test_dashboard_no_lee_ni_expone_env(tmp_path: Path) -> None:
 _preparar_expediente(tmp_path)
 (tmp_path / ".env").write_text("PJN_PASSWORD=SECRETO_SUPER_OBVIO\n", encoding="utf-8")

 resultado = generar_dashboard(root=tmp_path)
 html = resultado.output_path.read_text(encoding="utf-8")

 assert "SECRETO_SUPER_OBVIO" not in html
 assert "PJN_PASSWORD" not in html


def test_dashboard_vacio_es_valido(tmp_path: Path) -> None:
 resultado = generar_dashboard(root=tmp_path)
 html = resultado.output_path.read_text(encoding="utf-8")

 assert resultado.expedientes == 0
 assert "No hay expedientes locales" in html


def test_dashboard_no_modifica_manifest(tmp_path: Path) -> None:
 manifest_path = _preparar_expediente(tmp_path)
 antes = json.loads(manifest_path.read_text(encoding="utf-8"))

 generar_dashboard(root=tmp_path)

 despues = json.loads(manifest_path.read_text(encoding="utf-8"))
 assert antes == despues


def test_cargar_filas_dashboard_resume_datos(tmp_path: Path) -> None:
 _preparar_expediente(tmp_path)

 filas = cargar_filas_dashboard(tmp_path)

 assert len(filas) == 1
 fila = filas[0]
 assert fila.expediente_id == "pjn-1111-2024"
 assert fila.actuaciones == 7
 assert fila.documentos == 7
 assert fila.seleccionados == 7
 assert fila.manifest_rel.endswith("manifest.json")


def test_cli_dashboard(tmp_path: Path) -> None:
 _preparar_expediente(tmp_path)
 output = tmp_path / "dashboard.html"

 result = runner.invoke(app, ["dashboard", "--root", str(tmp_path), "--output", str(output)])

 assert result.exit_code == 0
 assert "Dashboard:" in result.stdout
 assert "Expedientes: 1" in result.stdout
 assert "Solo lectura: sí" in result.stdout
 assert output.exists()
