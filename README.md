# expediente-scout

Herramienta local para capturar, procesar y estudiar expedientes judiciales.

## Estado actual

MVP funcional para PJN.

Comando principal:

    scout-pjn FUERO NUMERO/AÑO

Ejemplos:

    scout-pjn CNT 017515/2024
    scout-pjn CCF 002899/2026

## Salida principal

El sistema genera un único Markdown operativo en el Vault de OpenClaw:

    /home/adso/.openclaw/workspace/Lucas's Vault/Expedientes/PJN/<FUERO-NUMERO-AÑO>/<FUERO-NUMERO-AÑO>_EXPEDIENTE.md

## Filosofía

- Los PDFs originales quedan como fuente.
- El formato operativo principal es Markdown.
- OpenClaw no debe cargar automáticamente todo el expediente.
- El usuario decide dónde procesar el Markdown final.

## Instalación básica

    git clone git@github.com:lucasm86/expediente-scout.git
    cd expediente-scout
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .

## Instalar wrapper scout-pjn

    mkdir -p ~/.local/bin
    cp bin/scout-pjn ~/.local/bin/scout-pjn
    chmod +x ~/.local/bin/scout-pjn

Agregar al PATH si hace falta:

    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc

## Credenciales

Crear localmente:

    .env.pjn.capture

Ese archivo no debe subirse a GitHub.

Usar como modelo:

    .env.pjn.capture.example

## Roadmap

- Integrar MEV Provincia de Buenos Aires.
- Crear comando equivalente scout-mev.
- Mantener el mismo contrato de salida: PDFs originales + índice normalizado + Markdown final único.
