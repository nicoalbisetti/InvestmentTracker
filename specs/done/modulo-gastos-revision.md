# Módulo de Gastos — Revisión de la spec, plan y crítica

Fecha: 2026-10-20 · Insumos: `specs/pending/modulo-gastos.txt`, `CONTEXT.md`, `.claude/CLAUDE.md`, código real (`database.py`, `main.py`, `models/`, `routers/transactions.py`, `services/proventos_importer.py`, `App.tsx`, `Sidebar.tsx`, `client.ts`) y los archivos de `docs/expenses/`.

> Este documento **no contiene nombres de terceros, CUIT, CBU/CVU ni números de cuenta**; cuando hace falta aludir a un dato así, lo describe ("nombre del titular", "tercero"). Las referencias `L123` son números de línea de la spec.
> No se tocó ninguna base real/demo (las consultas a la DB se hicieron sobre una copia en el scratchpad) ni el trabajo sin commitear de Simulación. No se escribió código.

---

## 0. Resumen ejecutivo (lo más importante)

1. **La spec es sólida en el dominio** y los formatos de los 3 CSV y de Mercado Pago se confirmaron contra archivos reales. Los problemas están en (a) supuestos sobre el repo que son falsos, (b) dos reglas de conciliación que no funcionan con los datos reales de Argentina, y (c) privacidad: **el propio spec (paso 0.3 lo commitea) contiene nombres de terceros**.
2. **Bug de fondo en el wiring de tablas**: `create_tables()` solo hace `create_all` sobre el engine real; la DB demo **no** recibe tablas al arrancar. El criterio "tablas creadas en real y demo al iniciar" es falso tal como está escrito (§1.1-A).
3. **Pagar tarjetas Argentina "por total exacto" no funciona**: el débito en cuenta = pesos + USD × TC del día, y el resumen declara pesos y USD por separado. Además hay pagos parciales/múltiples por resumen. El vínculo confiable es *débito en cuenta ↔ línea "SU PAGO" del resumen siguiente* (monto exacto), no el total del resumen (§1.5, §3.3).
4. **"Tarjeta sin detalle" tiene riesgo real de doble conteo** si el vínculo falla (falla "abierta"). Hay que decidirlo por cobertura (tarjeta × mes con resumen), no por vínculo (§3.3).
5. **El criterio T-05 #4 (LIQ. CAMBIO + IOF = rescate CDB) está semánticamente invertido**: son salidas de la cuenta XP *posteriores* al ingreso de 76.594,00; el rescate corresponde al Pix recibido, no a las dos filas de cambio (§1.5-F).
6. **El orden de XP "descendente → invertir" rompe el saldo corrido** en 3 filas (empates de segundo con orden ascendente dentro del empate). Hay que reconstruir el orden por la cadena de saldos (§1.5-A).
7. **Faltan reglas que mueven mucho el %**: con las reglas del spec, XP queda en 89% de filas sin revisar (96% por monto) — el criterio ≥90% sólo se cumple sumando Inter, y es in-sample (§1.5-A). Mercado Pago tiene 105 movimientos internos ("Dinero reservado/retirado") sin regla.
8. **Recomendación**: v0 acotada (T-01 + 3 parsers CSV + dedup + clasificador + vínculos BR + resumen + UI mínima), **base SQLite separada** para gastos, y PDFs argentinos como v0.5/v1 en este orden: Mercado Pago → cuenta Santander → tarjetas (§3.5).

---

## 1. REVISIÓN DE LA SPEC

### 1.1 Contraste con el código real

| # | Spec dice | Realidad | Impacto |
|---|---|---|---|
| A | T-01: registrar modelos en `create_tables()`; AC "Tablas creadas en **real y demo** al iniciar" (L75-77, L172) | `create_tables()` (`database.py:140-155`) hace `Base.metadata.create_all(bind=engine)` **solo** sobre el engine real. Las migraciones `_migrate_*` sí corren en ambos engines en `startup()`, pero `create_all` no. La demo se arma con `create_demo_db.py`, que **copia el esquema desde la DB real** (`get_demo_schema` lee `sqlite_master` de la real). | Hay que llamar `create_all` también sobre `demo_engine` (o, con DB separada, sobre sus dos engines). Si se queda tal cual, `/api/expenses/*` con `X-Env: demo` falla con "no such table". |
| B | "Tablas nuevas → create_all alcanza, no hace falta migración ad-hoc" (L76) | Cierto para la primera versión. En cuanto se agregue una columna (inevitable: ya hay 3 ambigüedades que lo van a pedir) hay que seguir el patrón `_migrate_*` de `main.py` en ambos engines. | Planificar un `expenses/migrations.py` desde el inicio, aunque esté vacío. |
| C | Modelo "`ProventoItem`" (L25, L147) | La clase se llama **`ProvéntoItem`** (con tilde) en `models/provento_item.py`. | `linking.py` debe importar `ProvéntoItem`. Detalle fácil de romper. |
| D | Linking contra `Transaction`: "mismo signo lógico", "monto exacto" (L419-422) | `Transaction` tiene **montos sin signo** (el signo lo da `type`: solo existen `aplicacion` y `rescate` en la base, 55 y 44 filas), **sin moneda** (hereda del `Instrument.currency`), sin custodia propia (está en `Instrument.custodian`). | El matcher necesita mapear `type`→signo y obtener la moneda/custodia vía join. Con `amount_brl` siempre cargado (0 nulos en 2026) alcanza para BRL; para instrumentos USD hay que decidir contra `amount_usd`. |
| E | Inversiones = `Transaction` + `ProventoItem` (L405-420) | Existe además **`EquityTrade`** (compras/ventas de acciones, con `usd_rate`). Aportes a "Alpha Trading/Deitres/Brasil Bitcoin/Mercado Bitcoin/Td" pueden corresponder a otros modelos. | La spec no dice qué pasa con aportes a renta variable: ¿se vinculan a `EquityTrade` o quedan "sin vincular" para siempre? Hay que definirlo o excluirlos de la auditoría. |
| F | `ProvéntoItem.custodian` útil para filtrar (L429-431) | En 2026, **171 de 230 proventos tienen `custodian` NULL**. La spec ya dice "no filtrar por custodia": correcto, y además no se podría. | Sin impacto, confirma la decisión. |
| G | `in_liquidation=1` para FGC (L424) | Existe en `Instrument` (4 instrumentos). ✔ | OK. |
| H | `parse_br_number()` "existente, moverlo a `app/utils/numbers.py`" (L198) | Está en `services/proventos_importer.py:146`. **`app/utils/` no existe.** Elimina *todos* los `.` y reemplaza `,`→`.`: no maneja `R$`, signo `-R$`, signo final (`1672.047,98-`) ni `$ -565.200,00`. | Mover/re-exportar **toca código de inversiones** (contradice "ningún módulo de inversiones se modifica"). Mejor: no moverlo; escribir `expenses/parsers/numbers.py` (≈30 líneas, con `Decimal`). |
| I | Sidebar en "frontend/src/..." sin ruta; "Sidebar" y "App.tsx" (L519, L546) | Sidebar real: `frontend/src/components/layout/Sidebar.tsx`, lista `NAV_ITEMS`. `Wallet` existe en lucide-react 0.577 ✔. Ruta se agrega en `App.tsx` como las demás. | OK, solo precisar la ruta. |
| J | Reusar "patrón InstrumentCombobox" (L530) | Existe: `components/ui/InstrumentCombobox.tsx`, pero es **específico de instrumentos** (usado solo en `Transactions.tsx`). | Hay que crear un `Combobox` genérico en `components/expenses/`; no se puede "reutilizar" sin tocar el componente de inversiones. |
| K | "`npm run build` sin errores de TypeScript" (L547) vs `CLAUDE.md`: "Siempre `bun`, no `npm`" | `frontend/package.json` tiene `build`/`lint`/`dev`; hay `package-lock.json` (no `bun.lockb`). **No hay `package.json` en la raíz**, así que `bun run typecheck`, `bun run test`, `bun run test:file`, `bun run lint:claude` de CLAUDE.md **no existen**. Backend: no hay `backend/tests/`, y **pytest no está instalado** ni en `requirements.txt`. | Contradicción spec↔CLAUDE.md y CLAUDE.md↔repo. Hay que bootstrapear pytest (T-00) y fijar comandos reales. |
| L | `get_db` Demo/Real (L31) | `get_db(request)` entrega `Session` por header `X-Env`; `client.ts` agrega el header sólo si `localStorage.app_env === 'demo'`. ✔ El servicio de FX (HTTP externo) y el parseo no dependen de `get_db`. | OK. Ojo: `linking.py` corre dentro del mismo `Session`; con DB separada necesita dos sesiones (§3.1). |
| M | Routers se registran en `main.py` | Se agregan a mano con `app.include_router`. ✔ | Una línea en `main.py` (el spec debería admitir explícitamente que `main.py` y `database.py` se tocan). |

