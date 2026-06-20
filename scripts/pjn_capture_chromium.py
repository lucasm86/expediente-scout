#!/usr/bin/env python3
"""
pjn_capture_chromium_v2.py

Capturador PJN con Chromium/Playwright para expediente-scout.

Salida contractual SOLO cuando se usa --download-pdfs:
  <output>/raw/*.pdf
  <output>/indice.json
  <output>/indice.csv

Modo seguro por defecto:
  - navega, busca expediente y extrae actuaciones;
  - NO descarga PDFs salvo que se pase --download-pdfs;
  - escribe indice.preview.json para auditar selectores sin tocar documentos.

Uso de prueba local:
  python pjn_capture_chromium_v2.py --selftest

Uso real controlado:
  python pjn_capture_chromium_v2.py \
    --jurisdiccion pjn --numero 12345 --anio 2024 \
    --output /tmp/pjn-out \
    --env-path .env.pjn.capture \
    --headless \
    --download-pdfs

Notas de seguridad:
- No imprime usuario, clave, cookies ni tokens.
- No intenta evadir captcha ni controles de acceso.
- Si detecta captcha, corta.
- Exige chmod 600 en env-path sobre POSIX.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

try:
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        Locator,
        Page,
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Falta dependencia playwright. Instalar con: pip install playwright && python -m playwright install chromium"
    ) from exc


class CaptureError(RuntimeError):
    """Error controlado de captura, sin filtrar credenciales."""


@dataclass(frozen=True)
class Selectors:
    username: str | None
    password: str | None
    login_button: str | None
    search_camara: str | None
    search_numero: str | None
    search_anio: str | None
    search_button: str | None
    result_link: str | None
    expediente_ready: str | None
    rows: str
    row_fecha: str
    row_descripcion: str
    row_pdf: str
    viewer_download: str | None
    captcha: str | None


@dataclass(frozen=True)
class Config:
    jurisdiccion: str
    numero: str
    anio: int
    output: Path
    env_path: Path | None
    headless: bool
    timeout_ms: int
    start_url: str | None
    search_url_template: str | None
    username_value: str | None
    password_value: str | None
    camara_value: str | None
    selectors: Selectors
    fixture_dir: Path | None = None
    slowmo_ms: int = 0
    download_pdfs: bool = False


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_env_file(path: Path | None) -> dict[str, str]:
    """Carga .env simple KEY=VALUE sin expandir secretos ni imprimirlos."""
    if path is None:
        return {}
    if not path.exists():
        raise CaptureError(f"No existe env-path: {path}")
    if os.name == "posix":
        mode = path.stat().st_mode & 0o777
        if mode != 0o600:
            raise CaptureError(f"Permisos inseguros en {path}. Usar: chmod 600 {path}")
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def env_get(env_file: dict[str, str], key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key)
    if value not in (None, ""):
        return value
    value = env_file.get(key)
    if value not in (None, ""):
        return value
    return default


def sanitize_filename(value: str, fallback: str = "documento") -> str:
    value = value.strip().lower()
    value = re.sub(r"[áàäâ]", "a", value)
    value = re.sub(r"[éèëê]", "e", value)
    value = re.sub(r"[íìïî]", "i", value)
    value = re.sub(r"[óòöô]", "o", value)
    value = re.sub(r"[úùüû]", "u", value)
    value = re.sub(r"ñ", "n", value)
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._-")
    return value[:140] or fallback


def parse_date(value: str) -> str | None:
    value = " ".join(value.strip().split())
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value[:10], fmt).date().isoformat()
        except ValueError:
            pass
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", value)
    if match:
        d, m, y = match.groups()
        try:
            return datetime(int(y), int(m), int(d)).date().isoformat()
        except ValueError:
            return None
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_output_dirs(output: Path) -> tuple[Path, Path]:
    raw = output / "raw"
    output.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    return output, raw


def detect_captcha(page: Page, selector: str | None) -> bool:
    try:
        if selector and page.locator(selector).count() > 0:
            return True
    except Exception:
        pass
    try:
        text = page.locator("body").inner_text(timeout=1500).lower()
    except Exception:
        text = ""
    markers = ["captcha", "recaptcha", "no soy un robot", "robot"]
    return any(marker in text for marker in markers)


def fill_if_configured(page: Page, selector: str | None, value: str, label: str, timeout_ms: int) -> bool:
    if not selector:
        return False

    value = str(value)
    locator = page.locator(selector).first

    # Primer intento: fill normal de Playwright.
    try:
        locator.fill(value, timeout=timeout_ms)
        return True
    except Exception:
        pass

    # Fallback para formularios JSF donde el input existe pero está oculto.
    filled = page.evaluate(
        """
        ({ selector, value, label }) => {
            const el = document.querySelector(selector);
            if (!el) {
                throw new Error(`No existe selector para ${label}: ${selector}`);
            }

            el.value = value;
            el.setAttribute('value', value);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));

            return {
                id: el.id || '',
                name: el.getAttribute('name') || '',
                value: el.value || ''
            };
        }
        """,
        {"selector": selector, "value": value, "label": label},
    )

    print(f"Campo {label} configurado por JS: {filled['id'] or filled['name']} = {filled['value']}")
    return True

def click_if_configured(page: Page, selector: str | None, label: str, timeout_ms: int) -> bool:
    if not selector:
        return False

    locator = page.locator(selector).first

    # Primer intento: click normal de Playwright.
    try:
        locator.click(timeout=timeout_ms)
        return True
    except Exception:
        pass

    # Fallback para JSF donde el botón existe pero está oculto.
    clicked = page.evaluate(
        """
        ({ selector, label }) => {
            const el = document.querySelector(selector);
            if (!el) {
                throw new Error(`No existe selector para ${label}: ${selector}`);
            }

            const form = el.form;

            el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
            el.dispatchEvent(new MouseEvent('click', { bubbles: true }));

            if (typeof el.click === 'function') {
                el.click();
            }

            return {
                id: el.id || '',
                name: el.getAttribute('name') || '',
                value: el.getAttribute('value') || '',
                form_id: form ? (form.id || form.getAttribute('name') || '') : ''
            };
        }
        """,
        {"selector": selector, "label": label},
    )

    print(f"Botón {label} clickeado por JS: {clicked['id'] or clicked['name']} = {clicked['value']}")
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass

    return True

def select_option_if_configured(page: Page, selector: str | None, value: str | None, label: str, timeout_ms: int) -> bool:
    if not selector:
        return False
    if value is None or str(value).strip() == "":
        raise CaptureError(f"Selector configurado para {label}, pero falta valor PJN_CAMARA_VALUE")

    value = str(value).strip()
    locator = page.locator(selector).first

    # Primer intento: selección normal de Playwright por value.
    try:
        locator.select_option(value=value, timeout=timeout_ms)
        return True
    except Exception:
        pass

    # Fallback para JSF/PrimeFaces/Bootstrap: el <select> existe pero está oculto.
    # En ese caso seteamos el value real y disparamos eventos input/change.
    selected = page.evaluate(
        """
        ({ selector, value, label }) => {
            const el = document.querySelector(selector);
            if (!el) {
                throw new Error(`No existe selector para ${label}: ${selector}`);
            }

            const options = Array.from(el.options || []);
            const found =
                options.find(o => String(o.value).trim() === String(value).trim()) ||
                options.find(o => String(o.textContent || '').trim() === String(value).trim()) ||
                options.find(o => String(o.textContent || '').includes(String(value).trim()));

            if (!found) {
                const available = options.map(o => `${o.value}:${String(o.textContent || '').trim()}`).join(' | ');
                throw new Error(`No se encontró opción ${value} para ${label}. Opciones: ${available}`);
            }

            el.value = found.value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));

            return {
                value: found.value,
                text: String(found.textContent || '').trim()
            };
        }
        """,
        {"selector": selector, "value": value, "label": label},
    )

    print(f"Selector {label} configurado por JS: {selected['value']} - {selected['text']}")
    return True


def wait_settle(page: Page, timeout_ms: int) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        page.wait_for_timeout(750)


def login_if_needed(page: Page, cfg: Config) -> None:
    if cfg.fixture_dir:
        return
    if not cfg.start_url:
        raise CaptureError("Falta PJN_START_URL/PJN_LOGIN_URL o --fixture-dir para pruebas")

    page.goto(cfg.start_url, wait_until="domcontentloaded", timeout=cfg.timeout_ms)
    wait_settle(page, cfg.timeout_ms)
    if detect_captcha(page, cfg.selectors.captcha):
        raise CaptureError("Captcha detectado. No se automatiza ni se evade.")

    # Si SCW ya está logueado, los campos pueden no existir. Solo intenta login si aparece el campo.
    if cfg.selectors.username and page.locator(cfg.selectors.username).count() > 0:
        fill_if_configured(page, cfg.selectors.username, cfg.username_value, "usuario", cfg.timeout_ms)
        fill_if_configured(page, cfg.selectors.password, cfg.password_value, "clave", cfg.timeout_ms)
        click_if_configured(page, cfg.selectors.login_button, "botón login", cfg.timeout_ms)
        wait_settle(page, cfg.timeout_ms)
        if detect_captcha(page, cfg.selectors.captcha):
            raise CaptureError("Captcha detectado después del login. No se automatiza ni se evade.")


def maybe_open_result(page: Page, cfg: Config) -> None:
    """Abre el expediente desde el listado de relacionados si todavía no está la tabla interna."""
    if page.locator(cfg.selectors.rows).count() > 0:
        return

    if cfg.selectors.result_link:
        page.locator(cfg.selectors.result_link).first.click(timeout=cfg.timeout_ms)
        wait_settle(page, cfg.timeout_ms)
        return

    # Fallback conservador para JSF/SCW: buscar textos típicos. Si no encuentra, falla claro.
    candidates = [
        "a:has-text('visualizar expediente')",
        "a:has-text('Visualizar expediente')",
        "input[value*='visualizar expediente' i]",
        "input[value*='Visualizar expediente' i]",
        "a[href*='expediente.seam']",
    ]
    for selector in candidates:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.click(timeout=cfg.timeout_ms)
                wait_settle(page, cfg.timeout_ms)
                return
        except Exception:
            continue
    raise CaptureError(
        "No se encontró tabla de actuaciones ni link de resultado. Configurar PJN_SELECTOR_RESULT_LINK."
    )


def open_expediente(page: Page, cfg: Config) -> None:
    if cfg.fixture_dir:
        index = cfg.fixture_dir / "index.html"
        if not index.exists():
            raise CaptureError(f"Fixture incompleto: falta {index}")
        page.set_content(index.read_text(encoding="utf-8"), wait_until="domcontentloaded", timeout=cfg.timeout_ms)
        return

    if cfg.search_url_template:
        url = cfg.search_url_template.format(
            jurisdiccion=cfg.jurisdiccion,
            numero=cfg.numero,
            anio=cfg.anio,
        )
        page.goto(url, wait_until="domcontentloaded", timeout=cfg.timeout_ms)
        wait_settle(page, cfg.timeout_ms)
        maybe_open_result(page, cfg)
        return

    select_option_if_configured(page, cfg.selectors.search_camara, cfg.camara_value, "cámara/fuero", cfg.timeout_ms)
    fill_if_configured(page, cfg.selectors.search_numero, cfg.numero, "número expediente", cfg.timeout_ms)
    fill_if_configured(page, cfg.selectors.search_anio, str(cfg.anio), "año expediente", cfg.timeout_ms)
    click_if_configured(page, cfg.selectors.search_button, "botón búsqueda", cfg.timeout_ms)
    wait_settle(page, cfg.timeout_ms)
    maybe_open_result(page, cfg)

    if cfg.selectors.expediente_ready:
        page.locator(cfg.selectors.expediente_ready).first.wait_for(timeout=cfg.timeout_ms)


def resolve_link(page_url: str, href: str) -> str:
    return urljoin(page_url, href)


def save_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def download_via_request(page: Page, cfg: Config, href: str, dest: Path) -> bool:
    absolute = resolve_link(page.url, href)
    parsed = urlparse(absolute)

    if cfg.fixture_dir and not parsed.scheme:
        src = (cfg.fixture_dir / href).resolve()
        if not src.exists():
            raise CaptureError(f"PDF fixture inexistente: {src}")
        shutil.copy2(src, dest)
        return True

    if parsed.scheme == "file":
        src = Path(parsed.path)
        if not src.exists():
            raise CaptureError(f"PDF fixture inexistente: {src}")
        shutil.copy2(src, dest)
        return True

    response = page.context.request.get(absolute, timeout=cfg.timeout_ms)
    if not response.ok:
        return False
    data = response.body()
    if data.startswith(b"%PDF"):
        save_bytes(dest, data)
        return True
    return False


def download_via_click_or_viewer(page: Page, cfg: Config, row_locator: Locator, link_selector: str, dest: Path) -> None:
    link = row_locator.locator(link_selector).first

    # Caso 1: click genera descarga directa.
    try:
        with page.expect_download(timeout=cfg.timeout_ms) as download_info:
            link.click(timeout=cfg.timeout_ms)
        download = download_info.value
        download.save_as(dest)
        return
    except PlaywrightTimeoutError:
        pass

    # Caso 2: click abre popup/visor.
    viewer_page: Page | None = None
    try:
        with page.expect_popup(timeout=3000) as popup_info:
            link.click(timeout=cfg.timeout_ms)
        viewer_page = popup_info.value
        wait_settle(viewer_page, cfg.timeout_ms)
    except PlaywrightTimeoutError:
        viewer_page = page

    if cfg.selectors.viewer_download:
        try:
            with viewer_page.expect_download(timeout=cfg.timeout_ms) as download_info:
                viewer_page.locator(cfg.selectors.viewer_download).first.click(timeout=cfg.timeout_ms)
            download = download_info.value
            download.save_as(dest)
            return
        except PlaywrightTimeoutError as exc:
            raise CaptureError("El visor abrió, pero no entregó descarga con PJN_SELECTOR_VIEWER_DOWNLOAD") from exc

    # Último fallback: si el viewer navega a PDF embebido, pedir la URL actual.
    if viewer_page.url and viewer_page.url != "about:blank":
        if download_via_request(viewer_page, cfg, viewer_page.url, dest):
            return

    raise CaptureError(
        "No se pudo descargar PDF: configurar PJN_SELECTOR_VIEWER_DOWNLOAD o revisar comportamiento del viewer."
    )


def build_filename(order: int, fecha_iso: str | None, descripcion: str, used_names: set[str]) -> str:
    base_name = sanitize_filename(f"{order:04d}_{fecha_iso or 'sin_fecha'}_{descripcion}")
    filename = f"{base_name}.pdf"
    suffix = 2
    while filename in used_names:
        filename = f"{base_name}_{suffix}.pdf"
        suffix += 1
    used_names.add(filename)
    return filename


def extract_rows(page: Page, cfg: Config) -> list[dict[str, Any]]:
    rows = page.locator(cfg.selectors.rows)
    count = rows.count()
    if count == 0:
        raise CaptureError(f"No se encontraron actuaciones con selector: {cfg.selectors.rows}")

    index: list[dict[str, Any]] = []
    used_names: set[str] = set()

    for i in range(count):
        row = rows.nth(i)
        fecha_txt = row.locator(cfg.selectors.row_fecha).first.inner_text(timeout=cfg.timeout_ms).strip()
        descripcion = row.locator(cfg.selectors.row_descripcion).first.inner_text(timeout=cfg.timeout_ms).strip()
        link = row.locator(cfg.selectors.row_pdf).first
        href = link.get_attribute("href")
        fecha_iso = parse_date(fecha_txt)
        filename = build_filename(i + 1, fecha_iso, descripcion, used_names)
        index.append(
            {
                "orden": i + 1,
                "fecha": fecha_iso,
                "descripcion": " ".join(descripcion.split()),
                "archivo": filename if cfg.download_pdfs else None,
                "href_detectado": bool(href),
                "sha256": None,
            }
        )
    return index


def download_rows(page: Page, cfg: Config, index: list[dict[str, Any]]) -> None:
    _, raw_dir = ensure_output_dirs(cfg.output)
    rows = page.locator(cfg.selectors.rows)
    for i, item in enumerate(index):
        row = rows.nth(i)
        link = row.locator(cfg.selectors.row_pdf).first
        filename = item["archivo"]
        if not filename:
            raise CaptureError("Estado interno inválido: archivo vacío con --download-pdfs")
        dest = raw_dir / filename
        href = link.get_attribute("href")
        ok = False
        if href:
            ok = download_via_request(page, cfg, href, dest)
        if not ok:
            download_via_click_or_viewer(page, cfg, row, cfg.selectors.row_pdf, dest)
        if not dest.exists() or dest.stat().st_size == 0:
            raise CaptureError(f"PDF vacío o faltante: {dest.name}")
        # Validación suave. PJN puede servir application/pdf sin prefijo legible por wrapper, pero si el archivo local no parece PDF, cortar.
        if dest.read_bytes()[:4] != b"%PDF":
            raise CaptureError(f"El archivo descargado no parece PDF: {dest.name}")
        item["sha256"] = sha256_file(dest)
        item.pop("href_detectado", None)


def write_index(output: Path, index: list[dict[str, Any]], download_pdfs: bool) -> Path:
    if download_pdfs:
        clean = [
            {
                "orden": item["orden"],
                "fecha": item["fecha"],
                "descripcion": item["descripcion"],
                "archivo": item["archivo"],
                "sha256": item["sha256"],
            }
            for item in index
        ]
        path = output / "indice.json"
        csv_path = output / "indice.csv"
        path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["orden", "fecha", "descripcion", "archivo", "sha256"])
            writer.writeheader()
            writer.writerows(clean)
        return path

    preview = [
        {
            "orden": item["orden"],
            "fecha": item["fecha"],
            "descripcion": item["descripcion"],
            "archivo_previsto": build_filename(item["orden"], item["fecha"], item["descripcion"], set()),
            "href_detectado": item.get("href_detectado", False),
        }
        for item in index
    ]
    path = output / "indice.preview.json"
    path.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_capture_log(output: Path, status: str, details: dict[str, Any]) -> None:
    safe_details = dict(details)
    for key in list(safe_details):
        if any(marker in key.lower() for marker in ("password", "clave", "secret", "token", "cookie")):
            safe_details[key] = "[redacted]"
    log_dir = output / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "status": status,
        "details": safe_details,
    }
    (log_dir / "capture.log.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def launch_chromium(pw: Any, cfg: Config) -> Browser:
    candidates: list[str] = []
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    last_exc: Exception | None = None
    for executable in candidates:
        try:
            return pw.chromium.launch(
                headless=cfg.headless,
                slow_mo=cfg.slowmo_ms,
                executable_path=executable,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception as exc:
            last_exc = exc
    try:
        return pw.chromium.launch(
            headless=cfg.headless,
            slow_mo=cfg.slowmo_ms,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
    except Exception as exc:
        raise CaptureError(
            "No se pudo lanzar Chromium. Instalar con: sudo apt install -y chromium o python -m playwright install chromium"
        ) from (last_exc or exc)


def run_capture(cfg: Config) -> Path:
    ensure_output_dirs(cfg.output)
    with sync_playwright() as p:
        browser = launch_chromium(p, cfg)
        context: BrowserContext = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(cfg.timeout_ms)
        try:
            login_if_needed(page, cfg)
            open_expediente(page, cfg)
            if detect_captcha(page, cfg.selectors.captcha):
                raise CaptureError("Captcha detectado. No se automatiza ni se evade.")
            index = extract_rows(page, cfg)
            if cfg.download_pdfs:
                download_rows(page, cfg, index)
            index_path = write_index(cfg.output, index, cfg.download_pdfs)
            write_capture_log(
                cfg.output,
                "ok",
                {
                    "jurisdiccion": cfg.jurisdiccion,
                    "numero": cfg.numero,
                    "anio": cfg.anio,
                    "documentos": len(index),
                    "modo": "descarga" if cfg.download_pdfs else "preview_sin_descarga",
                    "indice": str(index_path),
                },
            )
            return index_path
        finally:
            context.close()
            browser.close()


def build_config(args: argparse.Namespace) -> Config:
    env_file = load_env_file(Path(args.env_path) if args.env_path else None)
    selectors = Selectors(
        username=env_get(env_file, "PJN_SELECTOR_USERNAME"),
        password=env_get(env_file, "PJN_SELECTOR_PASSWORD"),
        login_button=env_get(env_file, "PJN_SELECTOR_LOGIN_BUTTON"),
        search_camara=env_get(env_file, "PJN_SELECTOR_SEARCH_CAMARA"),
        search_numero=env_get(env_file, "PJN_SELECTOR_SEARCH_NUMERO"),
        search_anio=env_get(env_file, "PJN_SELECTOR_SEARCH_ANIO"),
        search_button=env_get(env_file, "PJN_SELECTOR_SEARCH_BUTTON"),
        result_link=env_get(env_file, "PJN_SELECTOR_RESULT_LINK"),
        expediente_ready=env_get(env_file, "PJN_SELECTOR_EXPEDIENTE_READY"),
        rows=env_get(env_file, "PJN_SELECTOR_ROWS", ".actuacion") or ".actuacion",
        row_fecha=env_get(env_file, "PJN_SELECTOR_ROW_FECHA", ".fecha") or ".fecha",
        row_descripcion=env_get(env_file, "PJN_SELECTOR_ROW_DESCRIPCION", ".descripcion") or ".descripcion",
        row_pdf=env_get(env_file, "PJN_SELECTOR_ROW_PDF", "a.pdf") or "a.pdf",
        viewer_download=env_get(env_file, "PJN_SELECTOR_VIEWER_DOWNLOAD"),
        captcha=env_get(env_file, "PJN_SELECTOR_CAPTCHA"),
    )
    return Config(
        jurisdiccion=args.jurisdiccion,
        numero=args.numero,
        anio=int(args.anio),
        output=Path(args.output).resolve(),
        env_path=Path(args.env_path).resolve() if args.env_path else None,
        headless=bool(args.headless),
        timeout_ms=int(args.timeout_ms),
        start_url=env_get(env_file, "PJN_START_URL", env_get(env_file, "PJN_LOGIN_URL", args.login_url)),
        search_url_template=env_get(env_file, "PJN_SEARCH_URL_TEMPLATE", args.search_url_template),
        username_value=env_get(env_file, "PJN_USERNAME"),
        password_value=env_get(env_file, "PJN_PASSWORD"),
        camara_value=env_get(env_file, "PJN_CAMARA_VALUE"),
        selectors=selectors,
        fixture_dir=Path(args.fixture_dir).resolve() if args.fixture_dir else None,
        slowmo_ms=int(args.slowmo_ms),
        download_pdfs=bool(args.download_pdfs),
    )


def make_minimal_pdf(path: Path, text: str) -> None:
    payload = f"%PDF-1.4\n1 0 obj<<>>endobj\n2 0 obj<< /Length {len(text)+60} >>stream\nBT /F1 12 Tf 72 720 Td ({text}) Tj ET\nendstream endobj\ntrailer<<>>\n%%EOF\n"
    path.write_bytes(payload.encode("latin-1", errors="ignore"))


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        fixture = base / "fixture"
        pdfs = fixture / "pdfs"
        output_preview = base / "out-preview"
        output_download = base / "out-download"
        pdfs.mkdir(parents=True)
        make_minimal_pdf(pdfs / "demanda.pdf", "Demanda fixture")
        make_minimal_pdf(pdfs / "proveido.pdf", "Proveido fixture")
        (fixture / "index.html").write_text(
            """
            <!doctype html><meta charset='utf-8'>
            <table id='expediente:action-table'>
              <tr class='actuacion'>
                <td>Oficina</td><td></td><td class='fecha'>10/03/2024</td><td>Tipo</td>
                <td class='descripcion'>Presenta demanda</td><td><a class='pdf' href='pdfs/demanda.pdf'>Descargar</a></td>
              </tr>
              <tr class='actuacion'>
                <td>Oficina</td><td></td><td class='fecha'>20/03/2024</td><td>Tipo</td>
                <td class='descripcion'>Provee traslado</td><td><a class='pdf' href='pdfs/proveido.pdf'>Ver</a></td>
              </tr>
            </table>
            """,
            encoding="utf-8",
        )
        selectors = Selectors(
            username=None,
            password=None,
            login_button=None,
            search_camara=None,
            search_numero=None,
            search_anio=None,
            search_button=None,
            result_link=None,
            expediente_ready=None,
            rows=".actuacion",
            row_fecha=".fecha",
            row_descripcion=".descripcion",
            row_pdf="a.pdf",
            viewer_download=None,
            captcha=None,
        )
        base_cfg = dict(
            jurisdiccion="pjn",
            numero="999",
            anio=2024,
            env_path=None,
            headless=True,
            timeout_ms=10_000,
            start_url=None,
            search_url_template=None,
            username_value=None,
            password_value=None,
            camara_value=None,
            selectors=selectors,
            fixture_dir=fixture,
        )
        cfg_preview = Config(output=output_preview, download_pdfs=False, **base_cfg)
        preview_path = run_capture(cfg_preview)
        preview = json.loads(preview_path.read_text(encoding="utf-8"))
        assert preview_path.name == "indice.preview.json"
        assert len(preview) == 2
        assert not (output_preview / "indice.json").exists()

        cfg_download = Config(output=output_download, download_pdfs=True, **base_cfg)
        index_path = run_capture(cfg_download)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert index_path.name == "indice.json"
        assert len(index) == 2, index
        assert (output_download / "raw" / index[0]["archivo"]).exists()
        assert index[0]["fecha"] == "2024-03-10"
        assert index[0]["descripcion"] == "Presenta demanda"
        assert index[0]["sha256"]
        assert (output_download / "indice.csv").exists()
        assert (output_download / "logs" / "capture.log.json").exists()
        print("SELFTEST OK")
        print(f"Preview fixture: {output_preview}")
        print(f"Download fixture: {output_download}")
        return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capturador PJN Chromium → raw/ + indice.json")
    parser.add_argument("--jurisdiccion", default="pjn")
    parser.add_argument("--numero", default="0")
    parser.add_argument("--anio", type=int, default=datetime.now().year)
    parser.add_argument("--output", default="pjn-output")
    parser.add_argument("--env-path", default=None)
    parser.add_argument("--login-url", default=None, help="Alias retrocompatible de PJN_START_URL/PJN_LOGIN_URL")
    parser.add_argument("--search-url-template", default=None)
    parser.add_argument("--fixture-dir", default=None, help="Modo prueba: carpeta con index.html y PDFs locales")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--slowmo-ms", type=int, default=0)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--download-pdfs", action="store_true", help="Habilita descarga real y salida contractual raw/ + indice.json")
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.selftest:
        return selftest()
    try:
        cfg = build_config(args)
        index_path = run_capture(cfg)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        print("Captura: ok")
        print(f"Modo: {'descarga' if cfg.download_pdfs else 'preview_sin_descarga'}")
        print(f"Output: {cfg.output}")
        print(f"Raw: {cfg.output / 'raw'}")
        print(f"Índice: {index_path}")
        print(f"Actuaciones detectadas: {len(index)}")
        if not cfg.download_pdfs:
            print("Descarga PDFs: no")
            print("Para salida contractual usar: --download-pdfs")
        else:
            print(f"Documentos: {len(index)}")
        return 0
    except CaptureError as exc:
        eprint("Captura: error")
        eprint(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
