# Mejoras respecto al material original

## Excel

- Conserva los siete tabs, 12 objetivos, 36 indicadores y todas las metas y resultados originales.
- Sustituye el dashboard de cifras fijas por fórmulas vinculadas a las entradas.
- Corrige el semáforo: cumplido desde 100%, en riesgo desde 80%, crítico por debajo de 80%.
- Diferencia vacío, cero e indicadores de reducción; incorpora validación de entradas y códigos de importación.
- Calcula el promedio por objetivo y perspectiva; incluye un gráfico editable y todas las 36 filas en el detalle.
- Actualiza recomendaciones según el estado y conserva acciones específicas por indicador.
- Centraliza las entradas en BSC Completo: las hojas por perspectiva ya no mantienen copias independientes de los resultados.

## Frontend

- Unifica empresa, año e indicadores con el Excel: TechPeru SAC, 2025.
- Rediseña acceso, navegación, tablas, tarjetas, formularios y vista para celulares.
- Añade filtro anual real, búsquedas, filtros de estado, exportación CSV de la vista y guía de uso.
- Evita tendencias inventadas: presenta solo los períodos con mediciones.
- Los cambios se confirman después de una respuesta satisfactoria del servidor; los errores permanecen visibles en el formulario.
- La navegación usa teclado, formularios con etiquetas y diálogo nativo con control de foco.

## Backend

- API REST Python con SQLite y relaciones entre objetivos, indicadores, mediciones e iniciativas.
- Acceso real, contraseñas derivadas con PBKDF2, sesiones y permisos comprobados en servidor.
- Registro de cambios con usuario y fecha; comprobación de revisiones para cambios simultáneos.
- Validaciones de números, fechas, referencias y duplicados por período.
- Importación transaccional del Excel mejorado sin librerías externas.
- La base persiste entre ejecuciones y se excluye del repositorio.

## Límites de esta entrega

Se trata de una aplicación académica ejecutable en la computadora, no de un servicio empresarial desplegado. El Excel y la aplicación se sincronizan por importación manual. Las metas son anuales; para evaluar metas mensuales distintas haría falta un calendario de metas por período, que el material fuente no incluye.

La aplicación usa tres estados de desempeño y un estado Sin datos, con reglas coherentes entre sistema y Excel. No incluye correos automáticos ni integración con fuentes contables externas.

El prototipo original recibido se conserva como antecedente del trabajo; esta versión se entrega como ampliación académica del material proporcionado por el docente.