### 1.2 Contradicciones y ambigüedades

1. **Privacidad vs paso 0.3.** La decisión 7 (L47-51) dice que nombres de terceros "NUNCA se commitean", pero el spec (`modulo-gastos.txt`) contiene en las reglas semilla (L344-384) y en ejemplos de PDF (L252, L255) el nombre completo del titular (5 apariciones), el de la persona de limpieza, el de un familiar y el de otro tercero, además de empleador/contador. El paso 0.3 es `commit: add spec`. **Hay que depurar el spec antes de commitearlo** (usar placeholders `<TITULAR>`; las reglas reales viven solo en `rules.local.json`). Ver D-02.
2. **CONTEXT.md.** CLAUDE.md exige actualizar páginas/endpoints/features en `CONTEXT.md`; la spec dice "no inflar CONTEXT.md" y crear `CONTEXT-expenses.md` (L28, L603-605). Propuesta: `CONTEXT-expenses.md` con el detalle + en `CONTEXT.md` una sección corta (página `/gastos`, endpoints `/api/expenses/*` como una línea, feature en la lista, fecha). Cumple ambos.
3. **Paso 0.1** ("seguir los pasos de setup de `.claude/CLAUDE.md` (ClickUp/TASKS.md)", L65): CLAUDE.md **no define** pasos de ClickUp; `TASKS.md` es de una tarea vieja y ajena ("Ajustes Vista Mensual Patrimonio"). Ambiguo: ¿crear un `TASKS.md` nuevo (pisando el existente)? ¿una lista en ClickUp? Pregunta para Nico (D-12).
4. **Paso 0.2/0.3 y git.** `specs/pending/` entero está **sin trackear** (incluye `SPEC_simulation_fixes.md`, que es de Simulación). Un `git add specs/pending` arrastraría ese archivo. Los commits deben ser por ruta explícita. Además `docs/expenses/` **hoy no está ignorado** (`git check-ignore` rc=1) y aparece como `??` en `git status`: un `git add .`/`-A` lo subiría. El `.gitignore` es lo primero, y en un commit propio.
5. **`statement_total_native` único (L94)** vs tarjetas argentinas con **dos totales** (pesos y USD) (en los archivos actuales hay **un** "Total Consumos" por resumen, pero conviene no asumirlo). Hace falta `statement_totals` JSON por moneda.
6. **`needs_review` sobrecargado** (clasificación, signo, FX estimado: L125, L468-469). Mezcla colas distintas; conviene `needs_review` + `fx_estimated` (bool) separados, o una columna `review_reasons` (JSON/CSV).
7. **Staging indefinido** ("tabla staging o JSON en el batch", L296-297). Con `dedup_hash UNIQUE` no se pueden insertar filas en `exp_transactions` para el preview. Decidir: JSON en el batch (simple; los overrides del confirm se aplican al confirmar). Recomendado.
8. **`date` de tarjetas = vencimiento** (L113): es una decisión de base *caja por cuota* razonable (decisión 3), pero implica que el "gasto del mes" de una compra en diciembre pagada en enero cae en enero. Debe quedar escrito en la UI/KPIs, y `purchase_date` debe estar disponible como eje alternativo. No es un error, pero la spec no lo presenta como trade-off.
9. **Fecha de FX**: no dice con qué fecha se convierte. Por coherencia con (8): la de `date` (cobro/vencimiento), no la de compra. Escribirlo.
10. **Signo del "pago de tarjeta" en el resumen argentino**: la línea `SU PAGO EN PESOS` trae **dos importes** (ver §1.5-E); la spec solo dice "con `-` al final". Cuál es el que se guarda no está definido.
11. **`fx_conversion` con "cualquier signo" y T-05 #4**: ver §1.5-F.
12. **"Criterios por mes ene–sep"** (T-05/T-07): los extractos argentinos terminan en **junio/julio** (cuenta Santander hasta 02/07, VISA hasta 08/06, AMEX hasta 20/07, MP hasta 07/2026) y los brasileños en septiembre. Un resumen "ene–sep" mostrará Argentina en cero en jul–sep sin avisar. Falta un **indicador de cobertura por cuenta × mes** (qué meses tienen extracto).

### 1.3 Cosas que faltan

- **Reglas de clasificación faltantes** (medidas, §1.5-A): `TED recebida de <titular>` (12 filas XP, ≈R$ 57k) no matchea la regla de Pix propio; `AUTOPASS` (8 filas, peajes) y comercios de tarjeta (aéreas, supermercado, ropa: 86% de las filas de tarjeta XP sin regla); Mercado Pago `Dinero reservado/retirado Gastos` (105 filas = movimientos internos entre saldo y "reserva"), `Pago de servicio …`, `Pago de suscripción …`.
- **Casos de pago de tarjeta**: pagos parciales/múltiples por resumen (VISA ene-26 tiene 3 líneas SU PAGO; VISA feb-26 tiene 2), pago en pesos de saldo en USD con TC, pago tardío con cargos (XP mar-26), primer resumen del rango cuyo pago refiere a un resumen **no importado** (XP: pago de R$ 4.899,71 en el resumen de enero corresponde a diciembre).
- **Adicionales**: en los archivos actuales no hay (un solo "Total Consumos" por resumen) y `Portador` es siempre el titular con variantes de nombre; si aparecen, ignorar `Portador` (como dice la spec) los mezclaría.
- **Idempotencia de seeds de reglas** (¿se re-aplica `rules.local.json` en cada arranque? ¿pisa reglas editadas en UI?). Definir por `origin` + clave estable.
- **Re-clasificación**: qué pasa con filas ya confirmadas cuando cambia una regla seed (la AC dice "nunca pisan manual", falta el caso `rule`→`rule`).
- **Borrado de lote** con filas editadas manualmente: se pierden las ediciones; ¿advertir? ¿conservar?
- **Moneda de `amount` en cuentas multimoneda** (Santander AR ARS+USD): `exp_accounts.currency` es "la principal", pero las filas llevan su moneda; el saldo corrido se valida **por sección**, eso sí lo contempla.
- **Qué hace el resumen con USD de cuentas BR** (XP US no se importa) — ver §1.5-F.
- **Zona horaria/hora**: XP trae hora; no se guarda. Sirve para desempate y para el hash (§3.4).
- **Seguridad/privacidad operativa**: ver §3.1 (nombre de archivo con nº de cuenta, `owner_identifiers` en la misma DB que se respalda, logs/errores del parser).
- **Tests de arquitectura**: nada que *haga cumplir* "ningún módulo de inversiones importa `expenses`" ni "solo `linking.py` lee inversiones".

### 1.4 Criterios de aceptación que no se pueden verificar (o verifican otra cosa)

