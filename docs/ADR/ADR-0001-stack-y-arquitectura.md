# ADR-0001 — Stack y arquitectura inicial

## Estado

Aceptado para Paso 1.

## Contexto

El proyecto necesita una base determinística antes de conectarse con OpenClaw, GPT o PJN real. La prioridad es trazabilidad, reproducibilidad y bajo acoplamiento.

## Decisiones

1. Usar Python 3.11+ por disponibilidad, ecosistema documental y simplicidad operativa en Raspberry Pi.
2. Usar Pydantic v2 para modelos de dominio y validación fuerte del `manifest.json`.
3. Declarar Typer como dependencia, aunque la CLI se implementará recién en el Paso 2.
4. Usar PyMuPDF para generar PDFs mock reales y contar páginas.
5. Usar un `MockCaptura` determinístico como frontera inicial del sistema.
6. No integrar OpenClaw, GPT, PJN real, WhatsApp ni credenciales en este paso.

## Consecuencias

- El núcleo puede probarse sin red ni servicios externos.
- La captura real queda desacoplada del dominio.
- El manifest queda como contrato estable para pasos posteriores.
