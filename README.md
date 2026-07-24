# GuíaHub — APIT Cantabria

Aplicación Streamlit que consulta recursos turísticos, restaurantes y
experiencias almacenados en Google Sheets.

## Puesta en marcha

1. Cree un entorno virtual.
2. Instale las dependencias con `pip install -r requirements.txt`.
3. Copie `.streamlit/secrets.toml.example` como
   `.streamlit/secrets.toml` y complete los valores.
4. Ejecute `streamlit run app.py`.

## Arquitectura

- `app.py`: composición de la interfaz Streamlit y formularios.
- `cms/config.py`: libro, pestañas y esquemas de datos.
- `cms/data.py`: descarga CSV, validación, normalización y carga aislada.
- `cms/resources.py`: relaciones, reglas de fecha y valoraciones.
- `cms/submissions.py`: contrato de escritura con Google Apps Script.
- `tests/`: pruebas unitarias de las reglas independientes de la interfaz.

Las lecturas usan la exportación CSV de Google Sheets. Las escrituras se
envían a un Google Apps Script externo mediante HTTPS y un token guardado
en secretos de Streamlit.

## Identificadores y migración

Se recomienda añadir estas columnas:

| Hoja | Columna |
|---|---|
| `recursos` | `recurso_id` |
| `contenidos-recursos` | `recurso_id` |
| `restaurantes` | `restaurante_id` |
| `experiencias_restaurantes` | `restaurante_id` |

Los identificadores deben ser únicos, permanentes y no contener datos
personales; por ejemplo, `rec_0001` y `rest_0001`.

La aplicación prefiere los IDs. Durante la migración, si una relación no
tiene ID, usa el nombre normalizado como compatibilidad temporal. Cuando
todas las filas tengan ID, los nombres podrán cambiar sin romper relaciones.

## Acceso y seguridad

- Las URL CSV no usan autenticación de Google. Revise que el nivel de
  publicación/compartición del libro sea compatible con la sensibilidad de
  sus datos.
- El token de Apps Script no debe guardarse en Git ni enviarse al navegador.
- El Apps Script debe comparar el token, validar cada campo, limitar las
  acciones admitidas y ejecutar con una cuenta con permisos mínimos.
- El código del Apps Script debería versionarse en este repositorio o en otro
  repositorio enlazado.

Consulte [docs/apps-script-contract.md](docs/apps-script-contract.md) para el
contrato esperado.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```
