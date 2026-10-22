# BSC TechPeru SAC

Aplicación académica de Balanced Scorecard con frontend HTML/CSS/JavaScript, backend Python y base de datos SQLite. Incluye el Excel mejorado que sirve de referencia para los 12 objetivos y 36 indicadores.

## Iniciar en Windows

1. Instala Python 3.10 o posterior si aún no lo tienes. En su instalador, activa **Add Python to PATH**.
2. Descomprime el ZIP completo en una carpeta.
3. Haz doble clic en **iniciar.bat**. Mantén esa ventana abierta.
4. La primera vez, la ventana muestra una contraseña inicial aleatoria. Cópiala; no se guarda como texto en el proyecto.
5. Abre **http://127.0.0.1:8000** en tu navegador.
6. Ingresa como **admin@techperu.local** usando la contraseña mostrada. Puedes cambiarla en **Cómo usar el BSC**.

No abras `frontend/index.html` con doble clic: esta versión requiere el backend. Si el puerto está ocupado, ejecuta `py -3 backend/server.py --port 8001` y abre http://127.0.0.1:8001.

En Linux o macOS: `python3 backend/server.py`. No se requieren paquetes de pip, npm ni conexión a Internet para ejecutar la aplicación.

## Usuarios iniciales

Los tres usuarios reciben la contraseña generada en la primera ejecución. Puedes establecerla de antemano con la variable de entorno `BSC_INITIAL_PASSWORD`; no la subas a GitHub.

| Correo | Rol | Facultades |
| --- | --- | --- |
| admin@techperu.local | Administrador | Gestión completa, usuarios, importación Excel e historial. |
| gerente@techperu.local | Gerente | Objetivos, indicadores, mediciones e iniciativas. |
| responsable@techperu.local | Responsable de indicadores | Consulta del BSC y registro/edición de mediciones de Operaciones. |

El administrador puede crear otros usuarios con contraseñas propias. Cada usuario puede cambiar su contraseña en **Cómo usar el BSC**. Los permisos se comprueban en el servidor, no solo ocultando botones.

## Cómo usar el Excel

Abre `docs/BSC_TechPeru_Mejorado_2025.xlsx` y entra en **BSC Completo**.

- **F: Meta** y **G: Real** son las entradas numéricas. Los datos iniciales son ejemplos académicos.
- **H: Cumplimiento** e **I: Estado** contienen fórmulas.
- **J: Código KPI** permite relacionar cada fila con el sistema. Conserva estos códigos.
- **K: Sentido** permite elegir Mayor o Menor es mejor.
- Escribe `18` si el resultado es 18%, y `0.25` si son 0,25 millones de soles. S/ MM significa millones de soles.
- Las hojas por perspectiva, el resumen y el gráfico se actualizan mediante fórmulas. Evita editar sus celdas vinculadas.

Para aplicar cambios al sistema: guarda el archivo, ingresa como administrador y abre **Reportes y Excel → Importar Excel**. La importación actualiza las metas, el sentido y el resultado del período **2025-12** por código. No importa nombres ni reorganiza objetivos; esos cambios se gestionan en la aplicación. Una celda Real vacía elimina exclusivamente la medición de cierre de ese indicador en 2025-12. Otros períodos permanecen intactos.

La sincronización es manual: cambiar datos en el sistema no modifica el archivo Excel. El botón **Exportar vista CSV** descarga los indicadores que coinciden con el año y filtros visibles. El CSV es un reporte para Excel, no reemplaza la plantilla `.xlsx` de importación.

## Reglas de cálculo comunes

| Regla | Cálculo |
| --- | --- |
| Mayor es mejor | Resultado / Meta × 100, con puntuación limitada entre 0% y 150%. Meta mayor que cero. |
| Menor es mejor | 100% si Resultado ≤ Meta. De otro modo, Meta / Resultado × 100. Se admite meta cero. |
| Cumplido | Cumplimiento ≥ 100%. |
| En riesgo | Cumplimiento ≥ 80% y < 100%. |
| Crítico | Cumplimiento < 80%. |
| Sin datos | No existe una medición; se excluye del promedio, no equivale a un cero. |

El resumen promedia los KPI con datos dentro de cada objetivo, luego los objetivos con datos dentro de cada perspectiva y finalmente las perspectivas con datos. Todos tienen igual peso dentro de su nivel. Se informa la cantidad de indicadores con resultados para evitar interpretar un resumen parcial como cobertura completa.

Los 36 valores originales producen **84,2% global**, **0 cumplidos, 27 en riesgo y 9 críticos** con las reglas corregidas. El cambio respecto al semáforo original es intencional: antes se marcaban como logrados resultados desde el 90%.

## Datos y períodos

Los valores originales se cargan como un cierre académico anual en diciembre de 2025. El archivo fuente no aporta detalle mensual: no se han generado meses históricos artificiales. Seleccionar 2026 muestra Sin datos hasta registrar mediciones de ese año.

Las cuatro iniciativas iniciales son propuestas de mejora, con presupuesto y avance cero, pendientes de registrar. No representan proyectos reales ejecutados. La fecha de registro puede ser posterior al período medido. Existe una única medición por indicador y mes; para corregirla, usa Editar.

## Estructura

```text
frontend/         Pantallas, estilos y navegación
backend/server.py API REST, autenticación y validaciones
data/seed.json    Datos iniciales académicos
data/bsc.sqlite3  Base local generada al iniciar (excluida de Git)
docs/             Excel mejorado, guía y formato de entrega
tests/            Pruebas de integración HTTP y SQLite
```

La base de datos se crea al iniciar. Cerrar y volver a abrir el programa conserva los datos. Para respaldarlos, detén el servidor y copia `data/bsc.sqlite3`. No borres esa base para actualizar el programa: conserva tu historial. El backend se enlaza por defecto a tu computadora local. Un despliegue público requiere alojamiento del backend, HTTPS y configuración de entorno; GitHub por sí solo almacena el código y no ejecuta este servidor.

Las contraseñas usan PBKDF2 con sal aleatoria. Las sesiones expiran a las ocho horas y se gestionan con cookies HttpOnly y protección CSRF. Se registra la identidad del usuario que cambia datos. Las escrituras detectan revisiones antiguas para evitar sobrescribir cambios de otra sesión. Si aparece un conflicto, usa Actualizar antes de volver a editar.

## Verificar

Desde la carpeta del proyecto:

```bash
python -m unittest discover -s tests -v
```

También puedes verificar la lógica del frontend con Node.js (opcional): `node tests/test_frontend.mjs`.

Las pruebas levantan un servidor HTTP y una base temporal. Comprueban autenticación, permisos, CSRF, persistencia, valores cero, duplicados, relaciones, importación Excel, transacciones y conflictos. No modifican tu base de uso normal.

## Subir a GitHub

1. Crea un repositorio nuevo, por ejemplo `BSC-TechPeru`.
2. Sube **el contenido de esta carpeta**, con `README.md` en la raíz. Conserva frontend, backend, data/seed.json, docs y tests.
3. No subas `data/bsc.sqlite3`, contraseñas, archivos `.env` ni la carpeta `.git` de otro proyecto. El archivo `.gitignore` ya cubre los datos locales.
4. Copia el enlace real del repositorio y completa `docs/ENTREGA_PLANTILLA.txt` con tu nombre completo.

Esta entrega publica código y Excel. GitHub Pages solo admite archivos estáticos y no ejecuta este backend Python.
