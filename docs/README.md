# expediente-scout

`expediente-scout` es el núcleo determinístico y trazable para ordenar documentos de expedientes judiciales previamente capturados.

## Alcance del Paso 1

Este paso implementa solamente:

- modelos de dominio;
- estructura de carpetas;
- manifest JSON;
- fuente mock de captura;
- ingesta básica;
- tests.

Queda fuera de alcance: CLI funcional, normalización, clasificación, análisis con GPT, PJN real, OpenClaw, WhatsApp y credenciales.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Correr tests

```bash
pytest
```


## Paso 2

Se agrega una CLI mínima con Typer:

```bash
scout ingerir --root . --jurisdiccion pjn --numero 12345 --anio 2024
scout listar --root .
scout estado --root . --jurisdiccion pjn --numero 12345 --anio 2024
```

La reingesta es idempotente: si se ingiere dos veces la misma captura mock, no se duplican actuaciones ni documentos.


## Paso 3

Se agrega normalización documental local:

```bash
scout ingerir --root . --jurisdiccion pjn --numero 12345 --anio 2024
scout normalizar --root . --jurisdiccion pjn --numero 12345 --anio 2024
```

La normalización cuenta páginas con PyMuPDF, extrae texto a `text/<doc_id>.txt`, actualiza `manifest.json` y marca duplicados exactos por `sha256` con `categoria=duplicado`, `relevancia=duplicado` y `duplicado_de`.

## Paso 4 — Novedades

El mock ahora expone dos estados:

- `base`: cinco actuaciones iniciales.
- `ampliado`: las cinco iniciales más dos actuaciones nuevas.

Comandos útiles:

```bash
scout novedades --root . --jurisdiccion pjn --numero 12345 --anio 2024 --mock-estado ampliado
scout ingerir --root . --jurisdiccion pjn --numero 12345 --anio 2024 --mock-estado ampliado
```

La reingesta agrega solo actuaciones/documentos nuevos y no duplica lo ya existente.


## Paso 5 — Curaduría por reglas

El Paso 5 agrega clasificación conservadora por reglas. El comando:

```bash
scout curar --root . --jurisdiccion pjn --numero 12345 --anio 2024
```

Actualiza `manifest.json` con `categoria`, `relevancia`, `motivo_relevancia` y `metodo_clasificacion="regla"`. Además copia los documentos relevantes a `selected/` y deja lo ambiguo como `requiere_revision`.

Alcance deliberado: no hay GPT, no hay análisis jurídico, no hay informe final y no hay PJN real.

## Paso 5 — Curaduría por reglas

El Paso 5 agrega clasificación conservadora por reglas. El comando:

```bash
scout curar --root . --jurisdiccion pjn --numero 12345 --anio 2024
```

Actualiza `manifest.json` con `categoria`, `relevancia`, `motivo_relevancia` y `metodo_clasificacion="regla"`. Además copia los documentos relevantes a `selected/` y deja lo ambiguo como `requiere_revision`.

Alcance deliberado: no hay GPT, no hay análisis jurídico, no hay informe final y no hay PJN real.

## Paso 6 — Contrato de análisis y validador de referencias

El Paso 6 agrega un contrato JSON para la futura skill de análisis y un validador anti-alucinación. Todavía no llama a GPT: valida un archivo JSON simulado contra los IDs existentes en `manifest.json`.

Ejemplo:

```bash
scout validar-analisis \
  --root . \
  --jurisdiccion pjn \
  --numero 12345 \
  --anio 2024 \
  --analisis-json analisis-simulado.json
```

El resultado se guarda en `reports/analisis-validado.json`. Todo hallazgo sin fuentes o con fuentes inexistentes se descarta automáticamente.

## Paso 6 — Contrato de análisis y validador de referencias

El Paso 6 agrega un contrato JSON para la futura skill de análisis y un validador anti-alucinación. Todavía no llama a GPT: valida un archivo JSON simulado contra los IDs existentes en `manifest.json`.

Ejemplo:

```bash
scout validar-analisis \
  --root . \
  --jurisdiccion pjn \
  --numero 12345 \
  --anio 2024 \
  --analisis-json analisis-simulado.json
```

El resultado se guarda en `reports/analisis-validado.json`. Todo hallazgo sin fuentes o con fuentes inexistentes se descarta automáticamente.

## Paso 7 — Informe Markdown

Agrega `scout reportar`, que genera `reports/informe.md` con 14 secciones a partir de `manifest.json` y `reports/analisis-validado.json`.

Alcance:
- No llama a GPT.
- No integra PJN real.
- No exporta PDF todavía.
- Solo usa hallazgos previamente validados contra IDs internos existentes.

Comando:

```bash
scout reportar --root . --jurisdiccion pjn --numero 12345 --anio 2024
```
