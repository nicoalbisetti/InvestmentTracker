import { useEffect, useRef, useState } from 'react';
import { getInstruments, updateInstrument } from '../api/instruments';
import { importExcel, getImportHistory, getImportDetail } from '../api/import';
import Modal from '../components/ui/Modal';
import { INSTRUMENT_TYPE_LABELS } from '../utils/formatters';
import client from '../api/client';

const TYPE_OPTIONS = Object.entries(INSTRUMENT_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }));

type SortKey = 'name' | 'ticker' | 'custodian' | 'type' | 'status' | 'maturity_date';

function InstrumentCatalog() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [currencyFilter, setCurrencyFilter] = useState('');
  const [custodianFilter, setCustodianFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [noMaturity, setNoMaturity] = useState(false);
  const [sort, setSort] = useState<SortKey>('name');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [saving, setSaving] = useState(false);

  const load = () => {
    getInstruments({
      search: search || undefined,
      type: typeFilter || undefined,
      location: locationFilter || undefined,
      currency: currencyFilter || undefined,
      custodian: custodianFilter || undefined,
      status: statusFilter || undefined,
      no_maturity: noMaturity || undefined,
      sort,
      order,
      page,
      limit: 50,
    }).then(setData);
  };

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [search, typeFilter, locationFilter, currencyFilter, custodianFilter, statusFilter, noMaturity, sort, order, page]);

  const handleSort = (key: SortKey) => {
    if (sort === key) {
      setOrder(o => o === 'asc' ? 'desc' : 'asc');
    } else {
      setSort(key);
      setOrder('asc');
    }
    setPage(1);
  };

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sort !== col) return <span className="text-slate-300 dark:text-slate-600 ml-1">↕</span>;
    return <span className="text-indigo-500 ml-1">{order === 'asc' ? '↑' : '↓'}</span>;
  };

  const handleEdit = (inst: any) => {
    setEditing(inst);
    setForm({
      name: inst.name || '',
      custodian: inst.custodian || '',
      ticker: inst.ticker || '',
      type: inst.type || 'outro',
      location: inst.location || 'brasil',
      currency: inst.currency || 'BRL',
      status: inst.status || 'activo',
      liquidity: inst.liquidity || '',
      maturity_date: inst.maturity_date || '',
      issue_date: inst.issue_date || '',
      index_type: inst.index_type || '',
      asset_class: inst.asset_class || '',
      in_liquidation: inst.in_liquidation || false,
      pays_dividends: inst.pays_dividends || false,
    });
  };

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true);
    await updateInstrument(editing.id, {
      name: form.name || undefined,
      custodian: form.custodian || undefined,
      ticker: form.ticker || undefined,
      type: form.type || undefined,
      location: form.location || undefined,
      currency: form.currency || undefined,
      status: form.status || undefined,
      liquidity: form.liquidity || undefined,
      maturity_date: form.maturity_date || undefined,
      issue_date: form.issue_date || undefined,
      index_type: form.index_type || undefined,
      asset_class: form.asset_class || undefined,
      in_liquidation: form.in_liquidation,
      pays_dividends: form.pays_dividends,
    });
    setSaving(false);
    setEditing(null);
    load();
  };

  return (
    <div className="flex flex-col gap-3 h-[calc(100vh-160px)]">
      {/* Filter bar */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <input
          className="input w-56"
          placeholder="Buscar instrumento..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
        />
        <select
          className="input w-44"
          value={typeFilter}
          onChange={e => { setTypeFilter(e.target.value); setPage(1); }}
        >
          <option value="">Todos los tipos</option>
          {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select
          className="input w-36"
          value={locationFilter}
          onChange={e => { setLocationFilter(e.target.value); setPage(1); }}
        >
          <option value="">Todas las ubicaciones</option>
          <option value="brasil">Brasil</option>
          <option value="exterior">Exterior</option>
        </select>
        <select
          className="input w-32"
          value={currencyFilter}
          onChange={e => { setCurrencyFilter(e.target.value); setPage(1); }}
        >
          <option value="">Todas las monedas</option>
          <option value="BRL">BRL</option>
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
          <option value="ARS">ARS</option>
        </select>
        <select
          className="input w-36"
          value={custodianFilter}
          onChange={e => { setCustodianFilter(e.target.value); setPage(1); }}
        >
          <option value="">Todos los custodios</option>
          {['Allaria','BRADESCO','CITI','Deitres','FGTS','HSBC','INTER','MDQ','PORTO','PREV','SANTANDER','XP'].map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          className="input w-32"
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
        >
          <option value="">Todos los estados</option>
          <option value="activo">Activo</option>
          <option value="cerrado">Cerrado</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-400 whitespace-nowrap cursor-pointer">
          <input
            type="checkbox"
            checked={noMaturity}
            onChange={e => { setNoMaturity(e.target.checked); setPage(1); }}
            className="rounded"
          />
          Sin vencimiento
        </label>
        <span className="text-sm text-slate-400 ml-auto">{data.total} instrumentos</span>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden flex flex-col min-h-0 flex-1">
        <div className="overflow-auto flex-1">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800 sticky top-0 z-10">
              <tr>
                {([
                  { key: 'name', label: 'Instrumento' },
                  { key: 'ticker', label: 'Código' },
                  { key: 'custodian', label: 'Custodio' },
                  { key: 'type', label: 'Tipo' },
                ] as { key: SortKey; label: string }[]).map(col => (
                  <th
                    key={col.key}
                    className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase cursor-pointer hover:text-slate-700 dark:hover:text-slate-300 select-none whitespace-nowrap"
                    onClick={() => handleSort(col.key)}
                  >
                    {col.label}<SortIcon col={col.key} />
                  </th>
                ))}
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase select-none whitespace-nowrap">Ubicación</th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase select-none whitespace-nowrap">Moneda</th>
                {([
                  { key: 'status', label: 'Estado' },
                  { key: 'maturity_date', label: 'Vencimiento' },
                ] as { key: SortKey; label: string }[]).map(col => (
                  <th
                    key={col.key}
                    className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase cursor-pointer hover:text-slate-700 dark:hover:text-slate-300 select-none whitespace-nowrap"
                    onClick={() => handleSort(col.key)}
                  >
                    {col.label}<SortIcon col={col.key} />
                  </th>
                ))}
                <th className="px-3 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.items.map((inst: any) => (
                <tr key={inst.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="px-3 py-2 font-medium max-w-[200px] truncate" title={inst.name}>{inst.name}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-400">{inst.ticker || '—'}</td>
                  <td className="px-3 py-2 text-slate-500">{inst.custodian}</td>
                  <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{INSTRUMENT_TYPE_LABELS[inst.type] || inst.type}</td>
                  <td className="px-3 py-2 text-slate-500 whitespace-nowrap">
                    {inst.location === 'exterior' ? '🌎 Exterior' : '🇧🇷 Brasil'}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{inst.currency || 'BRL'}</td>
                  <td className="px-3 py-2">
                    <span className={`badge ${inst.status === 'activo' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'}`}>
                      {inst.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-slate-500 whitespace-nowrap">{inst.maturity_date || '—'}</td>
                  <td className="px-3 py-2">
                    <button className="text-indigo-500 hover:text-indigo-700 text-xs font-medium" onClick={() => handleEdit(inst)}>Editar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data.pages > 1 && (
          <div className="flex items-center gap-2 px-3 py-2 border-t border-slate-100 dark:border-slate-800 flex-shrink-0">
            <button className="btn-secondary text-xs py-1" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Ant</button>
            <span className="text-xs text-slate-500">Pág {page} de {data.pages}</span>
            <button className="btn-secondary text-xs py-1" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Sig →</button>
          </div>
        )}
      </div>

      {editing && (
        <Modal open={!!editing} onClose={() => setEditing(null)} title={`Editar: ${editing.name}`} size="lg">
          <div className="space-y-4">
            {/* Row 1: Name + Custodian */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Nombre</label>
                <input className="input" value={form.name} onChange={e => setForm((f: any) => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Custodio</label>
                <input className="input" value={form.custodian} onChange={e => setForm((f: any) => ({ ...f, custodian: e.target.value }))} />
              </div>
            </div>
            {/* Row 2: Ticker + Type */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Código (ticker)</label>
                <input className="input font-mono" placeholder="Ej: CDB325A7RYB" value={form.ticker} onChange={e => setForm((f: any) => ({ ...f, ticker: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Tipo</label>
                <select className="input" value={form.type} onChange={e => setForm((f: any) => ({ ...f, type: e.target.value }))}>
                  {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>
            {/* Row 3: Location + Currency + Status */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Ubicación</label>
                <select className="input" value={form.location || 'brasil'} onChange={e => setForm((f: any) => ({ ...f, location: e.target.value }))}>
                  <option value="brasil">Brasil</option>
                  <option value="exterior">Exterior</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Moneda</label>
                <select className="input" value={form.currency} onChange={e => setForm((f: any) => ({ ...f, currency: e.target.value }))}>
                  {['BRL', 'USD', 'EUR', 'ARS'].map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Estado</label>
                <select className="input" value={form.status} onChange={e => setForm((f: any) => ({ ...f, status: e.target.value }))}>
                  <option value="activo">Activo</option>
                  <option value="cerrado">Cerrado</option>
                  <option value="sin_datos">Sin datos</option>
                </select>
              </div>
            </div>
            {/* Row 4: Maturity + Issue date */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Vencimiento</label>
                <input type="date" className="input" value={form.maturity_date} onChange={e => setForm((f: any) => ({ ...f, maturity_date: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Emisión</label>
                <input type="date" className="input" value={form.issue_date} onChange={e => setForm((f: any) => ({ ...f, issue_date: e.target.value }))} />
              </div>
            </div>
            {/* Row 5: Index type + Asset class */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Indexador</label>
                <input className="input" placeholder="Ej: CDI, IPCA, Prefixado..." value={form.index_type} onChange={e => setForm((f: any) => ({ ...f, index_type: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Asset class</label>
                <input className="input" placeholder="Ej: CDB, CRI, CRA..." value={form.asset_class} onChange={e => setForm((f: any) => ({ ...f, asset_class: e.target.value }))} />
              </div>
            </div>
            {/* Row 6: Liquidity + checkboxes */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Liquidez</label>
                <input className="input" placeholder="D+2, D+30..." value={form.liquidity} onChange={e => setForm((f: any) => ({ ...f, liquidity: e.target.value }))} />
              </div>
              <div className="flex flex-col justify-end gap-2 pb-2">
                <label className="flex items-center gap-2 cursor-pointer select-none text-sm">
                  <input
                    type="checkbox"
                    className="w-4 h-4 accent-emerald-500"
                    checked={form.pays_dividends}
                    onChange={e => setForm((f: any) => ({ ...f, pays_dividends: e.target.checked }))}
                  />
                  Paga dividendos / proventos
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none text-sm">
                  <input
                    type="checkbox"
                    className="w-4 h-4 accent-red-500"
                    checked={form.in_liquidation}
                    onChange={e => setForm((f: any) => ({ ...f, in_liquidation: e.target.checked }))}
                  />
                  Em liquidação extrajudicial
                </label>
              </div>
            </div>

            <div className="flex gap-3 pt-2 border-t border-gray-100 dark:border-gray-700">
              <button className="btn-secondary flex-1" onClick={() => setEditing(null)}>Cancelar</button>
              <button className="btn-primary flex-1" onClick={handleSave} disabled={saving}>{saving ? 'Guardando...' : 'Guardar'}</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function ImportPanel() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => { getImportHistory().then(setHistory); }, []);

  const handleFile = async (file: File) => {
    setImporting(true);
    setProgress(0);
    setResult(null);
    try {
      const res = await importExcel(file, setProgress);
      setResult(res);
      getImportHistory().then(setHistory);
    } finally {
      setImporting(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          dragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-700 hover:border-blue-400'
        }`}
      >
        <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
        <p className="text-3xl mb-2">📂</p>
        <p className="font-medium text-gray-700 dark:text-gray-300">Arrastrar Excel aquí o hacer clic para seleccionar</p>
        <p className="text-sm text-gray-400 mt-1">Inversiones.xlsx — Formatos .xlsx, .xls</p>
        {importing && (
          <div className="mt-4">
            <div className="bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div className="bg-blue-600 h-2 rounded-full transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-sm text-gray-500 mt-1">Importando... {progress}%</p>
          </div>
        )}
      </div>

      {/* Import result */}
      {result && (
        <div className={`card border ${result.status === 'success' ? 'border-emerald-300 dark:border-emerald-700' : result.status === 'partial' ? 'border-amber-300 dark:border-amber-700' : 'border-red-300 dark:border-red-700'}`}>
          <div className="flex items-center gap-2 mb-3">
            <span>{result.status === 'success' ? '✅' : result.status === 'partial' ? '⚠️' : '❌'}</span>
            <h3 className="font-semibold">Importación {result.status === 'success' ? 'exitosa' : result.status === 'partial' ? 'con advertencias' : 'fallida'}</h3>
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm mb-3">
            {Object.entries(result.records || {}).map(([k, v]) => (
              <div key={k} className="text-center">
                <p className="text-xl font-bold">{v as any}</p>
                <p className="text-gray-500 text-xs capitalize">{k.replace(/_/g, ' ')}</p>
              </div>
            ))}
          </div>
          {result.warnings?.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-amber-600 font-medium">{result.warnings.length} advertencias</summary>
              <ul className="mt-2 space-y-1 text-gray-600 dark:text-gray-400 pl-4">
                {result.warnings.map((w: string, i: number) => <li key={i}>• {w}</li>)}
              </ul>
            </details>
          )}
          {result.errors?.length > 0 && (
            <details className="text-sm mt-2">
              <summary className="cursor-pointer text-red-500 font-medium">{result.errors.length} errores</summary>
              <ul className="mt-2 space-y-1 text-gray-600 dark:text-gray-400 pl-4">
                {result.errors.map((e: string, i: number) => <li key={i}>• {e}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* Import history */}
      {history.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-sm">Historial de importaciones</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {['Archivo', 'Fecha', 'Estado', 'Posiciones', 'Warnings', 'Errores', ''].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {history.map((h: any) => (
                <tr key={h.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-3 py-2 font-medium">{h.filename}</td>
                  <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{new Date(h.imported_at).toLocaleString('es-AR')}</td>
                  <td className="px-3 py-2">
                    <span className={`badge ${h.status === 'success' ? 'bg-emerald-100 text-emerald-700' : h.status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                      {h.status}
                    </span>
                  </td>
                  <td className="px-3 py-2">{h.records_positions}</td>
                  <td className="px-3 py-2 text-amber-600">{h.warning_count}</td>
                  <td className="px-3 py-2 text-red-500">{h.error_count}</td>
                  <td className="px-3 py-2">
                    <button className="text-blue-500 text-xs" onClick={() => getImportDetail(h.id).then(setDetail)}>Ver detalle</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detail && (
        <Modal open={!!detail} onClose={() => setDetail(null)} title={`Detalle: ${detail.filename}`} size="xl">
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-3 gap-2">
              {Object.entries(detail.records || {}).map(([k, v]) => (
                <div key={k} className="text-center bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                  <p className="text-xl font-bold">{v as any}</p>
                  <p className="text-gray-500 text-xs capitalize">{k.replace(/_/g, ' ')}</p>
                </div>
              ))}
            </div>
            {detail.warnings?.length > 0 && (
              <div>
                <p className="font-semibold text-amber-600 mb-1">Advertencias ({detail.warnings.length})</p>
                <ul className="text-gray-600 dark:text-gray-400 space-y-1 max-h-40 overflow-y-auto">
                  {detail.warnings.map((w: string, i: number) => <li key={i}>• {w}</li>)}
                </ul>
              </div>
            )}
            {detail.errors?.length > 0 && (
              <div>
                <p className="font-semibold text-red-500 mb-1">Errores ({detail.errors.length})</p>
                <ul className="text-gray-600 dark:text-gray-400 space-y-1 max-h-40 overflow-y-auto">
                  {detail.errors.map((e: string, i: number) => <li key={i}>• {e}</li>)}
                </ul>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

function ToolsPanel() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ updated: number; total_portfolio: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [demoLoading, setDemoLoading] = useState(false);
  const [demoResult, setDemoResult] = useState<string | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);

  const handleRecalculate = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await client.post('/api/positions/recalculate-stats');
      setResult(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateDemo = async () => {
    setDemoLoading(true);
    setDemoResult(null);
    setDemoError(null);
    try {
      await client.post('/api/demo/regenerate');
      setDemoResult('Base de datos demo regenerada con éxito.');
    } catch (e: any) {
      setDemoError(e?.response?.data?.detail || e?.message || 'Error');
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <div>
          <h3 className="font-semibold text-gray-800 dark:text-gray-200">Recalcular rankings y retornos</h3>
          <p className="text-sm text-gray-500 mt-1">
            Recalcula <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">portfolio_pct</code>,{' '}
            <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">return_1m/3m/6m/12m</code> y{' '}
            <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">rank_1m/3m/6m/12m</code> para todos
            los instrumentos activos usando los datos históricos de posiciones mensuales.
          </p>
        </div>
        <button
          className="btn-primary text-sm disabled:opacity-50"
          disabled={loading}
          onClick={handleRecalculate}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
              Calculando...
            </span>
          ) : 'Recalcular ahora'}
        </button>
        {result && (
          <div className="flex items-center gap-3 text-sm bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-4 py-3">
            <span className="text-green-600 font-bold text-base">✓</span>
            <span className="text-green-700 dark:text-green-400">
              {result.updated} instrumentos actualizados · Portfolio total: R$ {result.total_portfolio.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </span>
          </div>
        )}
        {error && (
          <p className="text-sm text-red-500">{error}</p>
        )}
      </div>

      <div className="card space-y-3">
        <div>
          <h3 className="font-semibold text-gray-800 dark:text-gray-200">Regenerar base de datos demo</h3>
          <p className="text-sm text-gray-500 mt-1">
            Copia los instrumentos y precios actuales de la base real y genera posiciones ficticias nuevas.
            Útil cuando se agregan nuevos instrumentos y se quiere que aparezcan en el modo demo.
          </p>
        </div>
        <button
          className="btn-secondary text-sm disabled:opacity-50"
          disabled={demoLoading}
          onClick={handleRegenerateDemo}
        >
          {demoLoading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full" />
              Generando...
            </span>
          ) : 'Regenerar demo'}
        </button>
        {demoResult && (
          <div className="flex items-center gap-3 text-sm bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-4 py-3">
            <span className="text-green-600 font-bold text-base">✓</span>
            <span className="text-green-700 dark:text-green-400">{demoResult}</span>
          </div>
        )}
        {demoError && (
          <p className="text-sm text-red-500">{demoError}</p>
        )}
      </div>
    </div>
  );
}

export default function Settings() {
  const [tab, setTab] = useState<'instruments' | 'import' | 'tools'>('import');

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700">
        {[
          { key: 'import', label: 'Importar Excel' },
          { key: 'instruments', label: 'Catálogo de Instrumentos' },
          { key: 'tools', label: 'Herramientas' },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as any)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'import' && <ImportPanel />}
      {tab === 'instruments' && <InstrumentCatalog />}
      {tab === 'tools' && <ToolsPanel />}
    </div>
  );
}