| AC | Problema | Propuesta |
|---|---|---|
| T-01 "Tablas creadas en real y demo al iniciar" | Falso con el código actual (§1.1-A). | Test: levantar app con ambas DB vacías y consultar `/api/expenses/accounts` con y sin `X-Env`. |
| T-01 "Seeds idempotentes" | OK pero sin definición de qué se compara. | Test: correr seed 2 veces → mismos conteos y ids. |
| T-02 "todos los checks de validación en verde para TODOS los archivos actuales" | Verificable, pero depende de arreglar el orden de XP (§1.5-A) y de definir "check" para PDFs (saldo corrido de Santander tiene líneas de resumen que contaminan). | Listar los checks por parser en el spec. |
| T-02 `detect()` "los 7 tipos" | Los parsers listados son **6**, no 7. Inventario real de archivos: 6 extractos Santander cuenta, 8 MP, 8 AMEX, 7 VISA, 9 faturas XP, 2 CSV XP cuenta, 1 CSV Inter = 7 *formatos* si se cuentan VISA y AMEX por separado. | Aclarar "6 parsers / 7 formatos". |
| T-04 "≥90% de filas de XP e Inter sin needs_review" | (1) Medí con las reglas del spec: **XP 89% (96% por monto), Inter 100%, combinado 92%**; XP solo no pasa. (2) Es **in-sample** (las reglas se escribieron mirando estos archivos). (3) No dice si es por filas o por monto. | Definir métrica (filas *y* monto), en conjunto y por cuenta; aceptar holdout: reglas con meses ene–jun, medir jul–sep. |
| T-05 "Pix Inter→XP 20/20; XP→Inter 16/16" | Reproducido: Inter→XP **20 pares exactos** (de 22 envíos al titular; 2 van a otros bancos); XP→Inter **16** pares (de 25 envíos; 9 van a otros bancos). El "n/n" sugiere cobertura total, pero 11 envíos quedan como "contraparte no importada". | Reescribir: "20 y 16 pares confirmados; 2 y 9 restantes = contraparte no importada, sin falsos positivos". |
| T-05 "Las 9 faturas XP vinculadas con monto exacto" | Verificado: la cadena es exacta (cada pago = total de la fatura anterior en las 8 transiciones). **Ene** paga una fatura no importada (R$ 4.899,71). Son 8 vínculos fatura→pago + 1 pago huérfano al inicio. | "9 faturas; 8 con pago, la 9ª (sep) sin pago aún; el pago de ene queda 'fatura no importada'". Verificar contra la cuenta XP: el pago de la fatura de sep (vence 20/09) debería estar; ver D-19. |
| T-05 #3 FGC "sugieren los rescates de Master, Pleno y Will" | Depende de datos de inversiones que cambian (ya se corrigieron el 20/10). Confirmé que existe un rescate de 29.208,78 en la copia de la DB. | Congelar un fixture de inversiones sintético; usar datos reales sólo como test opcional. |
| T-05 #4 LIQ. CAMBIO + IOF = rescate CDB | **Semánticamente incorrecto** (§1.5-F). | Reformular antes de implementar. |
| T-05 #5 "Débito automático tarjeta Inter aparece como 'Tarjeta sin detalle'" | Verificable. Son 9 débitos chicos (R$ 125,58 mayoritariamente; total ≈ R$ 1,6k): bajo valor para toda la maquinaria. | Mantener, es un buen test de la regla de cobertura (§3.3). |
| T-07 "gasto XP ≈ R$ 27k ene–jun más las faturas" y "~R$ 370k de flujos internos" | "del orden de", "más las faturas": no es un número. Depende de la clasificación final. | Congelar un *golden* local (`.local.json`, gitignored) con totales por kind generado y *revisado a mano una vez*; testear regresión contra eso. |
| T-07 "total del summary = suma de movimientos" | Tautológico si ambos usan la misma lógica. | Test de invariante: Σ(kind incluidos) − Σ(excluidos) = Σ(todas las filas) por moneda; y que cada fila esté en exactamente un balde. |
| T-08 `npm run build` | Ver §1.1-K. | `cd frontend && bun run build` (CLAUDE.md) y `bun run lint`. |
| T-08 "Ningún componente de inversiones se modifica salvo Sidebar y App.tsx" | Verificable por `git diff --stat`, pero §1.1-J muestra que reusar el combobox obliga a modificarlo. | Permitirlo vía componente nuevo; agregar chequeo en CI. |

### 1.5 Verificación parser por parser con archivos reales

Se leyeron localmente los archivos de `docs/expenses/` (nada se copió fuera del scratchpad; los datos personales no se reproducen acá).

#### A. `xp_account_csv` — **Mayormente correcto, con un bug de orden**

Archivos: `XP 2026-01 2026-6.csv` (205 filas), `XP 2026-07 2026-09.csv` (98).
- ✔ UTF-8 con BOM, `;`, encabezado `Data;Hora;Descricao;Valor;Saldo`, fecha `dd/mm/yy`, valores `-R$ 1.234,56`.
- ✔ Orden descendente por fecha/hora.
- ✔ Continuidad entre archivos: el saldo de apertura del 2º (R$ 3,13) = saldo final del 1º. Apertura del 1º = 0.
- ✘ **"Ordenar ascendente" invirtiendo el archivo rompe el saldo corrido en 3 filas.** Dentro de un mismo segundo (`29/04/26 10:32:47`, las dos filas de cambio/IOF) el archivo las lista en orden *ascendente* aunque el resto es descendente. Ordenar por (fecha, hora) con sort estable tampoco arregla (6 desajustes). Solución: **reconstruir la secuencia por la cadena de saldos** dentro de cada grupo de empate (prev + valor = saldo). Esto afecta además al `ordinal` del hash (§3.4).
- Datos para la 2ª parte del criterio: la fila `LIQ. CAMBIO VENDA` −75.760,63 y `IOF CAMBIO` −833,37 existen (29/04), ✔.
- Cobertura de reglas: ver tabla en §3.5 (métricas).

#### B. `xp_card_csv` — **Correcto**

Archivos: 9 faturas (`Fatura2026-01-20` … `2026-09-20`).
- ✔ BOM, CRLF, `;`, columnas `Data;Estabelecimento;Portador;Valor;Parcela`.
- ✔ Parcela: `n de N`, `-`, y ` de 1` (las líneas de cargos por atraso y el pago traen ` de 1`). También aparece ` de N`.
- ✔ **Fatura 2026-03-20: total sin pagos = 14.961,54; 1 pago de −12.320,58** (línea `Pagamento de fatura`). Los 4 cargos existen (246,41; 104,60; 49,85; 12,32).
- ✔ **Fatura 2026-04-20: 14 filas EASYJET R$ 10,00 del 24/03** (16 EASYJET en total: 14 de 10,00 + 3,30 + 4,29). Es el único caso de filas idénticas en los 9 archivos.
- ✔ Cadena exacta: pago de cada fatura = total de la anterior (8/8). Extra: la **única** negativa de abril además del pago es una devolución de comercio; en septiembre hay 3 negativas no-pago (`12GO`, `ESTORNO ANUIDADE CARTAO`, `Estorno IOF Exterior`) → `refund` ✔ como dice la spec.
- Dos textos de pago distintos (`Pagamentos Validos Normais` vs `Pagamento de fatura`): la spec ya lo prevé. ✔
- ⚠ La fecha de vencimiento sale del nombre (`FaturaYYYY-MM-DD`): confirmado que coincide con la cadena de pagos (fatura 03-20 pagada ~20/03).

#### C. `inter_account_csv` — **Correcto, con precisiones**

Archivo: `Inter Extrato-01-01-2026-a-30-09-2026-CSV.csv` (113 movimientos).
- ✔ UTF-8 **sin** BOM; preámbulo de 5 líneas + línea en blanco antes de `Data Lançamento;Descrição;Valor;Saldo` (la spec dice "4–5": correcto buscar el encabezado por texto).
- ✔ Fechas `dd/mm/yyyy` (a diferencia de XP, año de 4 dígitos). Valores sin `R$`.
- ✔ **El archivo está en orden ascendente** y el saldo corrido cierra sin desajustes (0/113). Es el opuesto de XP: el parser no debe asumir un orden.
- ⚠ El preámbulo contiene el **nº de cuenta**: no debe guardarse en `validation`/logs (privacidad).
- ⚠ El `Cp :<código>-<nombre>` trae un código de **8 dígitos** (ISPB), no "código de banco" de 3 dígitos como sugiere la spec; algunos Pix recibidos vienen como `BANCO INTER SA` sin `Cp`.
- ✔ Regla `Credito B3|Credito Evento B3` matchea los créditos de proventos y también las "Nota de Aluguel" de R$ 0,43–2,12 (comisiones de aluguel de acciones). Son centavos; no deberían ir a Proventos como evento propio (decidir si `provento` o `income/Rendimientos`).

