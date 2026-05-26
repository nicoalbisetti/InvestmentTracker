# History CSV Export — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar un botón de exportación CSV en la pantalla de Histórico de Posiciones que descarga los datos actualmente visibles (con todos los filtros aplicados) como archivo CSV de valores numéricos crudos.

**Architecture:** Generación de CSV 100% en el frontend. La función `exportHistoryCSV()` lee directamente el estado del componente (`items`, `periods`, `totals`) y produce un Blob descargable. No requiere cambios en backend ni nuevos endpoints.

**Tech Stack:** React 18, TypeScript, Lucide React (ícono `Download`), API nativa de browser (`Blob`, `URL.createObjectURL`).

---

### Task 1: Agregar función de exportación y botón en History.tsx

**Files:**
- Modify: `frontend/src/pages/History.tsx`

- [ ] **Step 1: Agregar `Download` al import de lucide-react**

En [frontend/src/pages/History.tsx](frontend/src/pages/History.tsx), la línea 1 no tiene imports de lucide-react. Agregar el import:

```typescript
import { Download } from 'lucide-react';
```

- [ ] **Step 2: Agregar la función `exportHistoryCSV` dentro del componente `History`**

Agregar esta función justo antes del `return` del componente (después de la declaración de `cellClass`, línea ~181):

```typescript
const exportHistoryCSV = () => {
  const header = ['Instrumento', ...periods.map(p => String(p))];
  const totalRow = ['Total', ...totals.map(v => (v === null || v === 0) ? '' : String(v))];
  const rows = items.map(item => [
    item.name,
    ...item.values.map(v => (v === null || v === 0) ? '' : String(v)),
  ]);

  const csvContent = [header, totalRow, ...rows]
    .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');

  const filename = view === 'monthly'
    ? `historico_mensual_${year}_${currency}.csv`
    : `historico_anual_${currency}.csv`;

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};
```

- [ ] **Step 3: Agregar el botón de exportación en la barra de controles**

En el JSX, localizar el `div` con `className="flex flex-wrap gap-2 items-center"` de la segunda fila de controles (línea ~204, que contiene el selector de año y el toggle BRL/USD). Agregar el botón de descarga al final de ese `div`, después del toggle de moneda:

```tsx
<div className="flex flex-wrap gap-2 items-center">
  {view === 'monthly' && (
    <select
      className="input w-28 text-sm"
      value={year}
      onChange={e => setYear(Number(e.target.value))}
    >
      {availableYears.map(y => <option key={y} value={y}>{y}</option>)}
      {!availableYears.includes(currentYear) && (
        <option value={currentYear}>{currentYear}</option>
      )}
    </select>
  )}
  <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
    {(['BRL', 'USD'] as const).map(c => (
      <button
        key={c}
        onClick={() => setCurrency(c)}
        className={`px-3 py-1.5 text-sm font-medium transition-colors ${
          currency === c
            ? 'bg-indigo-600 text-white'
            : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50'
        }`}
      >
        {c}
      </button>
    ))}
  </div>
  <button
    className="btn-secondary text-sm p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
    onClick={exportHistoryCSV}
    title="Exportar CSV"
  >
    <Download size={18} />
  </button>
</div>
```

- [ ] **Step 4: Verificar que el frontend compila sin errores**

```bash
cd frontend && npx tsc --noEmit
```

Esperado: sin errores de tipos.

- [ ] **Step 5: Verificar manualmente en el browser**

Con el frontend corriendo en `http://localhost:5173`:
1. Ir a la página de Histórico de Posiciones.
2. Verificar que aparece el ícono de descarga en la barra de controles (a la derecha del toggle BRL/USD).
3. Hacer click en el botón — debe descargarse un archivo `.csv`.
4. Abrir el CSV: verificar que la primera fila es el encabezado (`Instrumento, Ene, Feb, ...`), la segunda es `Total`, y las siguientes son instrumentos con valores numéricos crudos.
5. Cambiar a vista Anual y exportar — verificar nombre de archivo `historico_anual_BRL.csv`.
6. Aplicar un filtro de texto y exportar — verificar que el CSV refleja solo los instrumentos filtrados.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/History.tsx
git commit -m "feat(history): add CSV export button with client-side generation"
```
