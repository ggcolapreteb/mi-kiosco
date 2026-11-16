# Mi Kiosco — cómo publicarlo en GitHub

Un proceso automático de GitHub lee todos los feeds cada 20 minutos y guarda las
noticias en `data.json`. La página (`index.html`) solo muestra ese archivo.

## Pasos (una sola vez)

1. **Cuenta.** Crea una cuenta gratis en https://github.com (si no tienes).
2. **Repositorio.** Botón "+" arriba a la derecha → "New repository".
   Nombre: `mi-kiosco`. Visibilidad: **Public**. Crear.
3. **Subir archivos.** En el repositorio: "uploading an existing file" (o "Add file" →
   "Upload files"). Arrastra TODO el contenido de esta carpeta, incluida la carpeta
   `.github`. Abajo, "Commit changes".
4. **Revisar el flujo.** En la lista de archivos tiene que aparecer la carpeta
   `.github`. Si no aparece (algunos computadores la ocultan): "Add file" →
   "Create new file", escribe como nombre `.github/workflows/actualizar.yml`,
   pega el contenido de ese archivo y "Commit changes".
5. **Primera carga.** Pestaña "Actions" → "Actualizar noticias" → "Run workflow".
   Espera a que quede con un visto verde (1 minuto aprox.).
6. **Publicar.** "Settings" → "Pages" → en "Branch" elige `main` y carpeta `/ (root)` → "Save".
   En un par de minutos tu página queda en `https://TU-USUARIO.github.io/mi-kiosco/`.

## Para cambiar cosas después

- **Medios:** edita `fuentes.json` (cada línea es una fuente; `urls` se prueban en orden).
- **Subcategorías y palabras clave:** bloque CONFIGURACIÓN al inicio del script de `index.html`.
- **Frecuencia:** el `sleep 1200` (segundos) de `.github/workflows/actualizar.yml`.
- **Qué falló:** en la página, vista Lista → "Estado de las fuentes"; o en GitHub,
  pestaña "Actions" → la última ejecución → paso "Leer los feeds".
