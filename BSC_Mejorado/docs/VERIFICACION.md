# Verificación de la entrega

- Diez pruebas de integración HTTP y SQLite: correctas, sin pruebas omitidas.
- Importación real de los 36 indicadores del Excel mejorado: correcta.
- Una fila inválida después de una válida revierte toda la importación: comprobado.
- Rechazo de cambios sin autenticación, sin CSRF y sin permisos: comprobado.
- Cero, meta cero en reducción, duplicados por período y conflictos de revisión: comprobados.
- Lógica de las nueve vistas del frontend, filtros, año sin datos y formularios: comprobada con Node.js.
- Las 72 entradas del Excel (36 metas y 36 resultados) coinciden con el original.
- Recalculo del Excel, cambios de entrada, celdas vacías y cero: comprobados.
- Hojas y gráfico del Excel: revisados en imágenes renderizadas; gráfico nativo vinculado a fórmulas, con escala desde cero.

No se pudo ejecutar un navegador gráfico de prueba en este entorno. Por ello quedan pendientes la revisión visual del frontend en el navegador del estudiante y la comprobación del archivo en su versión local de Excel. La publicación en GitHub y el nombre del estudiante no se han completado automáticamente.
