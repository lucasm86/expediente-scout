# Roadmap MEV

## Objetivo

Crear un flujo equivalente al de PJN para expedientes de la MEV Provincia de Buenos Aires.

## Comando deseado

    scout-mev <datos-del-expediente>

## Contrato de salida

La MEV debe terminar generando:

- PDFs originales.
- índice normalizado.
- paquete de análisis.
- Markdown final único en el Vault.
- log técnico.
- resultado JSON técnico.

## Arquitectura

El capturador MEV debe estar separado del capturador PJN.

La salida normalizada debe alimentar el mismo pipeline general.
