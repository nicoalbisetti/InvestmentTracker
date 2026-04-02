import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ImportConfig, DiffItem, PreviewResponse, ImportResult, SuggestionItem,
  previewImport, confirmImport, itemKey, mapInstrument, getSuggestions,
} from '../api/importFixedIncome';
import { fmtBRL } from '../utils/formatters';

// ─── Default config ───────────────────────────────────────────────────────────

function defaultConfig(): ImportConfig {
  return {
    import_values: true,
    import_value_curva: true,
    import_value_mtm: true,
    value_change_threshold_pct: null,
    import_quantities: true,
    alert_quantity_change: false,
    import_instrument_data: true,
    import_maturity_date: true,
    import_issue_date: true,
    import_indexador: true,
    import_custodian: true,
    import_name: false,
    create_new_instruments: true,
    create_base_only: false,
    import_unit_price: true,
    custodian_filter: null,
  };
}

function defaultPeriod(): string {
  const now = new Date();
  const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, '0')}-01`;
}

// ─── Step indicator ───────────────────────────────────────────────────────────

function StepBar({ step }: { step: number }) {
  const steps = ['Configuración', 'Preview', 'Resultado'];
  return (
    <div className="flex items-center justify-center gap-0 mb-8">
      {steps.map((label, i) => {
        const n = i + 1;
        const active = n === step;
        const done = n < step;
        return (
          <div key={n} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                ${done ? 'bg-green-500 text-white' : active ? 'bg-blue-600 text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-500'}`}>
                {done ? '✓' : n}
              </div>
              <span className={`text-xs mt-1 whitespace-nowrap ${active ? 'text-blue-600 font-semibold' : 'text-gray-400'}`}>{label}</span>
            </div>
            {i < steps.length - 1 && (
              <div className={`w-16 h-0.5 mx-1 mb-5 ${done ? 'bg-green-400' : 'bg-gray-200 dark:bg-gray-700'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Step 1: Config form ──────────────────────────────────────────────────────

function Step1({
  config, setConfig, onSubmit, loading,
}: {
  config: ImportConfig;
  setConfig: (c: ImportConfig) => void;
  onSubmit: (file: File, period: string) => void;
  loading: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [period, setPeriod] = useState(defaultPeriod());
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    if (!f.name.match(/\.(xlsx|xls)$/i)) {
      alert('Solo se aceptan archivos .xlsx o .xls');
      return;
    }
    setFile(f);
  };

  const C = (field: keyof ImportConfig, val: boolean) =>
    setConfig({ ...config, [field]: val });

  return (
    <div className="space-y-6">
      {/* File + Period */}
      <div className="card space-y-4">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">Archivo y período</h2>

        {/* Drag & Drop */}
        <div
          className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
            ${dragOver ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files[0];
            if (f) handleFile(f);
          }}
          onClick={() => fileRef.current?.click()}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
          />
          {file ? (
            <div>
              <span className="text-green-600 font-semibold text-sm">📄 {file.name}</span>
              <p className="text-xs text-gray-400 mt-1">{(file.size / 1024).toFixed(0)} KB — Click para cambiar</p>
            </div>
          ) : (
            <div>
              <p className="text-gray-500 text-sm">Arrastrá el archivo Excel aquí o <span className="text-blue-500 underline">seleccioná</span></p>
              <p className="text-xs text-gray-400 mt-1">Formato: relatorio-consolidado-mensal-YYYY-mes.xlsx</p>
            </div>
          )}
        </div>

        {/* Period */}
        <div className="flex gap-4 items-end flex-wrap">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período (mes de referencia)</label>
            <input
              type="month"
              className="input"
              value={period.slice(0, 7)}
              onChange={e => setPeriod(e.target.value + '-01')}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Custodio</label>
            <select
              className="input"
              value={config.custodian_filter || ''}
              onChange={e => setConfig({ ...config, custodian_filter: e.target.value || null })}
            >
              <option value="">Todos</option>
              <option value="XP">Solo XP</option>
              <option value="SANTANDER">Solo Santander</option>
              <option value="INTER">Solo Inter</option>
            </select>
          </div>
        </div>
      </div>

      {/* Import options */}
      <div className="card space-y-5">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">¿Qué datos importar?</h2>

        {/* VALORES */}
        <OptionGroup title="Valores actualizados (balance BRL)" checked={config.import_values} onChange={v => C('import_values', v)}
          help="Desmarcar si ya ingresaste los valores manualmente este mes.">
          <SubOption label="Valor por curva (CDB, LCA, LCI, CRI, CRA, LIG, TD)" checked={config.import_value_curva} disabled={!config.import_values} onChange={v => C('import_value_curva', v)} />
          <SubOption label="Valor MTM — mark to market (Debêntures)" checked={config.import_value_mtm} disabled={!config.import_values} onChange={v => C('import_value_mtm', v)} />
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-gray-500 ml-6">Filtro de ruido: ignorar cambios menores a</span>
            <input
              type="number"
              className="input py-0.5 w-16 text-sm"
              placeholder="—"
              disabled={!config.import_values}
              value={config.value_change_threshold_pct ?? ''}
              onChange={e => setConfig({ ...config, value_change_threshold_pct: e.target.value ? parseFloat(e.target.value) : null })}
            />
            <span className="text-xs text-gray-500">%</span>
          </div>
        </OptionGroup>

        {/* CANTIDADES */}
        <OptionGroup title="Cantidades" checked={config.import_quantities} onChange={v => C('import_quantities', v)}
          help="Útil para detectar amortizaciones en CRIs y CRAs.">
          <SubOption label="Usar cantidad disponible" checked={true} disabled={true} onChange={() => {}} />
          <SubOption label="Alertar si la cantidad cambió (posible amortización parcial)" checked={config.alert_quantity_change} disabled={!config.import_quantities} onChange={v => C('alert_quantity_change', v)} />
        </OptionGroup>

        {/* DATOS DEL INSTRUMENTO */}
        <OptionGroup title="Actualizar datos del instrumento" checked={config.import_instrument_data} onChange={v => C('import_instrument_data', v)}
          help="Modificar datos del instrumento afecta el historial completo." helpStyle="warn">
          <SubOption label="Fecha de vencimiento" checked={config.import_maturity_date} disabled={!config.import_instrument_data} onChange={v => C('import_maturity_date', v)} />
          <SubOption label="Fecha de emisión" checked={config.import_issue_date} disabled={!config.import_instrument_data} onChange={v => C('import_issue_date', v)} />
          <SubOption label="Indexador (IPCA, CDI, SELIC, Prefixado)" checked={config.import_indexador} disabled={!config.import_instrument_data} onChange={v => C('import_indexador', v)} />
          <SubOption label="Custodio" checked={config.import_custodian} disabled={!config.import_instrument_data} onChange={v => C('import_custodian', v)} />
          <SubOption label="Nombre del emisor" checked={config.import_name} disabled={!config.import_instrument_data} onChange={v => C('import_name', v)} tooltip="Sobreescribe el nombre actual del instrumento" />
        </OptionGroup>

        {/* PRECIO UNITARIO */}
        <OptionGroup title="Precio unitario por título" checked={config.import_unit_price} onChange={v => C('import_unit_price', v)}
          help="Útil para calcular rendimiento por unidad en el tiempo." />

        {/* NUEVOS INSTRUMENTOS */}
        <OptionGroup title="Crear instrumentos nuevos automáticamente" checked={config.create_new_instruments} onChange={v => C('create_new_instruments', v)}
          help="Si desmarcado, solo se actualizan instrumentos ya registrados.">
          <div className="ml-6 space-y-1">
            <label className={`flex items-center gap-2 text-sm ${!config.create_new_instruments ? 'opacity-40' : ''}`}>
              <input type="radio" name="create_mode" disabled={!config.create_new_instruments} checked={!config.create_base_only} onChange={() => C('create_base_only', false)} />
              <span>Crear con todos los datos disponibles</span>
            </label>
            <label className={`flex items-center gap-2 text-sm ${!config.create_new_instruments ? 'opacity-40' : ''}`}>
              <input type="radio" name="create_mode" disabled={!config.create_new_instruments} checked={config.create_base_only} onChange={() => C('create_base_only', true)} />
              <span>Crear solo el registro base sin posición inicial</span>
            </label>
          </div>
        </OptionGroup>
      </div>

      {/* Submit */}
      <div className="flex justify-end">
        <button
          className="btn-primary px-8 py-2.5 text-sm font-medium disabled:opacity-50"
          disabled={!file || loading}
          onClick={() => file && onSubmit(file, period)}
        >
          {loading ? (
            <span className="flex items-center gap-2"><span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full" /> Analizando...</span>
          ) : 'Analizar diferencias →'}
        </button>
      </div>
    </div>
  );
}

function OptionGroup({ title, checked, onChange, children, help, helpStyle }: {
  title: string; checked: boolean; onChange: (v: boolean) => void;
  children?: React.ReactNode; help?: string; helpStyle?: 'warn';
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <label className="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" className="w-4 h-4 accent-blue-600" checked={checked} onChange={e => onChange(e.target.checked)} />
        <span className="font-medium text-sm text-gray-800 dark:text-gray-200">{title}</span>
      </label>
      {children && <div className="mt-3 space-y-1.5">{children}</div>}
      {help && (
        <p className={`text-xs mt-2 ${helpStyle === 'warn' ? 'text-amber-600' : 'text-gray-400'}`}>{help}</p>
      )}
    </div>
  );
}

function SubOption({ label, checked, disabled, onChange, tooltip }: {
  label: string; checked: boolean; disabled: boolean; onChange: (v: boolean) => void; tooltip?: string;
}) {
  return (
    <label className={`flex items-center gap-2 text-sm ml-6 cursor-pointer ${disabled ? 'opacity-40 pointer-events-none' : ''}`} title={tooltip}>
      <input type="checkbox" className="w-3.5 h-3.5 accent-blue-600" checked={checked} disabled={disabled} onChange={e => onChange(e.target.checked)} />
      <span className="text-gray-700 dark:text-gray-300">{label}</span>
      {tooltip && <span className="text-gray-400 text-xs">ⓘ</span>}
    </label>
  );
}

// ─── Map Instrument Modal ─────────────────────────────────────────────────────

function MapInstrumentModal({ item, fileToken, onMapped, onClose }: {
  item: DiffItem;
  fileToken: string;
  onMapped: (codigo: string, custodianOverride: string | null, instrumentId: number, instrumentName: string) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState('');
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    getSuggestions(fileToken, item.codigo)
      .then(setSuggestions)
      .catch(() => setSuggestions([]))
      .finally(() => setLoading(false));
  }, [fileToken, item.codigo]);

  const filtered = suggestions.filter(s =>
    !search || s.name.toLowerCase().includes(search.toLowerCase()) || s.custodian.toLowerCase().includes(search.toLowerCase())
  );

  const handleSelect = async (suggestion: SuggestionItem) => {
    setSaving(true);
    try {
      await mapInstrument(item.codigo, suggestion.id, fileToken, item.custodian_override);
      onMapped(item.codigo, item.custodian_override, suggestion.id, suggestion.name);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="font-semibold text-gray-900 dark:text-white text-base">Mapear instrumento</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                <span className="font-mono">{item.codigo}</span> — {item.nome.slice(0, 50)}
              </p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none ml-4">×</button>
          </div>
          <input
            autoFocus
            className="input w-full mt-3 text-sm"
            placeholder="Buscar instrumento existente..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <div className="overflow-y-auto flex-1 p-2">
          {loading ? (
            <div className="text-center py-8 text-gray-400 text-sm">Cargando...</div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">Sin resultados</div>
          ) : (
            filtered.map(s => (
              <button
                key={s.id}
                disabled={saving}
                onClick={() => handleSelect(s)}
                className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex items-center justify-between group"
              >
                <div>
                  <div className="text-sm font-medium text-gray-800 dark:text-gray-200">{s.name}</div>
                  <div className="text-xs text-gray-400">{s.custodian}{s.maturity_date ? ` · vence ${s.maturity_date}` : ''}</div>
                </div>
                <div className="flex items-center gap-2">
                  {s.score >= 5 && (
                    <span className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full">
                      {s.score >= 8 ? 'Alta' : 'Sugerido'}
                    </span>
                  )}
                  <span className="text-xs text-blue-500 opacity-0 group-hover:opacity-100">Seleccionar</span>
                </div>
              </button>
            ))
          )}
        </div>

        <div className="px-5 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button className="btn-secondary text-sm" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}


// ─── Step 2: Preview / Diff ───────────────────────────────────────────────────

type TabFilter = 'all' | 'NEW' | 'UPDATED' | 'UNCHANGED' | 'DISAPPEARED' | 'warnings';

const STATUS_LABEL: Record<string, string> = {
  NEW: 'Nuevo', UPDATED: 'Actualizado', UNCHANGED: 'Sin cambios', DISAPPEARED: 'Desaparecido',
};
const STATUS_COLOR: Record<string, string> = {
  NEW: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  UPDATED: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  UNCHANGED: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
  DISAPPEARED: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
};

function fmtMaturity(d: string | null) {
  if (!d) return '—';
  const [year, month] = d.split('-');
  return `${month}/${year}`;
}

function Step2({
  preview, setPreview, config, selectedKeys, setSelectedKeys, onConfirm, onBack, loading,
}: {
  preview: PreviewResponse;
  setPreview: (p: PreviewResponse) => void;
  config: ImportConfig;
  selectedKeys: Set<string>;
  setSelectedKeys: (s: Set<string>) => void;
  onConfirm: () => void;
  onBack: () => void;
  loading: boolean;
}) {
  const [tab, setTab] = useState<TabFilter>('all');
  const [page, setPage] = useState(1);
  const [showWarnings, setShowWarnings] = useState(false);
  const [mappingItem, setMappingItem] = useState<DiffItem | null>(null);
  const [statusFilters, setStatusFilters] = useState({ NEW: true, UPDATED: true, DISAPPEARED: false });
  const PER_PAGE = 20;
  const { summary, differences, parse_warnings } = preview;

  const toggleStatusFilter = (status: 'NEW' | 'UPDATED' | 'DISAPPEARED') => {
    const newVal = !statusFilters[status];
    setStatusFilters(prev => ({ ...prev, [status]: newVal }));
    setSelectedKeys(current => {
      const next = new Set(current);
      differences.filter(d => d.status === status).forEach(d => {
        if (newVal) next.add(itemKey(d));
        else next.delete(itemKey(d));
      });
      return next;
    });
    setPage(1);
  };

  const handleMapped = (codigo: string, custodianOverride: string | null, instrumentId: number, instrumentName: string) => {
    // Update the diff item in local state: NEW → UPDATED, store instrument_id
    const updatedDiff = preview.differences.map(d => {
      if (d.codigo === codigo && d.custodian_override === custodianOverride) {
        return { ...d, status: 'UPDATED' as const, instrument_id: instrumentId,
                 warnings: d.warnings.filter(w => !w.startsWith('Auto-match')) };
      }
      return d;
    });
    const updatedSummary = {
      ...preview.summary,
      new_instruments: updatedDiff.filter(d => d.status === 'NEW').length,
      updated_positions: updatedDiff.filter(d => d.status === 'UPDATED').length,
    };
    setPreview({ ...preview, differences: updatedDiff, summary: updatedSummary });
    // Auto-select the newly mapped item
    const k = `${codigo}::${custodianOverride ?? ''}`;
    const next = new Set(selectedKeys);
    next.add(k);
    setSelectedKeys(next);
    setMappingItem(null);
  };

  const toggleKey = useCallback((key: string) => {
    const next = new Set(selectedKeys);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setSelectedKeys(next);
  }, [selectedKeys, setSelectedKeys]);

  const filtered = differences.filter(d => {
    if (d.status === 'NEW' && !statusFilters.NEW) return false;
    if (d.status === 'UPDATED' && !statusFilters.UPDATED) return false;
    if (d.status === 'DISAPPEARED' && !statusFilters.DISAPPEARED) return false;
    if (tab === 'all') return true;
    if (tab === 'warnings') return d.warnings.length > 0;
    return d.status === tab;
  });

  const pages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const pageItems = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  const selectedCount = selectedKeys.size;

  const allPageSelected = pageItems.every(d => selectedKeys.has(itemKey(d)));
  const toggleAll = () => {
    const next = new Set(selectedKeys);
    if (allPageSelected) pageItems.forEach(d => next.delete(itemKey(d)));
    else pageItems.forEach(d => next.add(itemKey(d)));
    setSelectedKeys(next);
  };

  const tabCounts: Record<string, number> = {
    all: differences.length,
    NEW: summary.new_instruments,
    UPDATED: summary.updated_positions,
    UNCHANGED: summary.unchanged,
    DISAPPEARED: summary.disappeared,
    warnings: differences.filter(d => d.warnings.length > 0).length,
  };

  return (
    <div className="space-y-4">
      {/* Mapping modal */}
      {mappingItem && (
        <MapInstrumentModal
          item={mappingItem}
          fileToken={preview.file_token}
          onMapped={handleMapped}
          onClose={() => setMappingItem(null)}
        />
      )}

      {/* Header */}
      <div className="card">
        <div className="flex flex-wrap gap-4 items-center justify-between">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <span className="font-semibold text-gray-800 dark:text-gray-200">{summary.total_in_file} instrumentos</span> en el archivo
            {' · '}Período: <span className="font-semibold">{preview.period_date}</span>
          </div>
          <div className="flex flex-wrap gap-1.5 text-xs">
            {config.import_values && <span className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 px-2 py-0.5 rounded-full">Valores ✓</span>}
            {config.import_quantities && <span className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 px-2 py-0.5 rounded-full">Cantidades ✓</span>}
            {config.import_instrument_data && <span className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 px-2 py-0.5 rounded-full">Datos instrum. ✓</span>}
            {config.create_new_instruments && <span className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 px-2 py-0.5 rounded-full">Nuevos ✓</span>}
            {config.import_unit_price && <span className="bg-blue-50 dark:bg-blue-900/20 text-blue-600 px-2 py-0.5 rounded-full">Precio unit. ✓</span>}
          </div>
        </div>
      </div>

      {/* Status filter checkboxes */}
      <div className="card py-3 px-4 flex gap-5 items-center flex-wrap">
        <span className="text-sm text-gray-500 font-medium">Importar:</span>
        {([
          { key: 'NEW', label: 'Nuevos', color: 'text-blue-600' },
          { key: 'UPDATED', label: 'Actualizados', color: 'text-yellow-600' },
          { key: 'DISAPPEARED', label: 'Desaparecidos', color: 'text-red-600' },
        ] as const).map(({ key, label, color }) => (
          <label key={key} className={`flex items-center gap-1.5 text-sm font-medium ${color} cursor-pointer select-none`}>
            <input
              type="checkbox"
              className="w-4 h-4 accent-blue-600"
              checked={statusFilters[key]}
              onChange={() => toggleStatusFilter(key)}
            />
            {label} ({tabCounts[key]})
          </label>
        ))}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {([
          { key: 'NEW', label: 'Nuevos', color: 'text-blue-600', dot: '🟢' },
          { key: 'UPDATED', label: 'Actualizados', color: 'text-yellow-600', dot: '🟡' },
          { key: 'UNCHANGED', label: 'Sin cambios', color: 'text-gray-500', dot: '⚪' },
          { key: 'DISAPPEARED', label: 'Desaparecidos', color: 'text-red-600', dot: '🔴' },
          { key: 'warnings', label: 'Con warnings', color: 'text-amber-600', dot: '⚠️' },
        ] as const).map(({ key, label, color, dot }) => (
          <button
            key={key}
            onClick={() => { setTab(tab === key ? 'all' : key); setPage(1); }}
            className={`card p-3 text-center cursor-pointer transition-all hover:shadow-md
              ${tab === key ? 'ring-2 ring-blue-500' : ''}`}
          >
            <div className="text-lg font-bold">{dot} {tabCounts[key]}</div>
            <div className={`text-xs ${color}`}>{label}</div>
          </button>
        ))}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 flex-wrap">
        {(['all', 'NEW', 'UPDATED', 'UNCHANGED', 'DISAPPEARED', 'warnings'] as TabFilter[]).map(t => (
          <button
            key={t}
            onClick={() => { setTab(t); setPage(1); }}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors
              ${tab === t ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200'}`}
          >
            {t === 'all' ? 'Todos' : t === 'warnings' ? '⚠️ Warnings' : STATUS_LABEL[t]} ({tabCounts[t]})
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
              <tr>
                <th className="px-3 py-2 w-8">
                  <input type="checkbox" className="w-3.5 h-3.5" checked={allPageSelected && pageItems.length > 0} onChange={toggleAll} />
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Estado</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Código</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Instrumento</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Tipo</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Custodio</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Vencto</th>
                {config.import_values && (
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">Ant. → Nuevo</th>
                )}
                {config.import_quantities && (
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">Cant.</th>
                )}
                <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Avisos</th>
                <th className="px-3 py-2 w-16"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {pageItems.length === 0 && (
                <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">No hay items en esta categoría</td></tr>
              )}
              {pageItems.map(item => {
                const key = itemKey(item);
                const checked = selectedKeys.has(key);
                return (
                  <tr key={key} className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors ${!checked ? 'opacity-60' : ''}`}>
                    <td className="px-3 py-2">
                      <input type="checkbox" className="w-3.5 h-3.5" checked={checked} onChange={() => toggleKey(key)} />
                    </td>
                    <td className="px-3 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[item.status]}`}>
                        {STATUS_LABEL[item.status]}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-600 dark:text-gray-400">{item.codigo || '—'}</td>
                    <td className="px-3 py-2 max-w-[180px]">
                      <div className="truncate text-gray-800 dark:text-gray-200" title={item.nome}>{item.nome}</div>
                      {item.in_liquidation && (
                        <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full ml-0 mt-0.5 inline-block">Em liquidação</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">{item.tipo}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {item.custodian}
                      {item.custodian_override && (
                        <span className="ml-1 text-xs text-amber-500" title="Posición separada por custodio">*</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">{fmtMaturity(item.vencimento)}</td>
                    {config.import_values && (
                      <td className="px-3 py-2 text-xs whitespace-nowrap">
                        {item.status === 'DISAPPEARED' ? (
                          <span className="text-gray-400">{fmtBRL(item.ultimo_valor_brl)}</span>
                        ) : item.valor_actual_brl == null ? (
                          <span className="text-gray-400 italic" title="ANBIMA no valoriza">💰 Sin precio</span>
                        ) : (
                          <span>
                            <span className="text-gray-400">{item.valor_anterior_brl != null ? fmtBRL(item.valor_anterior_brl) : '—'}</span>
                            <span className="mx-1 text-gray-300">→</span>
                            <span className="font-medium text-gray-800 dark:text-gray-200">{fmtBRL(item.valor_actual_brl)}</span>
                            {item.variacion_pct != null && (
                              <span className={`ml-1 ${item.variacion_pct >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                                ({item.variacion_pct >= 0 ? '+' : ''}{item.variacion_pct.toFixed(1)}%)
                              </span>
                            )}
                          </span>
                        )}
                      </td>
                    )}
                    {config.import_quantities && (
                      <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
                        {item.cantidad_anterior != null && item.cantidad_actual != null && item.cantidad_anterior !== item.cantidad_actual ? (
                          <span>
                            <span className="text-gray-400">{item.cantidad_anterior}</span>
                            <span className="mx-1 text-gray-300">→</span>
                            <span className="font-medium">{item.cantidad_actual}</span>
                          </span>
                        ) : (
                          item.cantidad_actual ?? '—'
                        )}
                      </td>
                    )}
                    <td className="px-3 py-2">
                      {item.warnings.length > 0 && (
                        <span title={item.warnings.join('\n')} className="cursor-help text-amber-500 text-base">⚠️</span>
                      )}
                    </td>
                    <td className="px-2 py-2">
                      {item.status === 'NEW' && (
                        <button
                          className="text-xs text-blue-500 hover:text-blue-700 whitespace-nowrap underline"
                          onClick={() => setMappingItem(item)}
                        >
                          Mapear
                        </button>
                      )}
                      {item.status === 'UPDATED' && item.instrument_id && (
                        <button
                          className="text-xs text-gray-400 hover:text-blue-500 whitespace-nowrap"
                          title="Cambiar mapeo"
                          onClick={() => setMappingItem(item)}
                        >
                          ✎
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        {pages > 1 && (
          <div className="flex justify-between items-center px-4 py-3 border-t border-gray-200 dark:border-gray-700 text-sm text-gray-500">
            <span>Página {page} de {pages} ({filtered.length} items)</span>
            <div className="flex gap-2">
              <button className="btn-secondary py-1 text-xs" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
              <button className="btn-secondary py-1 text-xs" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Siguiente →</button>
            </div>
          </div>
        )}
      </div>

      {/* Parse warnings */}
      {parse_warnings.length > 0 && (
        <div className="card bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800">
          <button className="flex items-center gap-2 text-sm font-medium text-amber-700 dark:text-amber-400 w-full text-left" onClick={() => setShowWarnings(w => !w)}>
            <span>⚠️ {parse_warnings.length} avisos del archivo</span>
            <span className="ml-auto">{showWarnings ? '▲' : '▼'}</span>
          </button>
          {showWarnings && (
            <ul className="mt-3 space-y-1">
              {parse_warnings.map((w, i) => <li key={i} className="text-xs text-amber-700 dark:text-amber-400">• {w}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex justify-between items-center">
        <button className="btn-secondary" onClick={onBack}>← Volver a config</button>
        <button
          className="btn-primary px-6 py-2.5 text-sm font-medium disabled:opacity-50"
          disabled={selectedCount === 0 || loading}
          onClick={onConfirm}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
              Importando...
            </span>
          ) : `Importar seleccionados (${selectedCount}) →`}
        </button>
      </div>
    </div>
  );
}

// ─── Step 3: Result ───────────────────────────────────────────────────────────

function Step3({ result, onViewPositions, onReset }: {
  result: ImportResult;
  onViewPositions: () => void;
  onReset: () => void;
}) {
  if (!result.success && result.errors.length > 0 && result.imported.new_instruments === 0 && result.imported.new_positions === 0 && result.imported.updated_positions === 0) {
    // Complete failure
    return (
      <div className="card border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/10">
        <h2 className="text-lg font-bold text-red-700 dark:text-red-400 mb-4">Error en la importación</h2>
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {result.errors.map((e, i) => <p key={i} className="text-sm text-red-600">• {e}</p>)}
        </div>
        <div className="mt-4">
          <button className="btn-secondary" onClick={onReset}>Reintentar</button>
        </div>
      </div>
    );
  }

  const hasPartialErrors = result.errors.length > 0;

  return (
    <div className={`card border ${hasPartialErrors ? 'border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/10' : 'border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-900/10'}`}>
      <div className="flex items-center gap-3 mb-5">
        <span className="text-3xl">{hasPartialErrors ? '⚠️' : '✅'}</span>
        <h2 className={`text-lg font-bold ${hasPartialErrors ? 'text-amber-700 dark:text-amber-400' : 'text-green-700 dark:text-green-400'}`}>
          {hasPartialErrors ? 'Importación completada con avisos' : 'Importación completada'}
        </h2>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-5">
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-600">{result.imported.new_instruments}</div>
          <div className="text-xs text-gray-500">Instrumentos nuevos</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-600">{result.imported.new_positions}</div>
          <div className="text-xs text-gray-500">Posiciones nuevas</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-yellow-600">{result.imported.updated_positions}</div>
          <div className="text-xs text-gray-500">Posiciones actualizadas</div>
        </div>
        {(result.imported.closed_instruments ?? 0) > 0 && (
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">{result.imported.closed_instruments}</div>
            <div className="text-xs text-gray-500">Instrumentos cerrados</div>
          </div>
        )}
        <div className="text-center">
          <div className="text-2xl font-bold text-gray-500">{result.skipped}</div>
          <div className="text-xs text-gray-500">Omitidos</div>
        </div>
      </div>

      {hasPartialErrors && (
        <div className="mb-4">
          <p className="text-sm font-medium text-amber-700 dark:text-amber-400 mb-2">Errores parciales:</p>
          <div className="max-h-32 overflow-y-auto space-y-1">
            {result.errors.map((e, i) => <p key={i} className="text-xs text-amber-700">• {e}</p>)}
          </div>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="mb-4 space-y-1">
          {result.warnings.map((w, i) => <p key={i} className="text-xs text-gray-500">• {w}</p>)}
        </div>
      )}

      <div className="flex gap-3 flex-wrap">
        <button className="btn-primary" onClick={onViewPositions}>Ver posiciones actualizadas</button>
        <button className="btn-secondary" onClick={onReset}>Importar otro archivo</button>
      </div>
    </div>
  );
}

// ─── Main wizard ──────────────────────────────────────────────────────────────

export default function ImportFixedIncome() {
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [config, setConfig] = useState<ImportConfig>(defaultConfig());
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (file: File, period: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await previewImport(file, period, config);
      setPreview(res);
      // Default selection: NEW and UPDATED are checked; UNCHANGED and DISAPPEARED are not
      const initSelected = new Set<string>();
      res.differences.forEach(d => {
        if (d.status === 'NEW' || d.status === 'UPDATED') {
          initSelected.add(itemKey(d));
        }
      });
      setSelectedKeys(initSelected);
      setStep(2);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Error al analizar el archivo');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!preview) return;
    setLoading(true);
    setError(null);
    try {
      // skip_keys = all items NOT in selectedKeys
      const skipKeys = preview.differences
        .map(d => itemKey(d))
        .filter(k => !selectedKeys.has(k));

      const res = await confirmImport(
        preview.file_token,
        preview.period_date,
        config,
        skipKeys,
      );
      setResult(res);
      setStep(3);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Error al importar');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStep(1);
    setPreview(null);
    setSelectedKeys(new Set());
    setResult(null);
    setError(null);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <button className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm" onClick={() => navigate('/positions')}>
          ← Posiciones
        </button>
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">Importar Extrato Renta Fija</h1>
      </div>

      <StepBar step={step} />

      {error && (
        <div className="card border border-red-300 bg-red-50 dark:bg-red-900/10 text-red-700 dark:text-red-400 text-sm p-3">
          {error}
        </div>
      )}

      {step === 1 && (
        <Step1
          config={config}
          setConfig={setConfig}
          onSubmit={handleAnalyze}
          loading={loading}
        />
      )}
      {step === 2 && preview && (
        <Step2
          preview={preview}
          setPreview={setPreview}
          config={config}
          selectedKeys={selectedKeys}
          setSelectedKeys={setSelectedKeys}
          onConfirm={handleConfirm}
          onBack={() => setStep(1)}
          loading={loading}
        />
      )}
      {step === 3 && result && (
        <Step3
          result={result}
          onViewPositions={() => navigate('/positions')}
          onReset={handleReset}
        />
      )}
    </div>
  );
}
