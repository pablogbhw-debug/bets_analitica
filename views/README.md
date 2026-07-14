# Capa Vista

Responsabilidad MVC: capturar entradas y renderizar resultados; no ejecuta SQL.

- `componentes.py`: selectores, formato monetario y estilos reutilizables.
- `autenticacion.py`: formularios básicos de inicio de sesión y registro.
- `resumen/`: métricas, gráficos, riesgo y alertas.
- `recarga/`, `apuesta/`, `pendientes/`, `retiro/`: formularios de operaciones.
- `casas/`: configuración de reglas por casa.
- `historial/`: consulta, edición y eliminación visual de registros.

Mapeo del sílabo: entrada de datos, conversión de tipos, cadenas, formularios, selección condicional, tablas, métricas, gráficos y mensajes de retroalimentación con Streamlit.

Las vistas solo importan controladores y entidades de presentación; toda decisión financiera se obtiene desde `controllers/`.
