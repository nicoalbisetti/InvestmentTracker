import { useEffect, useRef, useState } from 'react';
import { getInstruments, updateInstrument } from '../api/instruments';
import { importExcel, getImportHistory, getImportDetail } from '../api/import';
import Modal from '../components/ui/Modal';
import { INSTRUMENT_TYPE_LABELS } from '../utils/formatters';

const TYPE_OPTIONS = Object.entries(INSTRUMENT_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }));

function InstrumentCatalog() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [saving, setSaving] = useState(false);

  const load = () => {
    getInstruments({ search: search || undefined, page, limit: 50 }).then(setData);
  };

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [search, page]);

  const handleEdit = (inst: any) => {
    setEditing(inst);
    setForm({ type: inst.type, liquidity: inst.liquidity || '', maturity_date: inst.maturity_date || '', status: inst.status });
  };

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true);
    await updateInstrument(editing.id, {
      type: form.type,
      liquidity: form.liquidity || undefined,
      maturity_date: form.maturity_date || undefined,
      status: form.status,
    });
    setSaving(false);
    setEditing(null);
    load();
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <input className="input w-64" placeholder="Buscar instrumento..." value={search} onChange={e => setSearch(e.target.value)} />
        <span className="text-sm text-gray-500 self-center">{data.total} instrumentos</span>
      </div>
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto max-h-80">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>
                {['Instrumento', 'Custodio', 'Tipo', 'Estado', 'Liquidez', 'Vencimiento', ''].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {data.items.map((inst: any) => (
                <tr key={inst.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-3 py-2 font-medium max-w-[160px] truncate" title={inst.name}>{inst.name}</td>
                  <td className="px-3 py-2 text-gray-500">{inst.custodian}</td>
                  <td className="px-3 py-2 text-gray-600">{INSTRUMENT_TYPE_LABELS[inst.type] || inst.type}</td>
                  <td className="px-3 py-2">
                    <span className={`badge ${inst.status === 'activo' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-gray-100 text-gray-500'}`}>
                      {inst.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-500">{inst.liquidity || '—'}</td>
                  <td className="px-3 py-2 text-gray-500">{inst.maturity_date || '—'}</td>
                  <td className="px-3 py-2">
                    <button className="text-blue-500 hover:text-blue-700 text-xs" onClick={() => handleEdit(inst)}>Editar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.pages > 1 && (
          <div className="flex gap-2 px-3 py-2 border-t border-gray-100 dark:border-gray-800">
            <button className="btn-secondary text-xs py-1" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Ant</button>
            <span className="text-xs text-gray-500 self-center">Pág {page} de {data.pages}</span>
            <button className="btn-secondary text-xs py-1" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Sig →</button>
          </div>
        )}
      </div>

      {editing && (
        <Modal open={!!editing} onClose={() => setEditing(null)} title={`Editar: ${editing.name}`} size="sm">
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium mb-1">Tipo</label>
              <select className="input" value={form.type} onChange={e => setForm((f: any) => ({ ...f, type: e.target.value }))}>
                {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Liquidez</label>
              <input className="input" placeholder="D+2, D+30..." value={form.liquidity} onChange={e => setForm((f: any) => ({ ...f, liquidity: e.target.value }))} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Vencimiento</label>
              <input type="date" className="input" value={form.maturity_date} onChange={e => setForm((f: any) => ({ ...f, maturity_date: e.target.value }))} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Estado</label>
              <select className="input" value={form.status} onChange={e => setForm((f: any) => ({ ...f, status: e.target.value }))}>
                <option value="activo">Activo</option>
                <option value="cerrado">Cerrado</option>
                <option value="sin_datos">Sin datos</option>
              </select>
            </div>
            <div className="flex gap-3 pt-2">
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

export default function Settings() {
  const [tab, setTab] = useState<'instruments' | 'import'>('import');

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700">
        {[
          { key: 'import', label: 'Importar Excel' },
          { key: 'instruments', label: 'Catálogo de Instrumentos' },
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
    </div>
  );
}