#### D. `santander_ar_account_pdf` — **Parcialmente correcto; el riesgo más alto del parsing**

Archivos: 6 PDFs mensuales (9–16 páginas c/u).
- ✔ `Desde:`/`Hasta:` presentes; sección "Movimientos en dólares" existe; `Saldo Inicial` existe y las líneas de resumen contaminan cualquier regex ingenuo.
- ✔ Cadena de saldo en pesos consistente: sobre filas de movimiento, los únicos "cortes" son filas de resúmenes (totales de tarjeta, etc.), no movimientos.
- ✘ **"La línea siguiente sin fecha es detalle" es inexacto.** La fecha de la fila está **centrada verticalmente** en la celda multilínea: en el texto plano aparece *a veces antes, a veces entre* la línea principal y el detalle (p. ej. `Pago ... $ x $ y` → `04/03/26` → `A <tercero> / pago ct / ...`), y para varias filas del mismo día aparece una sola vez. El extractor de texto asigna mal fecha y detalle. **Hay que usar coordenadas (`extract_words` con `top`/`x0`)** como ya admite la spec para MP.
- ✘ Líneas intercaladas tipo `Del 01/02/26 al 28/02/26` (período de intereses) aparecen *dentro* del bloque de una fila y se concatenarían al detalle.
- ✘ Dos columnas de importe distintas ("Caja de Ahorro en pesos" / "Cuenta Corriente en pesos"); hay que determinar por posición x en qué columna cae el importe.
- ⚠ Variantes numéricas confirmadas: `$ 103.091,80` (a veces el texto trae `$ 103.091 80` en la portada), `-$ 26.555,51`. La portada tiene importes con la coma perdida (`$591.44881`): **no usar la portada**, usar la tabla.
- ⚠ El **nombre del archivo contiene el nº de cuenta** (`YYYY-MM-DD_<nº de cuenta>.pdf`) y el encabezado trae CUIT/CBU/domicilio: ni el nombre de archivo ni esos campos deben persistirse.

#### E. `mercadopago_pdf` — **Correcto**

Archivos: 8 PDFs (dic-25 … jul-26).
- ✔ `RESUMEN DE CUENTA EN PESOS`, `Periodo: Del 1 al 30 de abril de 2026`, declarados `Entradas/Salidas/Saldo inicial/Saldo final` ✔.
- ✔ Fecha `dd-mm-yyyy`, ID de operación, descripción partida arriba y abajo de la fila con fecha ✔ (ver abril: "Transferencia recibida Julio" / fila / nombre del tercero).
- **Validé con un parser rápido: 8/8 archivos cierran** (saldo corrido, Σ entradas, Σ salidas, saldo final). Es el PDF más barato de implementar.
- ✘ Formato de importe **distinto** de Santander: `$ -565.200,00` (signo dentro) vs `-$ 26.555,51`. `parse_ar_number` debe aceptar ambos.
- ✘ **Sin regla en la spec**: `Dinero retirado Gastos` (90 filas) y `Dinero reservado Gastos` (15): movimientos entre el saldo y una reserva interna de MP. Sin regla → 105 de 562 filas (19%) irían a revisión; deben ser `own_transfer` (o un kind `internal`).
- ⚠ `Rendimientos` ✔ (151 filas) cubierto por la regla.

#### F. `santander_ar_card_pdf` (VISA y AMEX) — **Estructura correcta; conciliación mal planteada**

Archivos: 7 VISA (dic-25 … jun-26) y 8 AMEX (dic-25 … jul-26).
- ✔ Encabezado `CIERRE dd Mmm yy VENCIMIENTO dd Mmm yy` (en el texto extraído viene **pegado**: `CIERRE 26 Feb 26VENCIMIENTO 09 Mar 26`; regex sin espacio obligatorio). El vencimiento coincide con el nombre del archivo.
- ✔ Filas `[YY Mes] DD comprobante * COMERCIO C.nn/NN importe`; meses reales encontrados: `Setiem.`, `Noviem.`, `Diciem.`, `Octubre`, `Enero`… **`Setiem.` (no `Sept.`) y `Noviem.`**: incluir ambas variantes. Año de 2 dígitos arrastrado ✔ (p. ej. `25 Setiem. 02`).
- ✔ Impuestos como líneas (`IMPUESTO DE SELLOS`, `IIBB PERCEP`, `IVA RG 4240`, `DB.RG 5617`) ✔ presentes (bloque aparte, tras el listado de consumos).
- ✔ `DEBITAREMOS DE SU C.C. … LA SUMA DE $ X [+ U$S Y]` presente en 15/15 resúmenes. **Formatos de importe extraños**: `$ 1672047,98` (sin separador de miles), `1457.940,02` (punto de miles faltante delante), `1672.047,98-`. `parse_ar_number` por "quitar `.`, `,`→`.`" lo resuelve, pero **no usar regex que exijan grupos de 3 dígitos**.
- ✔ `Total Consumos de …` aparece una vez por resumen; la spec lo usa solo para validar ✔. En los VISA la línea de total lleva también USD (`* 3,07 *`).
- ✘ **`SU PAGO EN PESOS` tiene 3–4 importes**: `SU PAGO EN PESOS 1462.332,82 TC1445,000 1457.940,02- 3,04-` = (pesos efectivamente debitados) + TC + (crédito en pesos) + (crédito en USD). El débito real de la cuenta = pesos + USD × TC (comprobado: el débito del 09/03 en la cuenta es 1.676.453,43 = 1.672.047,98 + 3,07 × 1.435, y ese mismo importe aparece en la línea SU PAGO del resumen de abril). La spec "TC solo como dato" queda corta: **el importe de la primera columna es el que concilia con la cuenta**.
- ✘ **Pagos múltiples por resumen**: VISA ene-26 tiene 3 líneas `SU PAGO EN PESOS` (586.923,58 / 4.482,20 / 575.086,00); VISA feb-26 tiene 2. Un solo "card_payment ↔ statement_total exacto" no los vincula.
- ✘ Los SALDO ACTUAL de página están vacíos salvo en la última (la spec acierta en que hay que usar DEBITAREMOS; confirmo que `SALDO ACTUAL` aparece con valor sólo en la última página).
- ⚠ AMEX sólo trae pesos (`U$S 0,00`) y casi no tiene cuotas; VISA tiene muchas (hasta 15 `C.nn/NN` por resumen).
- ⚠ Para USD en VISA hay consumos en dólares (suscripciones ~3 USD/mes) y un cargo USD de 8,42 en mayo.

**Conciliación con la cuenta — corregida:** para Argentina conviene vincular `débito en cuenta ↔ línea SU PAGO del resumen N+1` (igualdad exacta de importe y fecha ±2 días), y `resumen N ↔ resumen N-1` por el DEBITAREMOS (pesos+USD×TC con tolerancia). Para el último resumen importado (sin N+1) hay que aceptar tolerancia de TC o dejar "sugerido".

#### G. Caso transversal: "LIQ. CAMBIO + IOF = rescate" (T-05 #4)

El 29/04 la cuenta XP **recibe** un Pix de R$ 76.594,00 desde otra cuenta propia (09:56) y **después** (10:32) debita LIQ. CAMBIO VENDA 75.760,63 + IOF 833,37 = 76.594,00. Es una cadena: *rescate CDB Santander → Pix a XP → conversión a USD → (XP US, no importada)*. El rescate corresponde al **Pix recibido** (`own_transfer` con contraparte no importada ligada a un `investment_withdrawal` del instrumento), y las filas de cambio son la salida hacia la cuenta USD. Vincular un rescate (positivo) a dos débitos (negativos) viola la propia regla de signos de la spec (L133-136) y además dejaría la plata "desaparecida" del lado USD (debería registrarse como aporte a inversiones/cuenta propia exterior, o como `own_transfer` fuera del sistema).

### 1.6 Fuentes de tipo de cambio — verificadas en vivo (2026-10-20)

