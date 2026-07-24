# Contrato de Google Apps Script

El código del Apps Script no está incluido en este repositorio. La
aplicación espera un endpoint HTTPS que reciba JSON y responda JSON.

## Requisitos de seguridad

1. Rechazar peticiones cuyo `token` no coincida mediante una comparación
   segura.
2. Admitir exclusivamente las acciones documentadas.
3. Validar tipos, longitudes y campos obligatorios antes de escribir.
4. Escapar valores que comiencen por `=`, `+`, `-` o `@` para evitar
   inyección de fórmulas en Sheets.
5. No devolver el token, trazas internas ni contenido sensible.
6. Registrar fecha, acción y resultado sin guardar el token.
7. Ejecutar con una identidad que solo pueda modificar las hojas necesarias.

## Acción `incidencia`

Campos: `usuario_nombre`, `tipo`, `categoria`, `nombre`, `entidad_id`,
`municipio`, `asunto` y `descripcion`.

Las propuestas nuevas y las correcciones deben entrar en una hoja de
moderación; no deberían modificar directamente los datos publicados.

## Acción `nueva_resena_restaurante`

Campos: `restaurante_id`, `restaurante`, `fecha`, `guia`, `num_personas`,
`precio_por_persona`, `rating` y `comentario`.

Durante la migración, `restaurante_id` puede estar vacío. Después de
completarla, el Apps Script debería exigirlo.

## Respuesta

Éxito:

```json
{"ok": true}
```

Error controlado:

```json
{"ok": false, "error": "mensaje no sensible"}
```
