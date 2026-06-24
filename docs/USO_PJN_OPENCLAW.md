# Uso PJN con Scout y OpenClaw

## Comando

    scout-pjn FUERO NUMERO/AÑO

Ejemplos:

    scout-pjn CNT 017515/2024
    scout-pjn CCF 002899/2026

## Resultado

El archivo final queda dentro del Vault:

    /home/adso/.openclaw/workspace/Lucas's Vault/Expedientes/PJN/<SLUG>/<SLUG>_EXPEDIENTE.md

Ejemplo:

    /home/adso/.openclaw/workspace/Lucas's Vault/Expedientes/PJN/CCF-002899-2026/CCF-002899-2026_EXPEDIENTE.md

## Regla operativa

OpenClaw debe ejecutar el comando y devolver la ruta del Markdown final.

No debe cargar automáticamente el expediente completo en contexto.

## Forzar recaptura

    scout-pjn CCF 002899/2026 --force
