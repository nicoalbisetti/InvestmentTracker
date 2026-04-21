# TASKS — Grilla Pagado con Previstos

- [ ] PASO 0: Crear TASKS.md y lista + tareas en ClickUp
- [ ] BACKEND: Cargar forecast_map en get_proventos_grid() desde ProventoForecast
- [ ] BACKEND: Construir forecast_months por instrumento (solo donde months[m] es null)
- [ ] BACKEND: Recalcular total de fila sumando pagado + previsto
- [ ] BACKEND: Recalcular month_totals sumando pagado + previsto por columna
- [ ] BACKEND: Agregar paid_month_totals al response (solo suma pagados)
- [ ] BACKEND: Recalcular grand_total con nueva lógica
- [ ] FRONTEND: Actualizar onClick de celda para pre-popular con forecast si no hay pago
- [ ] FRONTEND: Agregar lógica de color ternaria (verde / ámbar / gris)
- [ ] FRONTEND: Mostrar asterisco en celdas previstas
- [ ] FRONTEND: Colorear totales de columna en ámbar si incluyen previstos
- [ ] FRONTEND: Actualizar saveCell para limpiar forecast_months en estado local
- [ ] FRONTEND: Agregar leyenda verde/ámbar debajo de controles
- [ ] VERIFICACIÓN: Recorrer los 7 escenarios del Paso 3
- [ ] PASO FINAL: Actualizar CONTEXT.md y PLAN.md, mover spec, commit