| Fuente | Endpoint | Resultado |
|---|---|---|
| PTAX BCB (Olinda) | `https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)?@dataInicial='MM-DD-YYYY'&@dataFinalCotacao='MM-DD-YYYY'&$format=json&$select=cotacaoCompra,cotacaoVenda,dataHoraCotacao` | **HTTP 200.** JSON `{"value":[{cotacaoCompra, cotacaoVenda, dataHoraCotacao}]}`. 20 filas para abril-2026: **una por día hábil, sin fines de semana ni feriados** (faltan 03/04 y 21/04). Fecha en formato **MM-DD-YYYY**. Valores con 4–5 decimales (venta ≈ compra + 0,0006). |
| MEP (argentinadatos) | `https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa` | **HTTP 200.** Array de `{casa:"bolsa", compra, venta, fecha}`: **2.914 filas desde 2018-10-29 hasta 2026-10-20**, 293 en 2026 → **una por día calendario**, con fines de semana ya rellenados (valor repetido). Última venta 1.544,1. |

Conclusiones: (1) la regla "fin de semana → último día hábil" aplica solo a PTAX; para MEP la API ya lo resuelve. (2) No hay clave ni autenticación: bien. (3) Falta decidir **compra, venta o promedio** para MEP (la spec solo dice "PTAX venta"). (4) Una sola descarga trae toda la serie MEP: cachear en `exp_fx_rates` al primer uso, no por fila. (5) Dependencia externa sin SLA ni contrato: ya está bien previsto "fuente en constante" + carga manual; agregar un test con respuesta grabada. (6) Hay una discrepancia con el dato de la propia cuenta: el TC de los pagos de tarjeta (1.405–1.490) es el tipo de cambio de **Santander para pagar el saldo en USD**, no MEP; no mezclarlos.

---

## 2. PLAN DE IMPLEMENTACIÓN

Esfuerzo relativo: **S** ≈ ½–1 día · **M** ≈ 2–3 días · **L** ≈ 4–7 días (de trabajo concentrado). Riesgo: 🟢 bajo · 🟡 medio · 🔴 alto.

### T-00 (nuevo, no está en la spec) — Higiene y andamiaje · **S** · 🟢
Debe ir **antes** de cualquier cosa de la spec.
1. `.gitignore`: `docs/expenses/`, `backend/app/expenses/seed/*.local.json`, `backend/tests/expenses/real_golden*.json` (y, opcional, `exports/`).
2. **Depurar `modulo-gastos.txt`**: reemplazar nombres reales por placeholders (D-02).
3. Bootstrapear tests: `backend/requirements-dev.txt` (pytest), `backend/tests/__init__.py`, `conftest.py` con sesión SQLite en memoria y fixture de skip para archivos reales.
4. Fijar comandos reales de verificación (los de CLAUDE.md no existen): `cd frontend && bun run build && bun run lint`; `cd backend && python -m pytest`.
5. Commit **por ruta explícita** (nunca `git add .`); no incluir los 7 archivos de Simulación ni `specs/pending/SPEC_simulation_fixes.md`.
Dependencias: ninguna. Archivos: `.gitignore`, `specs/pending/modulo-gastos.txt`, `backend/requirements-dev.txt`, `backend/tests/*`.

### T-01 — Modelo de datos · **M** · 🟡
Pasos:
1. Decidir D-01 (misma DB vs DB separada). Plan base asume **DB separada** (`expenses_investment.db`, `Base` propia); la variante "misma DB" se indica entre paréntesis.
2. `backend/app/expenses/__init__.py`, `db.py` (engines real/demo, `ExpBase`, `get_exp_db` con la misma lógica `X-Env`) *(misma DB: usar `app.database.Base`/`get_db`)*.
3. `expenses/models/`: `entity.py`, `account.py`, `import_batch.py`, `category.py`, `transaction.py`, `rule.py`, `link.py`, `fx_rate.py`. Constraints: `UNIQUE(account_id, file_hash)`, `UNIQUE(dedup_hash)`. Usar centavos enteros o `Numeric` para `amount` (ver §3.4).
4. `expenses/seed/` : `entities.py`, `categories.py` (idempotente por `code`/`name`), `rules.example.json` (+ cargador de `rules.local.json`).
5. Cablear en `main.py`: `create_all` para ambos engines + `include_router` (aunque vacío) + hook de migraciones `expenses/migrations.py`.
6. Test: arranque con ambas DB vacías crea tablas; seed idempotente; test de arquitectura (grep/AST) que falla si algo fuera de `expenses/` importa `app.expenses` o si algo en `expenses/` fuera de `services/linking.py` importa `app.models`.
Archivos nuevos: ~12. Modificados: `main.py` (+`database.py` si misma DB).
Dependencias: T-00.

### T-06 — Tipos de cambio · **S** · 🟢  (en paralelo con T-02)
1. `expenses/services/fx.py`: constantes de fuente, `fetch_ptax(from,to)`, `fetch_mep()`, cache en `exp_fx_rates`, `get_rate(pair, date)` con *forward fill* (PTAX) y `fx_estimated` si se usa valor viejo.
2. `convert(amount, currency, date) -> (amount_brl, amount_usd, fx_usd_brl, fx_ars_usd, estimated)`.
3. Tests con respuestas grabadas (los dos endpoints ya verificados) y caso "API caída".
4. `POST /api/expenses/fx/recompute?from&to`, `PUT /api/expenses/fx/rates` (manual).
Dependencias: T-01.

### T-02 — Parsers · **L** (dividir en sub-PRs) · 🔴 (PDFs)
Orden y esfuerzo por parser:
| Sub-tarea | Esfuerzo | Riesgo | Notas |
|---|---|---|---|
| 2.0 `parsers/base.py` (`StatementParser`, `ParsedStatement`, `ParsedRow`, `Check`), `numbers.py` (`parse_br_number` local, `parse_ar_number`, soporta `R$`, `-R$`, `$ -`, signo final, `Decimal`), `detect.py` (registro) | S | 🟢 | Hacer *antes* los fixtures sintéticos. |
| 2.1 `xp_card_csv` | S | 🟢 | Formato más simple y mejor cubierto de ACs. |
| 2.2 `inter_account_csv` | S | 🟢 | No asumir orden; extraer `Cp`. |
| 2.3 `xp_account_csv` | M | 🟡 | Reconstrucción de orden por saldos (§1.5-A). |
| 2.4 `mercadopago_pdf` | M | 🟡 | Agrupación por coordenadas; validado 8/8 con parser rápido. |
| 2.5 `santander_ar_account_pdf` | L | 🔴 | Fecha centrada verticalmente, intercalados, 2 columnas, secciones ARS/USD. |
| 2.6 `santander_ar_card_pdf` | L | 🔴 | USD, cuotas, pagos múltiples con TC, año arrastrado, meses `Setiem.`/`Noviem.`. |
Cada parser: fixture **sintético** commiteado (generado a mano, importes inventados; para PDF, generar un PDF mínimo con `reportlab`/`fpdf` o testear sobre un "texto/palabras con coordenadas" serializado) + test contra archivo real con `skip` si no existe.
Dependencias: T-00, T-01 (sólo para `ParsedRow` estable; los parsers no tocan DB).

### T-03 — Flujo de importación · **M** · 🟡
1. `expenses/services/importer.py`: `detect → parse → validar → dedup → fx → clasificar → proponer vínculos`.
2. Staging: **JSON en `exp_import_batches.preview_rows`** (columna nueva respecto de la spec).
3. `routers/imports.py`: `POST /imports` (multipart), `POST /imports/{id}/confirm` (con `force`), `DELETE /imports/{id}`, `GET /imports`. 409 por `(account_id, file_hash)`.
4. Dedup según §3.4. Sanear `file_name` antes de persistir.
5. Tests: re-importar → 409; solape XP; borrar lote borra exactamente sus filas y sus vínculos.
Dependencias: T-02 (≥1 parser), T-01, T-06 (para convertir).

### T-04 — Clasificación · **M** · 🟡
1. `services/classifier.py`: normalización de comercio (lista de prefijos/sufijos como datos, no código), identificadores propios, reglas por prioridad, default.
2. `services/rules.py`: preview de impacto, "crear regla desde corrección", protección de `manual`.
3. Seed: `rules.example.json` + cargador `rules.local.json`. Agregar las reglas faltantes (§1.3).
4. Endpoints: `PATCH/POST bulk` (de T-07) + `POST /rules/preview`.
5. Tests: reglas nunca pisan manual; crear regla reclasifica sólo `needs_review` matcheables; métrica de cobertura como test opcional (skip sin datos reales).
Dependencias: T-03 (o en paralelo con T-03 usando filas parseadas).

