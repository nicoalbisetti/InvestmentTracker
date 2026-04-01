InvestmentTracker
Sistema Web de Seguimiento de Inversiones

Documento de Requisitos Funcionales y Tecnicos
Para Claude Code

Version 1.0  |  Marzo 2026

# 1. Vision General del Proyecto

InvestmentTracker es un sistema web completo para el seguimiento y analisis de carteras de inversion personal. Reemplaza y supera la funcionalidad de un Excel de seguimiento manual que registra datos desde enero 2015, con mas de 150 instrumentos de inversion en multiples custodios.

## 1.1 Problema que Resuelve
El Excel fuente de referencia presenta limitaciones criticas:
- Formato pivot con 150+ instrumentos como columnas — extremadamente dificil de mantener
- Sin validacion de consistencia entre hojas
- Mezcla de valores en BRL y USD sin separacion clara por moneda
- Fechas inconsistentes entre hojas (dia 1 vs dia 15 del mes)
- Instrumentos cerrados (saldo=0) siguen listados sin distincion
- Sin visualizacion de datos ni dashboards interactivos
- Sin proyecciones ni alertas automatizadas

## 1.2 Objetivo
Construir un sistema web profesional que:
- Importe y normalice los datos existentes del Excel
- Provea dashboards interactivos con graficos y metricas
- Permita el ingreso manual de nuevas operaciones
- Calcule performance, rankings y proventos automaticamente
- Sea mantenible y extensible a largo plazo

# 2. Estructura del Excel Fuente

El Excel de referencia (Inversiones.xlsx) contiene 6 hojas con la siguiente estructura y aproximadamente 5.638 filas de datos historicos desde enero 2015.

## 2.1 Hoja: Saldos
Tabla longitudinal principal. Cada fila es una posicion mensual de un instrumento en un custodio.

## 2.2 Hoja: Resumen
Pivot mensual en formato wide. Filas = fechas mensuales (290 filas), columnas = instrumentos (~150 columnas) mas columnas de totales por custodio.

Columnas de totales incluidas:
- HSBC Total, Bradesco Total, XP BR Total, XP US Total
- Santander Total, Inter Total, Brasil Total
- FGTS, PREV, Total + Prev, Total - B3
- USA Total, Dolar (cotizacion), Total Dolar, Total Dolar + Prev
- Incremento (variacion porcentual mensual del portfolio total)

## 2.3 Hoja: Totales
Resumen anual del portfolio desde 2015. Columnas:
- Ano: Primer dia del anio
- Total: Valor total del portfolio al cierre del anio
- Dif: Variacion absoluta respecto al anio anterior
- Ganancia: Rendimiento puro (excluye aplicaciones/rescates)
- Aplicaciones/Rescates: Flujo neto de capital

## 2.4 Hoja: Ranking
Performance de instrumentos activos con ranking. Para cada instrumento:
- Fondo: Nombre del instrumento
- Venc: Liquidez (D+2, D+3, D+30, etc.)
- Saldo: Valor actual en BRL
- Porc: Porcentaje del portfolio total
- Ultimo mes: Rendimiento mensual + numero de ranking
- Ultimos 3/6/12 meses: Rendimientos acumulados + rankings

## 2.5 Hoja: Cotizaciones
Serie historica mensual de tipos de cambio y precios de acciones base. Columnas: Fechas, Dolar (USD/BRL), BVMF3 (precio de referencia).

## 2.6 Hoja: Proventos
Dividendos y proventos recibidos por instrumento. Estructura:
- Fondo: Nombre del instrumento
- Saldo: Valor actual
- Proventos 2026, 2025, 2024... hasta 2020: Totales anuales
- Total: Suma historica acumulada
- Columnas mensuales: Desglose mes a mes del anio vigente

# 3. Tipos de Instrumentos en Cartera

# 4. Arquitectura Tecnica

## 4.1 Stack Tecnologico

## 4.2 Estructura de Directorios

# 5. Modelos de Base de Datos

Todos los modelos deben ser creados con SQLAlchemy ORM. La base de datos SQLite debe ser creada automaticamente al iniciar la aplicacion si no existe.

## 5.1 Instrument
Catalogo maestro de instrumentos de inversion.

## 5.2 MonthlyPosition
Posiciones mensuales historicas — datos de la hoja Saldos del Excel.

## 5.3 PortfolioSnapshot
Snapshot mensual del portfolio completo — datos de la hoja Resumen.

## 5.4 AnnualSummary
Resumen anual — datos de la hoja Totales.

## 5.5 Provento
Dividendos y proventos por instrumento y periodo.

## 5.6 Quote
Serie historica de cotizaciones — datos de la hoja Cotizaciones.

