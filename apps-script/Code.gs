const EMAIL_DESTINO = "daniel@apitcantabria.com";
const SHEET_ID = "1J1T4vS736sotTVP9KgdSje0OxlBvFU_7alO4Mwap5YY";
const ACCIONES_PERMITIDAS = ["incidencia", "nueva_resena_restaurante"];

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return respuestaJSON(false, "Solicitud vacía");
    }

    const data = JSON.parse(e.postData.contents);
    const token = PropertiesService.getScriptProperties()
      .getProperty("APPS_SCRIPT_TOKEN");

    if (!token || data.token !== token) {
      return respuestaJSON(false, "Token inválido");
    }

    if (!ACCIONES_PERMITIDAS.includes(data.accion)) {
      return respuestaJSON(false, "Acción no permitida");
    }

    const ss = SpreadsheetApp.openById(SHEET_ID);
    const lock = LockService.getScriptLock();
    lock.waitLock(10000);

    try {
      if (data.accion === "incidencia") {
        return guardarIncidencia(ss, data);
      }
      return guardarResenaRestaurante(ss, data);
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    console.error(err && err.stack ? err.stack : err);
    return respuestaJSON(false, "No se pudo registrar la información");
  }
}

function guardarIncidencia(ss, data) {
  const sheet = obtenerHoja(ss, "incidencias");
  const fecha = new Date();
  const registro = {
    usuario: campo(data.usuario_nombre, "usuario_nombre", 120, true),
    email: campo(data.usuario_email, "usuario_email", 200, false),
    tipo: campo(data.tipo, "tipo", 40, true),
    categoria: campo(data.categoria, "categoria", 40, true),
    nombre: campo(data.nombre, "nombre", 250, true),
    municipio: campo(data.municipio, "municipio", 150, false),
    asunto: campo(data.asunto, "asunto", 300, true),
    descripcion: campo(data.descripcion, "descripcion", 4000, true),
    entidadId: campo(data.entidad_id, "entidad_id", 100, false),
  };

  sheet.appendRow([
    fecha,
    registro.usuario,
    registro.email,
    registro.tipo,
    registro.categoria,
    registro.nombre,
    registro.municipio,
    registro.asunto,
    registro.descripcion,
    "pendiente",
    registro.entidadId,
  ]);

  enviarAvisoSeguro({
    subject: "Nueva incidencia registrada en el CMS Cantabria",
    body:
      "Se ha registrado una nueva incidencia en el CMS Cantabria.\n\n" +
      "Fecha: " + fecha + "\n" +
      "Guía: " + registro.usuario + "\n" +
      "Tipo: " + registro.tipo + "\n" +
      "Categoría: " + registro.categoria + "\n" +
      "Nombre: " + registro.nombre + "\n" +
      "ID: " + registro.entidadId + "\n" +
      "Municipio: " + registro.municipio + "\n" +
      "Asunto: " + registro.asunto + "\n\n" +
      "Descripción:\n" + registro.descripcion,
  });

  return respuestaJSON(true, "");
}

function guardarResenaRestaurante(ss, data) {
  const sheet = obtenerHoja(ss, "experiencias_restaurantes");
  const registro = {
    restauranteId: campo(data.restaurante_id, "restaurante_id", 100, false),
    restaurante: campo(data.restaurante, "restaurante", 250, true),
    fecha: campo(data.fecha, "fecha", 20, true),
    guia: campo(data.guia, "guia", 120, true),
    personas: numeroEntero(data.num_personas, "num_personas", 1, 500),
    precio: campo(data.precio_por_persona, "precio_por_persona", 50, false),
    rating: numeroEntero(data.rating, "rating", 1, 5),
    comentario: campo(data.comentario, "comentario", 2000, true),
  };

  sheet.appendRow([
    registro.restaurante,
    registro.fecha,
    registro.guia,
    registro.personas,
    registro.precio,
    registro.rating,
    registro.comentario,
    registro.restauranteId,
  ]);

  enviarAvisoSeguro({
    subject: "Nueva reseña de restaurante en el CMS Cantabria",
    body:
      "Se ha registrado una nueva reseña de restaurante.\n\n" +
      "Restaurante: " + registro.restaurante + "\n" +
      "ID: " + registro.restauranteId + "\n" +
      "Fecha visita: " + registro.fecha + "\n" +
      "Guía: " + registro.guia + "\n" +
      "Personas: " + registro.personas + "\n" +
      "Precio por persona: " + registro.precio + "\n" +
      "Valoración: " + registro.rating + "/5\n\n" +
      "Comentario:\n" + registro.comentario,
  });

  return respuestaJSON(true, "");
}

function obtenerHoja(ss, nombre) {
  const sheet = ss.getSheetByName(nombre);
  if (!sheet) {
    throw new Error("No existe la hoja requerida: " + nombre);
  }
  return sheet;
}

function campo(value, nombre, maxLength, required) {
  let text = value == null ? "" : String(value).trim();
  if (required && !text) {
    throw new Error("Falta el campo obligatorio: " + nombre);
  }
  if (text.length > maxLength) {
    throw new Error("El campo es demasiado largo: " + nombre);
  }
  if (/^[=+\-@]/.test(text)) {
    text = "'" + text;
  }
  return text;
}

function numeroEntero(value, nombre, min, max) {
  const number = Number(value);
  if (!Number.isInteger(number) || number < min || number > max) {
    throw new Error("Valor no válido: " + nombre);
  }
  return number;
}

function enviarAvisoSeguro(message) {
  try {
    MailApp.sendEmail({
      to: EMAIL_DESTINO,
      subject: message.subject,
      body: message.body,
    });
  } catch (err) {
    console.error(
      "Registro guardado, pero no se pudo enviar el correo: " + err
    );
  }
}

function respuestaJSON(ok, error) {
  return ContentService
    .createTextOutput(JSON.stringify({ ok: ok, error: error }))
    .setMimeType(ContentService.MimeType.JSON);
}
