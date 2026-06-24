from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re
import unicodedata

import yaml


POLICY_DEFAULT_PATH = Path("config/document_policies/estado_actual_v1.yaml")


@dataclass(frozen=True)
class DocumentoEstadoActual:
    orden: int
    fecha: str
    descripcion: str
    archivo: str
    pdf: str
    texto_path: str
    paginas: int
    caracteres: int
    hitos: list[str]
    texto: str
    bloque_hito: str


@dataclass(frozen=True)
class ResultadoCompactacionEstadoActual:
    indice_estado_path: Path
    policy_path: Path
    output_dir: Path
    resumen_compacto_path: Path
    referencias_path: Path
    documentos_importantes_path: Path
    input_llm_compacto_path: Path
    total_documentos: int
    total_texto_completo: int
    total_extracto_relevante: int
    total_resumen_operativo: int
    total_solo_metadata: int
    caracteres_input_compacto: int


def normalizar_texto(valor: str) -> str:
    txt = unicodedata.normalize("NFKD", valor or "")
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return txt.casefold()


def unicos(items: list[str]) -> list[str]:
    vistos: set[str] = set()
    salida: list[str] = []
    for item in items:
        limpio = " ".join(str(item).split())
        if not limpio:
            continue
        key = normalizar_texto(limpio)
        if key in vistos:
            continue
        vistos.add(key)
        salida.append(limpio)
    return salida