## 5.7 Transaction
Registro de transacciones manuales (aplicaciones, rescates, proventos ingresados manualmente).

# 6. Logica de Negocio

## 6.1 Calculos de Performance

## 6.2 Estados de Instrumentos
- activo: Tiene saldo > 0 en el ultimo periodo disponible
- cerrado: Tuvo saldo pero en los ultimos 3 periodos tiene saldo = 0
- sin_datos: Nunca tuvo saldo registrado (recien creado en el sistema)
Los instrumentos cerrados deben excluirse de calculos de portfolio actual pero conservarse en el historial.

## 6.3 Normalizacion de Fechas
El Excel usa inconsistentemente el dia 1 o el dia 15 del mes. El sistema debe:
- Detectar automaticamente el patron de fechas al importar
- Normalizar todas las fechas al primer dia del mes correspondiente
- Almacenar la fecha normalizada en la base de datos
- Mostrar las fechas en formato DD/MM/YYYY en la interfaz

# 7. Importador de Excel

El importador es una funcionalidad critica. Debe ser robusto, tolerante a errores y generar un reporte detallado de lo que se importo.

## 7.1 Endpoint

## 7.2 Logica de Parseo por Hoja

### Hoja Saldos
ATENCION: Los headers reales estan en la fila 0 del DataFrame (no en la fila de indices de pandas). Detectar columnas por nombre, no por posicion.
- Iterar cada fila como una MonthlyPosition
- Crear o reusar Instrument segun combinacion (Banco, Fondo)
- Normalizar fecha al primer dia del mes
- Ignorar filas donde todos los valores numericos son NaN o 0
- Registrar warnings para datos inconsistentes

### Hoja Resumen
Formato pivot — primera columna son fechas, resto son instrumentos.
- Ignorar columnas que empiezan con 'Unnamed'
- Las columnas de totales (HSBC Total, etc.) van a PortfolioSnapshot
- Las demas columnas son instrumentos — valores son saldos en BRL
- Columna 'Incremento' = variacion porcentual mensual del total

### Hoja Cotizaciones
Estructura simple: Fechas, Dolar, BVMF3. Ignorar columnas Unnamed.

### Hoja Totales
Fila 0 son los headers. Datos desde fila 1. Ultima fila 'Totales' debe ser ignorada (es un total acumulado, no un anio).

### Hoja Ranking
Headers en fila 2 del DataFrame. Datos desde fila 3. Ignorar filas NaN. Columnas: Fondo, Venc, Saldo, Porc, Ultimo mes, Ranking ult mes, Ultimos 3 meses, [rank], Ultimos 6 meses, [rank], Ultimo ano, [rank].

### Hoja Proventos
Headers en fila 2 del DataFrame. Una fila por instrumento. Columnas anuales (Proventos 2026, 2025...) y columnas mensuales del anio vigente.

## 7.3 Manejo de Duplicados
Al reimportar, el sistema debe actualizar registros existentes (upsert) en lugar de duplicar. Clave unica para MonthlyPosition: (instrument_id, date). Si ya existe ese par, actualizar todos los demas campos.

## 7.4 Reporte de Importacion
La UI debe mostrar una pantalla/modal con el resultado completo de la importacion:
- Conteo de registros importados por tipo
- Lista de warnings (datos sospechosos pero importados igualmente)
- Lista de errores (datos que no pudieron importarse)
- Boton para descargar el reporte completo en CSV

# 8. API REST Endpoints

## 8.1 Parametros de Query Comunes
- ?date_from=YYYY-MM-DD  — Filtro de fecha inicio
- ?date_to=YYYY-MM-DD    — Filtro de fecha fin
- ?custodian=XP          — Filtrar por custodio
- ?type=renta_fija       — Filtrar por tipo de instrumento
- ?currency=USD          — Filtrar por moneda
- ?page=1&limit=50       — Paginacion
- ?sort=gain_pct&order=desc — Ordenamiento

# 9. Paginas de la Interfaz Web

## 9.1 Dashboard Principal
Pantalla inicial. Debe cargarse en menos de 2 segundos con datos del ultimo periodo disponible.

- KPIs en cards (fila superior):
- Total cartera en BRL y equivalente en USD
- Variacion del mes en % y en BRL absoluto
- Variacion YTD (enero a la fecha)
- Total proventos recibidos en el anio

- Grafico de evolucion historica (area/linea):
- Serie temporal mensual del portfolio total
- Toggle para ver en BRL o en USD
- Selector de rango: 1A, 3A, 5A, Todo
- Tooltip con valor exacto al hover

- Graficos de distribucion (dos pie/donut lado a lado):
- Por clase de activo (renta fija, acciones, FIIs, fondos, USD, etc.)
- Por custodio (HSBC, Bradesco, XP, Santander, etc.)

