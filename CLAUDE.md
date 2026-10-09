# CLAUDE.md

Contexto persistente del proyecto. Se carga al inicio de cada sesión: mantenerlo corto.

## Usuario
- Fabián Campo. Responder siempre en **español**, directo y sin relleno.
- Perfil: pregrado en Matemáticas, especialización en Gerencia Financiera, dos maestrías en finanzas. Se puede asumir nivel técnico en finanzas y matemáticas.
- Explicar con pasos concretos. Si hay varias opciones, dar una recomendación, no un listado largo.

## Proyecto: votacion-practica
- App de una sola página: `index.html` (HTML + CSS + JS en un único archivo, ~27 KB). No hay build ni dependencias de npm.
- Sirve para que estudiantes voten temáticas de su práctica profesional. Hay dos vistas: `#page-student` (votación) y `#page-teacher` (acceso docente con contraseña, resultados con gráficos).
- Gráficos con Chart.js 4.4.0 por CDN (jsdelivr).
- Los datos se guardan en `localStorage` (`getVotes`/`saveVotes`, `getStudents`/`saveStudents`). Por eso los votos viven solo en el navegador de cada dispositivo; no hay backend.
- Rama de trabajo: `claude/determined-cray-o7krsu`. No abrir PR a menos que Fabián lo pida.

## Cómo trabajar aquí
- Editar `index.html` con cambios puntuales (Edit), no reescribir el archivo completo.
- Mantener el estilo existente: variables CSS en `:root`, textos de interfaz en español.
- No escribir contraseñas ni credenciales en commits, mensajes ni este archivo.
- Para probar: abrir `index.html` en el navegador (o un servidor estático local).

## Ahorro de tokens (importante)
- Fabián tuvo consumo muy alto por conversaciones largas en Opus con esfuerzo alto. Prioridad: gastar poco sin perder contexto.
- Modelo por defecto: **Sonnet**. Subir a Opus solo si la tarea lo exige (razonamiento difícil o alto riesgo de error).
- No releer ni pegar archivos completos si basta con buscar la parte relevante (Grep/Read con rango).
- Respuestas cortas por defecto; extenderse solo si se pide.
- Al cerrar un bloque de trabajo largo, escribir un resumen breve del estado (qué se hizo, qué falta) para poder continuar en un chat nuevo sin arrastrar el historial.
- Rutinas programadas (Routines) gastan tokens solas cada día: antes de crear o reactivar una, avisar a Fabián del costo.

## Estado actual
- Versión inicial publicada (commit `8bcf8df`). Sin tareas pendientes registradas.
- Actualizar esta sección cuando cambie el estado del proyecto.
