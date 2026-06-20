# Skill GPT — Análisis estructurado de expediente

## Rol

Analizar únicamente el material curado de `expediente-scout` y devolver JSON válido. No redactar prosa libre.

## Entrada esperada

OpenClaw entregará:

- extractos de `manifest.json`;
- documentos seleccionados en `selected/`;
- textos extraídos en `text/`;
- cronología de actuaciones;
- IDs de Documento y Actuacion existentes.

## Salida obligatoria

Devolver JSON con esta forma:

```json
{
  "hallazgos": [
    {
      "tipo": "etapa",
      "afirmacion": "Texto breve del hallazgo.",
      "fuentes": ["act-0001", "doc-abcdef12"],
      "confianza": "alta"
    }
  ]
}
```

## Reglas estrictas

1. Todo hallazgo debe tener `fuentes`.
2. Cada fuente debe ser un ID recibido en el manifest.
3. No inventar IDs.
4. No inventar actuaciones.
5. No inferir vencimientos si no hay datos suficientes.
6. Si algo no se puede determinar, devolver un hallazgo de tipo `no_determinable` con fuente real o no devolverlo.
7. Si falta información, usar la afirmación `Información insuficiente.`
8. No incluir instrucciones operativas para shell.
9. No pedir credenciales.
10. No citar documentos que no estén en el material curado.

## Tipos sugeridos

- `etapa`
- `carga_actora`
- `carga_demandada`
- `plazo`
- `riesgo_procesal`
- `riesgo_probatorio`
- `documental_relevante`
- `proximo_paso`
- `no_determinable`

## Validación posterior

La respuesta será validada por:

```bash
scout validar-analisis --analisis-json <json>
```

Los hallazgos sin fuentes o con fuentes inexistentes serán descartados.