- Mini-tabla: Top 5 y Bottom 5 del mes por rendimiento

## 9.2 Posiciones Actuales
Replica y mejora la hoja Ranking del Excel.

- Tabla con columnas: Instrumento, Custodio, Tipo, Saldo BRL, % del total, 1M%, 3M%, 6M%, 12M%, Rank 1M
- Ordenable por cualquier columna (click en header)
- Filtros: por custodio, tipo de activo, moneda, estado (activo/cerrado)
- Color coding automatico: verde para rendimiento positivo, rojo para negativo
- Columna Vencimiento para renta fija (con alert si vence en <90 dias)
- Boton Exportar CSV con los datos filtrados actualmente
- Busqueda por nombre de instrumento

## 9.3 Evolucion Historica
Analisis de instrumentos individuales o comparativos.

- Selector de uno o varios instrumentos para comparar
- Grafico de lineas multi-serie con saldos mensuales
- Vista alternativa: rendimientos porcentuales (en lugar de saldos)
- Tabla de datos mensuales debajo del grafico
- Metricas calculadas: CAGR, rendimiento acumulado, volatilidad, maximo drawdown

## 9.4 Analisis Anual
Resumen por anio — replica la hoja Totales con visualizacion.

- Tabla: Anio, Saldo final, Variacion, Ganancia pura, Flujo neto de capital
- Grafico de barras apiladas: ganancia vs. aplicaciones netas por anio
- Card de metricas globales: total invertido historico, total ganado, ratio ganancia/capital

## 9.5 Proventos y Dividendos
Seguimiento de ingresos pasivos — replica la hoja Proventos.

- Tabla: Instrumento, Saldo actual, Prov 2026, 2025, 2024, 2023, 2022, Total historico
- Grafico de barras mensual: total de proventos por mes del anio actual
- Proyeccion anual basada en promedio de los ultimos 12 meses
- Comparativa YTD vs. mismo periodo del anio anterior
- Desglose por tipo: dividendos de acciones, rendimientos de FIIs, JCP, amortizaciones

## 9.6 Transacciones
Ingreso manual de operaciones.

- Formulario: Instrumento (autocomplete), Fecha, Tipo, Monto BRL, Monto USD (opcional), Notas
- Lista de transacciones con filtros por fecha/instrumento/tipo
- Paginacion (50 por pagina)
- Editar y eliminar transacciones

## 9.7 Configuracion

- Catalogo de instrumentos: ver, editar tipo/custodio/vencimiento de cada instrumento
- Panel de importacion: arrastrar y soltar nuevo Excel, ver historial de importaciones
- Cotizacion USD/BRL: ingreso manual del tipo de cambio del mes actual
- Toggle de tema claro/oscuro

# 10. Requisitos de UX/UI

## 10.1 Idioma y Formatos

## 10.2 Experiencia de Usuario
- Loading states en todas las queries asincronas (skeleton loaders, no spinners genericos)
- Error boundaries con mensajes claros y boton de reintentar
- Tooltips en metricas con explicacion del calculo
- Responsive design: funcional en mobile, optimo en desktop (1280px+)
- Tema dark/light con toggle en el header
- Navegacion lateral colapsable con iconos y labels
- Breadcrumbs en paginas internas

## 10.3 Performance
- Dashboard principal debe cargar en < 2 segundos
- Paginacion server-side para tablas con > 100 filas
- Caching de calculos pesados (ranking, CAGR) con invalidacion al importar
- Exportacion CSV asincrona con indicador de progreso

# 11. Issues Criticos del Excel a Resolver

El sistema debe corregir activamente estos problemas del Excel fuente. No son opcionales.

# 12. Entregables Requeridos

- Sistema completamente funcional con backend FastAPI y frontend React
- Script seed_data.py que genere al menos 24 meses de datos de prueba realistas
- Script de importacion compatible con el archivo Inversiones.xlsx
- README.md con instrucciones claras de instalacion y primer uso
- Script start.sh (o instrucciones equivalentes) para levantar el sistema en un comando
- docker-compose.yml opcional pero valorado

## 12.1 Criterios de Aceptacion
- El sistema puede importar el Excel de referencia sin errores criticos
- El Dashboard muestra datos coherentes con el Excel importado
- La tabla de Posiciones Actuales muestra los mismos instrumentos que la hoja Ranking
- Los totales anuales coinciden con la hoja Totales dentro de un margen del 0.1%
- La interfaz es navegable en un navegador moderno sin errores en consola
- Se puede agregar una transaccion manual y ver su efecto en el portfolio

InvestmentTracker — Documento de Requisitos v1.0  |  Marzo 2026
