# Nuevo Instrumento Manual

## Descripción
Agregar en Settings → Catálogo de Instrumentos un botón "+ Nuevo Instrumento" que abre un modal con formulario completo para crear un instrumento manualmente, con saldo inicial opcional.

## Tareas

### Backend
- [x] Actualizar `InstrumentCreate` schema en `backend/app/schemas/instrument.py` con todos los campos nuevos
- [x] Agregar endpoint `POST /api/instruments` en `backend/app/routers/instruments.py`
  - Validar name/custodian no vacíos
  - Verificar duplicado (name + custodian) → 409
  - Crear Instrument
  - Si hay balance_brl: crear MonthlyPosition, calcular balance_usd desde quotes, actualizar cache

### Frontend — API Client
- [x] Agregar función `createInstrument(data)` en `frontend/src/api/instruments.ts`

### Frontend — Settings.tsx
- [x] Agregar estados: `showCreate`, `createForm`, `createSaving`, `createError`, `createWarning`
- [x] Agregar botón "+ Nuevo Instrumento" en la barra de filtros del catálogo
- [x] Agregar modal de creación con formulario completo (2 columnas, campos condicionales)
- [x] Comportamiento dinámico: currency↔location, asset_class/index_type ocultos si no renta_fija
- [x] Implementar `handleCreateInstrument()` con validación cliente + llamada API
- [x] Mostrar warning amarillo 5s después de creación exitosa con warning

### Documentación
- [x] Actualizar `CONTEXT.md`
- [x] Actualizar `PLAN.md`
- [x] Mover spec a `specs/done/`
