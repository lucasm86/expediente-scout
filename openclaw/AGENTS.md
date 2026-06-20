# OpenClaw — AGENTS.md

## Objetivo

OpenClaw actúa como interfaz, router y orquestador. No es el sistema de registro del expediente. Ese rol pertenece al CLI `scout`.

## Regla matriz

Todo comando recibido por WhatsApp debe traducirse a comandos `scout` determinísticos. No se permite navegación manual del portal, improvisación de rutas ni análisis libre sin referencias internas.

## Allowlist

Solo se acepta el número dedicado configurado en `openclaw/examples/allowlist.example.txt` o en la configuración local real, no versionada.

Si el remitente no está autorizado, OpenClaw debe rechazar el comando sin ejecutar shell.

## Comandos WhatsApp soportados

### 1. Listar expedientes locales

```text
Expediente: listar
```

Ejecuta:

```bash
scout listar --root .
```

No toca PJN.

### 2. Estado local de un expediente

```text
Expediente: estado pjn 12345/2024
```

Ejecuta:

```bash
scout estado --root . --jurisdiccion pjn --numero 12345 --anio 2024
```

No toca PJN.

### 3. Capturar expediente

```text
Expediente: capturar pjn 12345/2024
```

Ejecuta:

```bash
scout capturar --script-path /opt/expediente-scout/scripts/pjn.py --env-path .env --root . --jurisdiccion pjn --numero 12345 --anio 2024
```

Toca PJN solo mediante el script externo de Lucas.

### 4. Buscar novedades

```text
Expediente: novedades pjn 12345/2024
```

Ejecuta captura por script externo y luego estado local:

```bash
scout capturar --script-path /opt/expediente-scout/scripts/pjn.py --env-path .env --root . --jurisdiccion pjn --numero 12345 --anio 2024
scout estado --root . --jurisdiccion pjn --numero 12345 --anio 2024
```

### 5. Informe completo

```text
Expediente: informe pjn 12345/2024
```

Secuencia esperada:

```bash
scout capturar --script-path /opt/expediente-scout/scripts/pjn.py --env-path .env --root . --jurisdiccion pjn --numero 12345 --anio 2024
scout normalizar --root . --jurisdiccion pjn --numero 12345 --anio 2024
scout curar --root . --jurisdiccion pjn --numero 12345 --anio 2024
# OpenClaw envía el material curado a GPT con el prompt openclaw/prompts/analisis_gpt.md
# GPT debe guardar JSON en data/expedientes/pjn/12345-2024/reports/analisis-gpt.json
scout validar-analisis --root . --jurisdiccion pjn --numero 12345 --anio 2024 --analisis-json data/expedientes/pjn/12345-2024/reports/analisis-gpt.json
scout reportar --root . --jurisdiccion pjn --numero 12345 --anio 2024
```

## Prohibiciones

- No ejecutar comandos fuera de los permitidos en `TOOLS.md`.
- No leer ni devolver `.env`.
- No mandar el expediente crudo entero a GPT.
- No aceptar conclusiones GPT sin `scout validar-analisis`.
- No publicar ni enviar a terceros documentación del expediente.