### T-05 — Conciliación · **L** · 🔴
Dividir en **A+B (internos)** y **C+D+E (inversiones)**:
- **5.1 Pares own_transfer (A)** · M · 🟢. Indexar por (monto, moneda), ventana ±2 días, único → confirmed.
- **5.2 Tarjeta ↔ resumen (B)** · M-L · 🔴. Implementar *cobertura por tarjeta×mes* (§3.3), vínculo por SU PAGO del resumen N+1 (Argentina) y por total exacto (Brasil, ya verificado), pagos múltiples, resumen sin pago, pago sin resumen.
- **5.3 Inversiones y proventos (C+D)** · L · 🟡. Join con `Transaction`/`Instrument`/`ProvéntoItem`; N:M con `amount_allocated_brl`; score.
- **5.4 Auditoría (E)** · M · 🟡. Solo lectura.
Cada sub-tarea con *tests sobre fixtures sintéticos de inversiones* (no la base real).
Dependencias: T-03 (+T-04 para kinds).

### T-07 — Consulta y edición · **M** · 🟡
1. `services/summary.py`: una sola fuente de verdad para "qué entra en gasto" (lista de kinds + regla de cobertura de tarjetas), reutilizada por `/summary`, `/transactions` y la cola de revisión.
2. Routers: `summary`, `transactions` (+PATCH/bulk), `review-queue`, `installments/upcoming`, `links/*`, CRUD `accounts/categories/entities/rules`.
3. Test de invariantes (§1.4) y de cobertura de meses.
Dependencias: T-04, T-05, T-06.

### T-08 — Frontend · **L** · 🟡
1. `api/expenses.ts`; `pages/expenses/GastosPage.tsx` con tabs por `?tab=`.
2. Tabs: Resumen (KPIs, barras apiladas, tabla, cuotas), Movimientos, Revisar, Importar (wizard), Configuración.
3. `components/expenses/*`: `Combobox` genérico, tablas, modales. Ruta en `App.tsx`; ítem en `Sidebar.tsx`.
4. Indicador de **cobertura** por cuenta × mes en Resumen.
Dependencias: T-07 (puede arrancar con mocks tras T-03).

### T-09 — Demo · **S** · 🟢
Datos ficticios para la DB demo de gastos. Con DB separada, un script `expenses/seed/demo.py` independiente de `create_demo_db.py` (que **no** debe tocarse); con misma DB, extender `create_demo_db.py` y verificar que `get_demo_schema` no arrastre filas reales de `exp_*`.
Dependencias: T-01, T-07.

### T-10 — Carga real · **M** · 🟡
Crear cuentas desde la UI/script local, importar todo `docs/expenses/`, medir % clasificado y cola por motivo, generar *golden* local. Reportar sin identificadores.
Dependencias: todo.

### Cortes en PR/commits independientes y testeables

| PR | Contenido | Verificación | Esfuerzo |
|---|---|---|---|
| **PR-0** | T-00: `.gitignore`, spec depurada, pytest | `git status` limpio de `docs/expenses/`; `pytest` corre | S |
| **PR-1** | T-01 + T-06 (modelos, wiring ambos entornos, seeds, FX) | Tablas en real y demo; tests de seed, FX con grabaciones; test de arquitectura | M |
| **PR-2** | T-02 parte CSV (2.0–2.3) | Parsers vs fixtures + archivos reales (skip) | M |
| **PR-3** | T-03 + T-04 (import + clasificador) sólo BR, por API | Escenarios 409 / solape / borrar lote; cobertura medida | M |
| **PR-4** | T-05.1–5.2 (pares y tarjetas BR) + T-07 (`summary`, `transactions`, `review-queue`) | Invariantes; faturas 8/8; pares 20 y 16 | M-L |
| **PR-5** | T-08 v0 (Importar, Movimientos, Resumen) | Build, demo y real | M-L |
| **PR-6** | MercadoPago PDF (2.4) + reglas | 8/8 checks | M |
| **PR-7** | Santander cuenta PDF (2.5) | Saldo por sección | L |
| **PR-8** | Santander tarjetas PDF (2.6) + conciliación AR (5.2 AR) | Resúmenes 15/15 vs DEBITAREMOS | L |
| **PR-9** | T-05.3–5.4 (inversiones/proventos/auditoría) + tab Revisar | Fixtures sintéticos | L |
| **PR-10** | T-09, T-10, `CONTEXT-expenses.md` + sección en `CONTEXT.md`, spec → `specs/done/`, aviso Slack (memoria del usuario) | Checklist PASO FINAL | M |

Cada PR deja la app usable: PR-5 ya entrega valor (BR completo) sin esperar los PDFs.

---

## 3. CRÍTICA Y ALTERNATIVAS

### 3.1 ¿El límite del módulo es suficiente o excesivo?

**Lo bueno:** paquete propio + prefijo `exp_` + solo `linking.py` lee inversiones es barato, mantiene el acoplamiento unidireccional y facilita borrar el módulo. **No es excesivo.**

**Lo que le falta (riesgos reales, no de código sino de datos):**
1. **Misma archivo SQLite = mismo radio de daño.** Investments y gastos compartirían `investment_tracker.db`. Consecuencias:
   - **Privacidad**: los *backups manuales* (`investment_tracker.backup-*.db` ya existen) y `copy`s a demo incluirían movimientos bancarios, nombres de terceros y `owner_identifiers` (CBU/CUIT). Sacar el módulo = `DROP` de 10 tablas en la base de inversiones.
   - **Locking**: SQLite es *single-writer*; un import largo (FX por HTTP dentro de la transacción) puede bloquear escrituras de inversiones.
   - **`create_demo_db.py`** copia el esquema desde la base real: arrastra `exp_*` (vacías, pero acopla).
   - **Migraciones**: cualquier fallo en `exp_*` en `startup()` impide levantar el backend de inversiones.
2. **Los extractos tienen identificadores en nombres de archivo y cabeceras** (nº de cuenta, CUIT, CBU, nº de cuenta Inter). Hay que prohibir que lleguen a `file_name`, `validation` JSON, logs y mensajes de error. Un test específico (grep del resultado serializado contra un patrón de ≥8 dígitos) lo hace cumplir.
3. **Falta un test de arquitectura** que haga cumplir la regla (§2, T-01 paso 6); sin él, el límite se erosiona al primer apuro.
4. **Tests con importes reales commiteados** (14.961,54; 192.618,87; …) son datos financieros personales. Mantener los esperados reales en un `*.local.json` gitignored y commitear solo sintéticos.

**Alternativa recomendada (barata):** `ExpBase` y **un archivo SQLite aparte** (`expenses.db` / `expenses_demo.db`), con su propio `get_exp_db` con la misma lógica `X-Env`. Como `exp_links` ya prescinde de FKs hacia inversiones, **no se pierde ninguna capacidad**; `linking.py` abre dos sesiones (la de gastos y la de inversiones). Costo: ~1 archivo extra y dos engines más (S). Beneficios: aislamiento total de backups/privacidad/locks/migraciones, borrar el módulo = borrar un archivo, `create_demo_db.py` queda intacto. Si Nico prefiere un único archivo por simplicidad, el resto del plan sigue valiendo (D-01).

### 3.2 `exp_links` genérica vs tablas específicas

La tabla genérica es **razonable para los vínculos hacia afuera** (inversiones/proventos) porque (a) sin FK es la única forma de respetar el límite, (b) el N:M con `amount_allocated_brl` es el mismo patrón en ambos casos. Debilidades:
- **Huérfanos y deriva silenciosa**: `target_id` apunta a `transactions.id`; otras features de inversiones borran/recrean filas (p. ej. commits recientes "registrar saldo inicial como transacción", "recalcular MonthlyPosition"). Un vínculo confirmado puede apuntar a otra cosa mañana. Mitigar guardando en el vínculo un **snapshot** (`target_date`, `target_amount`, `target_label`) y chequeándolo en la auditoría.
- **Mezcla de semánticas**: `own_transfer_pair` (simétrico exp↔exp) y `card_statement` (exp→batch) son relaciones *internas* con integridad verificable y ruta caliente: el `summary` debe decidir en cada consulta si una `card_payment` está "cubierta". Hacerlo con joins sobre una tabla genérica `target_type` es más lento y más difícil de testear.
- **Par simétrico**: ¿se guarda una fila o dos? La spec no lo dice; si se guarda una por sentido, hay doble conteo al contar "pares".

