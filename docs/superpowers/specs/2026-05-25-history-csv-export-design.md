# Design: CSV Export para Historia de Posiciones

**Fecha:** 2026-05-25  
**Estado:** Aprobado

---

## Objetivo

Agregar un botón de descarga CSV en la pantalla de Histórico de Posiciones (`/history`), con el mismo estilo visual que el botón existente en Posiciones. El CSV refleja exactamente los datos visibles en pantalla, incluyendo todos los filtros activos.

---

## Enfoque

Generación de CSV en el frontend (sin nuevo endpoint backend). La data ya está disponible en el estado React del componente al momento de la exportación.

**Motivo:** El filtro de texto de instrumento se aplica client-side; generar el CSV desde el estado garantiza que el archivo exportado coincide exactamente con lo visible en pantalla.

---

## Cambios en archivos

### `frontend/src/pages/History.tsx` (única modificación)

1. **Import:** Agregar `Download` desde `lucide-react`.

2. **Función `exportHistoryCSV()`:** Definida dentro del componente, accede directamente a `items`, `periods` y `totals` del estado.

   - Primera fila: `Instrumento, <period1>, <period2>, ...`
   - Segunda fila: `Total, <total1>, <total2>, ...`
   - Filas siguientes: `<item.name>, <value1>, <value2>, ...`
   - Valores `null` o `0` se escriben como cadena vacía `""`.
   - Valores numéricos crudos (sin formato de moneda).
   - Nombre del archivo: `historico_mensual_<year>_<currency>.csv` (vista mensual) o `historico_anual_<currency>.csv` (vista anual).
   - Descarga vía `Blob` → `URL.createObjectURL` → `<a>` programático → `revokeObjectURL`.

3. **Botón:** En la fila superior de controles, alineado a la derecha junto al toggle de moneda. Mismo estilo que Positions:
   ```
   className="btn-secondary text-sm p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
   title="Exportar CSV"
   ```
   Ícono: `<Download size={18} />`

---

## Comportamiento esperado

- El botón está siempre habilitado (si no hay datos, el CSV tendrá solo encabezados).
- No requiere estado adicional ni llamadas a la API.
- Funciona igual en vista mensual y anual.
- El CSV puede abrirse directamente en Excel o Google Sheets.

---

## Fuera de alcance

- Endpoint backend para exportación.
- Formateo de moneda en los valores del CSV.
- Exportación parcial o paginada.
