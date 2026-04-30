# TASKS — Monto por moneda en transacciones

## PASO 0 — Setup
- [x] Crear TASKS.md
- [x] Crear lista en ClickUp
- [x] Crear tareas en ClickUp

## Backend
- [ ] BACKEND: Agregar GET /api/quotes/lookup en quotes.py (antes del GET "")

## Frontend
- [ ] FRONTEND: Agregar estado quoteRate, quoteFound, manualRate, overrideSecondary
- [ ] FRONTEND: useEffect para fetch de cotización al cambiar fecha/instrumento/tipo
- [ ] FRONTEND: Lógica calculatedSecondary y effectiveRate
- [ ] FRONTEND: Nuevo layout del modal para tipos aplicacion/rescate (BRL y USD)
- [ ] FRONTEND: Bloque de cotización (encontrada / no encontrada / manual)
- [ ] FRONTEND: Checkbox de override con pre-carga del valor calculado
- [ ] FRONTEND: Construcción del payload en handleSave según currency
- [ ] FRONTEND: Comportamiento en modo edición (override=true por defecto)
- [ ] FRONTEND: Reset de estados nuevos en closeModal

## QA
- [ ] Verificar todos los criterios de aceptación

## PASO FINAL
- [ ] Commit con mensaje de spec
- [ ] Actualizar CONTEXT.md
- [ ] Mover spec a specs/done/
- [ ] Enviar mensaje a Slack
