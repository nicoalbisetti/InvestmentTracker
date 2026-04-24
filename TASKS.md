# TASKS — Mejoras CRUD Transacciones + Renombre Sidebar

## T1 — [Backend] Filtro por custodio y mes/año en GET /api/transactions
- [ ] Agregar parámetro `custodian: Optional[str]` con join a Instrument
- [ ] Agregar parámetro `month_year: Optional[str]` con filtro strftime

## T2 — [Frontend] Barra de filtros en /transactions
- [ ] Estado `filters` (custodian, month_year, type, instrument_id)
- [ ] Pasar filtros activos a `getTransactions`
- [ ] Resetear page=1 al cambiar filtro
- [ ] Select de Custodio (XP, SANTANDER, INTER, XP_INTERNATIONAL)
- [ ] Input type="month" para Mes/Año
- [ ] Select de Tipo con TYPE_OPTIONS
- [ ] Combobox de Instrumento (ver T4)
- [ ] Botón "Limpiar filtros" (solo visible si hay filtro activo)
- [ ] Conteo "X transacciones" debajo de los filtros

## T3 — [Frontend] Edición de transacciones
- [ ] Estado `editingTx` (null=crear, objeto=editar)
- [ ] Botón "Editar" en columna Acciones (antes de Eliminar)
- [ ] Pre-cargar formulario con datos de la transacción al editar
- [ ] Título del modal cambia a "Editar Transacción" en modo edición
- [ ] Campo instrumento como texto estático en modo edición (no editable)
- [ ] `handleSave` llama updateTransaction si editingTx, createTransaction si no
- [ ] Al cerrar modal: resetear editingTx y limpiar formulario

## T4 — [Frontend] Combobox con búsqueda para selector de instrumento
- [ ] Crear `frontend/src/components/ui/InstrumentCombobox.tsx`
- [ ] Props: value, onChange, instruments, placeholder, disabled
- [ ] Filtrado case-insensitive por name y custodian
- [ ] Cada ítem: nombre (bold) + custodian (gris, pequeño)
- [ ] Ícono X para deseleccionar
- [ ] Lista máx 200px, scrollable
- [ ] Ancho del dropdown = ancho del trigger
- [ ] Usar en formulario de transacción (reemplaza select)
- [ ] Usar en filtro de instrumento

## T5 — [Frontend] Renombrar label Sidebar
- [ ] Cambiar label de `/annual` de "Anual" a "Análisis de Patrimonio"
- [ ] Verificar que en modo colapsado no hay regresión
