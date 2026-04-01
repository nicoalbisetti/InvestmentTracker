# TASKS — Cambios al Histórico de Posiciones

> Feature: mejoras visuales y de UX en la página /history (vista mensual y anual)

---

## 1. Backend — Agregar campo `location` en respuesta

- [ ] Agregar campo `location` (brasil/exterior) en los items de `/api/history/monthly`
- [ ] Agregar campo `location` en los items de `/api/history/annual`

---

## 2. Frontend — Ordenar por mercado y tipo

- [ ] Ordenar filas: brasil primero → exterior después, y dentro de cada mercado por tipo (TYPE_ORDER)

---

## 3. Frontend — Verde si aumentó vs período anterior

- [ ] En vista mensual: celda verde si el valor es mayor al mes anterior del mismo instrumento
- [ ] En vista anual: celda verde si el valor es mayor al año anterior del mismo instrumento
- [ ] Celdas null/0 no aplican color

---

## 4. Frontend — Solo mostrar filas con valor

- [ ] Filtrar items cuyo array `values` sea todo null/0 — no mostrarlos en la tabla
- [ ] Aplicar tanto en vista mensual como anual

---

## 5. Frontend — Totales arriba y fijos

- [ ] Mover la fila de totales al thead (arriba del todo), debajo del header de períodos
- [ ] Hacerla sticky junto al header

---

## 6. Frontend — Sacar el custodio

- [ ] Eliminar la línea secundaria con el custodio en la columna de instrumento
- [ ] Reducir el padding vertical de las filas para que sean más compactas
