# Uso MEV con Scout

## Comando previsto

    scout-mev JURISDICCION ORGANISMO EXPEDIENTE

Ejemplos:

    scout-mev LZ CC8 85092
    scout-mev SI CC6 23308
    scout-mev SM T2 12345

## Códigos de jurisdicción

    LZ = Lomas de Zamora
    SI = San Isidro
    SM = San Martín

El listado se configura en:

    config/mev_aliases.json

## Códigos de organismo

    CC8 = Juzgado Civil y Comercial Nº 8
    T2 = Tribunal de Trabajo Nº 2
    F3 = Juzgado de Familia Nº 3

## Salida esperada

El Markdown final debe quedar en:

    /home/adso/.openclaw/workspace/Lucas's Vault/Expedientes/MEV/<SLUG>/<SLUG>_EXPEDIENTE.md

Ejemplo:

    /home/adso/.openclaw/workspace/Lucas's Vault/Expedientes/MEV/LZ-CC8-85092/LZ-CC8-85092_EXPEDIENTE.md

## Credenciales

La navegación MEV debe leer credenciales desde:

    /home/adso/.openclaw/workspace/.openclaw/secrets/mev.env

Variables esperadas:

    MEV_USUARIO
    MEV_PASSWORD

Nunca hardcodear credenciales en scripts, skills, documentación ni commits.
