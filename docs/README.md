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
