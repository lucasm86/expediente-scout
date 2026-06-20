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