**Propuesta:** dejar `exp_links` solo para `investment` y `provento` (externos, N:M) y modelar lo interno con columnas directas: `exp_transactions.transfer_group_id` (UUID/ int compartido por el par) y `exp_transactions.statement_batch_id` (FK a `exp_import_batches` en `card_payment`). Es más simple, se indexa, y permite constraints. (D-05.)

### 3.3 "Tarjeta sin detalle" y doble conteo

Contar el pago de tarjetas sin extracto como gasto **es necesario** (si no, el gasto desaparece) pero la regla de la spec es frágil:
1. **Falla "abierta"**: hoy el pago se excluye *sólo si* existe un vínculo confirmado a un lote. Si el vínculo falla (Argentina por USD×TC, pagos parciales múltiples, pago tardío, TC distinto) el pago se cuenta como "Tarjeta sin detalle" **y** los consumos del resumen se cuentan también → **doble conteo**. Peor, silencioso.
2. **Borde de inicio**: el primer pago del rango (XP, ene: R$ 4.899,71) corresponde a una fatura anterior no importada; contado como "sin detalle" imputa consumo de diciembre a enero (correcto como caja, pero debe verse).
3. **Cargos dentro del pago**: los pagos de tarjeta pueden incluir intereses/multas (XP mar: R$ 14.961,54 incluyen R$ 413,18 de cargos) — en una tarjeta sin resumen quedan en "Tarjeta sin detalle" en vez de "Cargos financieros".

**Regla propuesta (por cobertura, no por vínculo):**
- Para cada `(tarjeta, mes de vencimiento)`: si existe un lote confirmado con `statement_period` de ese mes → **todos** los `card_payment` de la cuenta pagadora cuyo `date` esté en la ventana [vencimiento − 5 días, vencimiento + 31 días] del mes se **excluyen**, haya o no vínculo exacto.
- Si no hay lote → se cuentan como "Tarjeta sin detalle".
- Si un pago queda en la ventana de dos tarjetas/meses → cola de revisión.
- Mostrar "Tarjeta sin detalle" con color/etiqueta distintiva ("estimado, sin categoría") en gráficos, y la **cobertura** por tarjeta×mes.
- Invariante testeable: para cada (tarjeta, mes) cubierto, Σ gastos del lote + Σ pagos excluidos de ese mes ≠ doble conteo (es decir, ningún `card_payment` cubierto aporta al total).
Esto convierte un fallo de matching en una advertencia de revisión en vez de un doble conteo.

### 3.4 Regla de dedup (hash + ordinal)

Funciona en el caso real documentado (las 14 EASYJET de R$ 10,00 son filas idénticas dentro de **un** archivo, ordinales 0–13). Casos donde **falla o es frágil**:
1. **Archivos superpuestos con corte a mitad de día**: A tiene las 3 primeras de 5 filas idénticas del día; B (exportado después) tiene las 5. Ordinales 0–2 coinciden (dupes) y 3–4 son nuevas: ✔. El caso inverso (B más corto que A en ese día) también deja consistente. El problema aparece cuando **el orden relativo de filas idénticas entre archivos cambia** (XP: empates de segundo en orden distinto) — sólo afecta cuál ordinal recibe cada fila, no el conteo; inofensivo para filas totalmente idénticas, **dañino si difieren en un campo fuera del hash** (p. ej. `balance_after`/hora, que la spec excluye del hash).
2. **Descripciones que cambian entre exports** (el banco "enriquece" la descripción, o cambia el formato entre PDF y CSV): hash distinto → duplicado silencioso. No hay red de seguridad (ni ventana difusa) en la spec.
3. **Filas borradas/editadas a mano y reimportadas**: reaparecen (no hay "tombstones").
4. **Float en el hash**: `amount` como `Float` produce strings distintas (`10.0` vs `10.00`). Usar **centavos enteros** (o `Decimal` normalizado) para hash y sumas.
5. **Colisión con `UNIQUE(dedup_hash)` global**: dos cuentas distintas no colisionan (account_id en el hash) ✔, pero dos filas legítimas idénticas en archivos **no superpuestos** distintos sí comparten hash (ambas con ordinal 0) → la segunda se descartaría como duplicada. Ej.: dos pagos idénticos del mismo día cortados por la frontera de dos exports contiguos. Para Inter/XP el riesgo es bajo pero real.
6. **Tarjetas**: dos facturas distintas con la misma compra en cuotas son filas distintas por `statement_period` ✔.

**Mejora propuesta:** usar **clave natural cuando exista** (`external_id`: comprobante Santander / ID de operación MP; se ve ≥ 95% de las filas de PDF) con *fallback* a `hash + ordinal` sólo si no hay `external_id`; incluir la hora (XP) en el hash cuando exista; asignar ordinales sobre el orden **canónico** ya reconstruido; normalizar a centavos; y que el preview marque "dudoso" cuando una fila tenga mismo (cuenta, fecha, monto) que una existente pero distinta descripción. (D-06.)

### 3.5 ¿Alcance v1 demasiado grande? — Sí; propongo v0 y escalones

Datos medidos con los archivos reales que respaldan el recorte:
- **Reglas de la spec sobre Brasil:** XP 89% de filas (96% por monto), Inter 100% (113/113), **tarjeta XP solo 14% de filas (51% por monto)** — la clasificación de comercios de tarjeta es el grueso del trabajo manual, no los extractos de cuenta.
- **4 de los 6 parsers son PDFs argentinos**, y los 2 PDF de Santander son los de mayor riesgo (fecha centrada, USD, TC con pagos múltiples).
- Los extractos argentinos **terminan en jun/jul**; Brasil llega a sep. Para los ACs de "ene–sep", Brasil ya cierra solo.
- Mercado Pago PDF es la excepción fácil (8/8 cierran con parser rápido).

**Propuesta de escalones:**
- **v0 (PR-0..PR-5):** T-00, T-01 (sin `parent_id`, sin `hits`), T-06 (PTAX + MEP), parsers `xp_card_csv`, `inter_account_csv`, `xp_account_csv`; import con preview/confirm/delete; dedup; clasificador con reglas desde JSON (sin UI de reglas: se editan por archivo/endpoints); vínculos internos BR (pares + faturas XP); `summary` + `transactions` + `review-queue` básica; UI: Importar, Movimientos (edición inline simple), Resumen (KPIs + barras). Sin tabs Configuración/Revisar elaboradas ni bulk. **Entrega gasto real BR de ene–sep.**
- **v0.5:** MP PDF; cuenta Santander PDF; reglas AR; tab Revisar.
- **v1:** tarjetas Santander PDF + conciliación AR; inversiones/proventos/auditoría (T-05 C–E); Configuración completa; demo; instalaciones.
- **Antes de invertir en PDF de Santander:** averiguar si el home banking permite exportar **CSV/XLS** de movimientos y de resúmenes de tarjeta. Si sí, se evita el 40–50% del esfuerzo de parsers (hipótesis no verificada acá; dependería del home banking).

### 3.6 Tipos de cambio (PTAX / MEP)

- Ambos endpoints existen y responden (§1.6). **Cambios sugeridos:** (a) MEP: definir *venta* (o promedio) como convención, (b) FX en una sola descarga y cache (la serie completa son 2.914 filas), (c) `fx_estimated` separado de `needs_review`, (d) no usar el TC de los pagos de tarjeta como proxy de MEP, (e) test con respuestas grabadas y un modo "offline" (sin red) en CI.
- PTAX sin feriados BR: usar el último día hábil previo (ya previsto).
- **Riesgo de dependencia:** `argentinadatos.com` es un proyecto comunitario; tener la carga manual y la constante de fuente es suficiente para v1.

### 3.7 Lo que me parece sobrediseñado (o prematuro)