def cargar_policy(path: Path = POLICY_DEFAULT_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe política documental: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("La política documental debe ser un objeto YAML.")

    for key in ["id", "modos_inclusion", "reglas_por_descripcion", "salidas"]:
        if key not in data:
            raise ValueError(f"La política documental no incluye '{key}'.")

    return data


def parsear_metadata(bloque_doc: str) -> dict[str, str]:
    match = re.search(r"```text(?:\s+id=\"[^\"]+\")?\s+(.*?)```", bloque_doc, flags=re.S)
    if not match:
        return {}

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[normalizar_texto(key.strip())] = value.strip()
    return meta


def parsear_texto_extraido(bloque_doc: str) -> str:
    if "### Texto extraído" not in bloque_doc:
        return ""

    after = bloque_doc.split("### Texto extraído", 1)[1]
    match = re.search(r"```text(?:\s+id=\"[^\"]+\")?\s+(.*?)```", after, flags=re.S)
    if match:
        return match.group(1).strip()

    return after.strip()


def parsear_documentos_bloque(path: Path, *, bloque_hito: str) -> list[DocumentoEstadoActual]:
    contenido = path.read_text(encoding="utf-8")
    patron = re.compile(r"^## Documento orden (\d+) - ([0-9]{4}-[0-9]{2}-[0-9]{2})\s*$", re.M)
    marcas = list(patron.finditer(contenido))
    documentos: list[DocumentoEstadoActual] = []

    for i, marca in enumerate(marcas):
        inicio = marca.start()
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(contenido)
        bloque_doc = contenido[inicio:fin]
        meta = parsear_metadata(bloque_doc)
        texto = parsear_texto_extraido(bloque_doc)
        hitos = [h.strip() for h in meta.get("hitos", "").split(",") if h.strip()]

        documentos.append(
            DocumentoEstadoActual(
                orden=int(meta.get("orden") or marca.group(1)),
                fecha=meta.get("fecha") or marca.group(2),
                descripcion=meta.get("descripcion") or "",
                archivo=meta.get("archivo") or "",
                pdf=meta.get("pdf") or "",
                texto_path=meta.get("texto") or "",
                paginas=int(meta.get("paginas") or 0),
                caracteres=int(meta.get("caracteres") or len(texto)),
                hitos=hitos,
                texto=texto,
                bloque_hito=bloque_hito,
            )
        )

    return documentos


def cargar_documentos(indice_estado_path: Path) -> tuple[dict[str, Any], list[DocumentoEstadoActual]]:
    if not indice_estado_path.exists():
        raise FileNotFoundError(f"No existe índice de estado actual: {indice_estado_path}")

    indice = json.loads(indice_estado_path.read_text(encoding="utf-8"))
    documentos: list[DocumentoEstadoActual] = []

    for bloque in indice.get("bloques", []):
        archivo = bloque.get("archivo")
        hito = bloque.get("hito", "")
        if archivo:
            documentos.extend(parsear_documentos_bloque(Path(archivo), bloque_hito=hito))

    documentos.sort(key=lambda d: d.orden)
    return indice, documentos


def decidir_modo_inclusion(doc: DocumentoEstadoActual, policy: dict[str, Any]) -> str:
    desc = normalizar_texto(doc.descripcion)
    reglas = policy["reglas_por_descripcion"]

    for modo in ["texto_completo", "extracto_relevante", "resumen_operativo", "solo_metadata"]:
        for patron in reglas.get(modo, []):
            if normalizar_texto(patron) in desc:
                return modo

    if doc.paginas >= 3 or doc.caracteres > 2500:
        return "extracto_relevante"

    return "resumen_operativo"


def buscar_lineas_utiles(texto: str) -> list[str]:
    claves = [
        "solicito", "solicita", "intim", "dacion", "dación", "pago",
        "transferencia", "giro", "honorarios", "capital", "cbu",
        "cuit", "cuil", "dni", "iva", "responsable inscripto",
        "domicilio", "tel", "banco", "cuenta", "apercibimiento",
        "archivo", "apelacion", "apelación",
    ]

    lineas: list[str] = []
    for line in texto.splitlines():
        limpia = " ".join(line.split())
        if not limpia:
            continue
        norm = normalizar_texto(limpia)
        if any(clave in norm for clave in claves):
            lineas.append(limpia)

    return unicos(lineas)


def extraer_datos_utiles(texto: str) -> dict[str, list[str]]:
    bancos: list[str] = []
    for banco in ["BBVA", "Santander", "Banco Santander", "Banco Santander Río", "Banco Galicia", "Banco Nación", "Banco Provincia"]:
        if normalizar_texto(banco) in normalizar_texto(texto):
            bancos.append(banco)

    personas: list[str] = []
    for patron in [
        r"Mirta\s+Liliana\s+Tuchin",
        r"Lucas\s+Marino\s+ALONSO\s+CARLI",
        r"RENIERIS,\s+JONATHAN\s+JAVIER",
        r"VERISURE\s+ARGENTINA\s+MONITOREO\s+DE\s+ALARMAS\s+S\.?A\.?",
        r"(?:Dr\.?|Dra\.?)\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\s]+",
    ]:
        personas.extend(re.findall(patron, texto, flags=re.I))

    return {
        "personas": unicos(personas),
        "montos": unicos(re.findall(r"\$\s?[\d\.\,]+", texto)),
        "cbus": unicos(re.findall(r"\b\d{22}\b", texto)),
        "cuit_cuil_dni": unicos(re.findall(r"\b(?:CUIT|CUIL|DNI|C\.U\.I\.T\.|C\.U\.I\.L\.)\s*(?:N[°º]\s*)?[:\-]?\s*[\d\-\.]{7,15}\b", texto, flags=re.I)),
        "telefonos": unicos(re.findall(r"\b(?:\+?54\s*)?(?:\d{2,4}[-\s])?\d{3,4}[-\s]\d{3,4}\b", texto)),
        "emails": unicos(re.findall(r"[\w\.\-+]+@[\w\.\-]+\.\w+", texto)),
        "bancos": unicos(bancos),
        "lineas_utiles": buscar_lineas_utiles(texto)[:8],
    }


def generar_extracto(texto: str, max_chars: int = 900) -> str:
    lineas = buscar_lineas_utiles(texto)
    if lineas:
        return "\n".join(f"- {line}" for line in lineas)[:max_chars].strip()

    limpio = "\n".join(line.strip() for line in texto.splitlines() if line.strip())
    return limpio[:max_chars].strip()


def ficha_base(doc: DocumentoEstadoActual, modo: str) -> dict[str, Any]:
    return {
        "orden": doc.orden,
        "fecha": doc.fecha,
        "descripcion": doc.descripcion,
        "modo_inclusion": modo,
        "hitos": doc.hitos,
        "bloque_hito": doc.bloque_hito,
        "efecto_procesal": doc.descripcion.replace("Detalle:", "").strip() or "Sin descripción",
        "archivo_pdf": doc.pdf,
        "archivo_texto": doc.texto_path,
        "archivo": doc.archivo,
        "paginas": doc.paginas,
        "caracteres": doc.caracteres,
        "datos_utiles": extraer_datos_utiles(doc.texto),
    }


def md_items(titulo: str, items: list[str]) -> list[str]:
    if not items:
        return []
    return [f"- {titulo}:"] + [f"  - {item}" for item in items]


def render_ficha(ficha: dict[str, Any]) -> str:
    datos = ficha["datos_utiles"]
    lines = [
        f"## Orden {ficha['orden']} | {ficha['fecha']} | {ficha['modo_inclusion']}",
        "",
        f"- Descripción: {ficha['descripcion']}",
        f"- Efecto procesal: {ficha['efecto_procesal']}",
        f"- Hitos: {', '.join(ficha['hitos']) if ficha['hitos'] else 'sin hito'}",
        f"- PDF fuente: {ficha['archivo_pdf']}",
        f"- Texto fuente: {ficha['archivo_texto']}",
    ]

    lines.extend(md_items("Personas/intervinientes detectados", datos["personas"]))
    lines.extend(md_items("Montos detectados", datos["montos"]))
    lines.extend(md_items("CBU detectados", datos["cbus"]))
    lines.extend(md_items("CUIT/CUIL/DNI detectados", datos["cuit_cuil_dni"]))
    lines.extend(md_items("Teléfonos detectados", datos["telefonos"]))
    lines.extend(md_items("Emails detectados", datos["emails"]))
    lines.extend(md_items("Bancos detectados", datos["bancos"]))

    if datos["lineas_utiles"]:
        lines.append("- Líneas útiles:")
        lines.extend(f"  - {line}" for line in datos["lineas_utiles"])

    return "\n".join(lines).strip() + "\n"


def render_documento(doc: DocumentoEstadoActual, modo: str) -> tuple[str, dict[str, Any], str | None]:
    ficha = ficha_base(doc, modo)

    if modo == "texto_completo":
        importante = (
            f"## Documento importante | Orden {doc.orden} | {doc.fecha}\n\n"
            f"- Descripción: {doc.descripcion}\n"
            f"- PDF fuente: {doc.pdf}\n"
            f"- Texto fuente: {doc.texto_path}\n\n"
            "```text\n"
            f"{doc.texto.strip()}\n"
            "```\n"
        )
        return render_ficha(ficha), ficha, importante

    if modo == "extracto_relevante":
        ficha["extracto_relevante"] = generar_extracto(doc.texto)
        md = render_ficha(ficha)
        md += "\n### Extracto relevante\n\n"
        md += ficha["extracto_relevante"] + "\n"
        return md, ficha, None

    if modo == "solo_metadata":
        ficha["datos_utiles"]["lineas_utiles"] = []

    return render_ficha(ficha), ficha, None


def compactar_estado_actual(
    *,
    indice_estado_path: Path,
    output_dir: Path,
    policy_path: Path = POLICY_DEFAULT_PATH,
) -> ResultadoCompactacionEstadoActual:
    policy = cargar_policy(policy_path)
    indice_estado, documentos = cargar_documentos(indice_estado_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    salidas = policy["salidas"]
    resumen_path = output_dir / salidas["resumen_compacto_md"]
    referencias_path = output_dir / salidas["referencias_json"]
    importantes_path = output_dir / salidas["documentos_importantes_md"]
    input_path = output_dir / salidas["input_llm_compacto_md"]

    partes = [
        "# Estado actual compacto",
        "",
        "Resumen operativo de escritos simples, extractos de resoluciones relevantes y textos completos sólo de piezas sustanciales.",
        "",
        "## Fuente",
        "",
        f"- Índice estado actual: {indice_estado_path}",
        f"- Política documental: {policy_path}",
        f"- Prompt original: {indice_estado.get('prompt_path', '')}",
        f"- Material original: {indice_estado.get('material_path', '')}",
        "",
        "## Documentos compactados",
        "",
    ]

    referencias: list[dict[str, Any]] = []
    importantes = [
        "# Documentos importantes con texto completo",
        "",
        "Sólo se incluyen documentos clasificados como `texto_completo`.",
        "",
    ]

    conteo = {m: 0 for m in ["texto_completo", "extracto_relevante", "resumen_operativo", "solo_metadata"]}

    for doc in documentos:
        modo = decidir_modo_inclusion(doc, policy)
        conteo[modo] += 1

        md, ficha, importante = render_documento(doc, modo)
        partes.append(md)
        partes.append("---\n")
        referencias.append(ficha)

        if importante:
            importantes.append(importante)
            importantes.append("---\n")

    resumen = "\n".join(partes).strip() + "\n"
    importantes_md = "\n".join(importantes).strip() + "\n"

    prompt_original = ""
    prompt_path = indice_estado.get("prompt_path")
    if prompt_path and Path(prompt_path).exists():
        prompt_original = Path(prompt_path).read_text(encoding="utf-8").strip()

    input_compacto = (
        "# Input compacto para LLM - Estado actual del expediente\n\n"
        "## Prompt de análisis\n\n"
        + prompt_original
        + "\n\n---\n\n"
        "## Material compacto\n\n"
        + resumen
        + "\n\n---\n\n"
        "## Documentos importantes completos\n\n"
        + importantes_md
        + "\n"
    )

    resumen_path.write_text(resumen, encoding="utf-8")
    referencias_path.write_text(json.dumps(referencias, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    importantes_path.write_text(importantes_md, encoding="utf-8")
    input_path.write_text(input_compacto, encoding="utf-8")

    return ResultadoCompactacionEstadoActual(
        indice_estado_path=indice_estado_path,
        policy_path=policy_path,
        output_dir=output_dir,
        resumen_compacto_path=resumen_path,
        referencias_path=referencias_path,
        documentos_importantes_path=importantes_path,
        input_llm_compacto_path=input_path,
        total_documentos=len(documentos),
        total_texto_completo=conteo["texto_completo"],
        total_extracto_relevante=conteo["extracto_relevante"],
        total_resumen_operativo=conteo["resumen_operativo"],
        total_solo_metadata=conteo["solo_metadata"],
        caracteres_input_compacto=len(input_compacto),
    )