| Elemento | Opinión | Alternativa |
|---|---|---|
| `exp_categories.parent_id` | No se usa en ningún lado (la lista seed es plana). | Quitarlo hasta que haya jerarquía. |
| `exp_rules.hits`, `origin` | `hits` es telemetría sin consumidor; `origin` sí sirve para el re-seed. | Dejar `origin`, quitar `hits`. |
| `exp_fx_rates` PK `(date,pair)` con `source` | OK. | — |
| Tab **Configuración** completa (reglas con drag, cuentas con `owner_identifiers`, TC manual) | Mucho UI de bajo uso; el titular tipea reglas poco. | v0: reglas por archivo/endpoint; cuentas y TC manuales por formulario simple. |
| "Crear regla" con **preview del impacto** + reclasificación masiva | Valioso pero L. | v0: crear regla = reclasifica las `needs_review` que matchean (ya definido) sin preview; el preview llega en v1. |
| `POST /links/rebuild` | Útil, pero requiere idempotencia estricta. | Ejecutar al confirmar; `rebuild` en v1. |
| `GET /installments/upcoming` | Es el único "dato para v2" que entra en v1; añade un endpoint, una query y un bloque de UI. | Diferir a v1.1 (el dato `n/N` ya queda guardado). |
| `fx_conversion` como kind separado | Útil; pero el único caso observado es LIQ. CAMBIO. | Mantener, pero definir su tratamiento (§1.5-G). |
| Kinds: 10 valores | Razonable. | — |
| `classification_source` de 4 valores + `rule_id` | Justifica la regla "nunca pisar manual". | Mantener. |
| 2 archivos de documentación (`CONTEXT-expenses.md` + `CONTEXT.md`) | Conflicto con CLAUDE.md (§1.2-2). | Resolver como se propone. |

Lo que **no** es sobrediseño y hay que conservar: validación de saldo corrido por parser, `file_hash` + preview/confirm, `kind`/regla de signos, rule-engine con `manual` inviolable, la regla de cobertura de tarjeta, y la exclusión explícita de transferencias/inversiones del gasto.

---

## 4. DECISIONES QUE NECESITO DE NICO

Marcadas con mi recomendación. Las primeras bloquean el arranque.

| ID | Decisión | Opciones | Recomendación |
|---|---|---|---|
| **D-01** | **¿Dónde viven las tablas `exp_*`?** | (a) misma DB de inversiones; (b) archivo SQLite aparte (real+demo) con `Base` propia | **(b)**: aísla backups/privacidad/locks/migraciones; el plan casi no cambia (§3.1). |
| **D-02** | **El spec actual contiene nombres de terceros** y el paso 0.3 lo commitea. ¿Lo depuro (placeholders) y dejo las reglas reales sólo en `rules.local.json`? | Sí / No / Lo commiteo tal cual | **Sí, depurar antes de commitear.** Ya está contradicho por la decisión 7. |
| **D-03** | **Alcance:** ¿v0 (BR + CSV) → v0.5 (MP, cuenta Santander) → v1 (tarjetas AR, inversiones)? ¿o todo v1 junto? | Escalonado / Todo junto | **Escalonado** (§3.5). |
| **D-04** | **Conciliación de tarjetas por cobertura** (tarjeta × mes con resumen → se excluyen los pagos de ese mes aunque no haya vínculo exacto) en lugar de por vínculo. | Cobertura / Vínculo | **Cobertura** (§3.3). |
| **D-05** | **Vínculos internos (pares y fatura) como columnas directas** (`transfer_group_id`, `statement_batch_id`); `exp_links` sólo para inversión/provento. | Directas / Todo en `exp_links` | **Directas** (§3.2). |
| **D-06** | **Dedup:** clave natural `external_id` cuando exista + hash/ordinal de respaldo; centavos enteros; hora en el hash si existe. | Spec actual / Propuesta | **Propuesta** (§3.4). |
| **D-07** | **Pago de tarjeta Argentina en pesos + USD×TC:** ¿se concilia el débito en cuenta con la línea `SU PAGO` del resumen siguiente? | Sí / Otra | **Sí**; y se guarda el importe en pesos de la primera columna (§1.5-F). |
| **D-08** | **T-05 #4 (LIQ. CAMBIO + IOF):** ¿lo reformulamos como `rescate ↔ Pix recibido de cuenta propia` y las filas de cambio como `fx_conversion` + IOF como gasto (con destino XP US fuera del sistema)? ¿Las salidas a XP US cuentan como aporte a inversiones? | Reformular / Mantener | **Reformular**. Necesito saber cómo querés ver ese flujo. |
| **D-09** | **Mercado Pago "Dinero reservado/retirado"**: ¿son reservas internas (→ `own_transfer`)? | Sí / No | Sí (105 filas). |
| **D-10** | **`TED recebida de <titular>`**, **AUTOPASS (peajes)**, **comercios de tarjeta** (aéreas, supermercado, ropa): ¿agrego las reglas al seed local? ¿qué categoría para viajes/aéreas ya que son R$ 50k+? | Sí / No | Sí, con categoría "Viajes". |
| **D-11** | **Provento vs ingreso para "Nota de Aluguel"** (centavos de comisión de aluguel de acciones): ¿provento o `income/Rendimientos`? | provento / income | `income/Rendimientos`. |
| **D-12** | **Paso 0.1** ("pasos de setup de CLAUDE.md (ClickUp/TASKS.md)"): CLAUDE.md no los define y `TASKS.md` existente es de otra tarea. ¿Crear lista/tareas en ClickUp? ¿pisar `TASKS.md`? | ClickUp / `TASKS.md` nuevo / Ninguno | Aclarar; mi default: **no tocar `TASKS.md`** y listar tareas en el PR. |
| **D-13** | **Comandos de verificación:** `bun run typecheck/test/lint` no existen. ¿Los creo (package.json raíz) o uso `cd frontend && bun run build/lint` y `cd backend && pytest` (PR-0)? | Crear / Usar los reales | **Usar los reales** + `pytest`. |
| **D-14** | **`parse_br_number`**: ¿copiar a `expenses/parsers/numbers.py` (sin tocar inversiones) o mover a `app/utils` (toca `proventos_importer.py`)? | Copiar / Mover | **Copiar**. |
| **D-15** | **Moneda de referencia del MEP**: ¿compra, venta o promedio? | compra/venta/promedio | **Venta**. |
| **D-16** | **Cobertura temporal**: Argentina termina en jun/jul; ¿mostramos los meses sin extracto como "sin datos" (no como 0)? | Sí / No | **Sí**. |
| **D-17** | **Metas de clasificación**: ¿aceptás medir ≥90% **por filas y por monto**, con holdout (reglas con ene–jun, medir jul–sep), y no sólo sobre los datos con los que se escribieron las reglas? | Sí / No | **Sí**. |
| **D-18** | **Privacidad operativa:** ¿ok con (i) no persistir el nombre de archivo original (usar hash + etiqueta), (ii) tests de golden sólo locales gitignored, (iii) agregar `exports/` al `.gitignore`? | Sí / No | **Sí** a las tres. |
| **D-19** | **Preguntas abiertas de datos:** (1) ¿la fatura XP de sep (vence 20/09) ya está paga en la cuenta XP? (no hay pago de sep en los datos que revisé); (2) VIVO/Telefónica: ¿entidad Bertioga o Personal? (ya figura como pendiente en la spec); (3) ¿hay extractos de la tarjeta Inter para evitar "Tarjeta sin detalle"? | — | Para T-10. |

---

### Qué hice y no hice
- Hice: lectura de la spec, `CONTEXT.md`, `CLAUDE.md`, código listado, apertura de **todos** los archivos de `docs/expenses/` (CSV completos; PDFs: texto de las 6 cuentas Santander, 8 MP, 15 resúmenes de tarjeta) y verificación de los endpoints de FX en vivo.
- Scripts de apoyo: sólo en el scratchpad de sesión (fuera del repo); las consultas a la DB de inversiones se hicieron sobre una **copia** de solo lectura.
- No hice: ningún cambio en `backend/`, `frontend/`, `.gitignore`, ni commits; no toqué los 7 archivos modificados de Simulación.
