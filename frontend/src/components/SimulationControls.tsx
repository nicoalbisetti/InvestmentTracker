import { INSTRUMENT_TYPE_COLORS } from '../utils/formatters';
import { SimulationParams, CLASS_LABELS } from '../api/simulation';

const RATE_CLASSES = ['renta_fija', 'accion', 'fii', 'fundo', 'internacional'] as const;

function formatHorizonLabel(months: number): string {
  const years = Math.floor(months / 12);
  const rem = months % 12;
  if (rem === 0) return years === 1 ? '1 año' : `${years} años`;
  if (years === 0) return `${rem} meses`;
  return `${years} año${years > 1 ? 's' : ''} ${rem} mes${rem > 1 ? 'es' : ''}`;
}

interface Props {
  params: SimulationParams;
  onChange: (params: SimulationParams) => void;
  onReset: () => void;
}

export default function SimulationControls({ params, onChange, onReset }: Props) {
  const setField = <K extends keyof SimulationParams>(key: K, val: SimulationParams[K]) =>
    onChange({ ...params, [key]: val });

  return (
    <div className="card space-y-6 w-full">
      {/* Horizonte temporal */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Horizonte
          </label>
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            {formatHorizonLabel(params.horizon_months)}
          </span>
        </div>
        <input
          type="range"
          min={12}
          max={120}
          step={1}
          value={params.horizon_months}
          onChange={(e) => setField('horizon_months', Number(e.target.value))}
          className="w-full accent-indigo-600"
        />
        <div className="flex justify-between text-xs text-slate-400">
          {[12, 24, 36, 60, 84, 120].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setField('horizon_months', m)}
              className="hover:text-indigo-600 transition-colors"
            >
              {m / 12}a
            </button>
          ))}
        </div>
      </div>

      {/* Aporte mensual */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Aporte mensual
        </label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400">R$</span>
          <input
            type="number"
            min={0}
            step={100}
            value={params.monthly_contribution_brl || ''}
            placeholder="0"
            onChange={(e) => setField('monthly_contribution_brl', Number(e.target.value) || 0)}
            className="input pl-9 w-full"
          />
        </div>
      </div>

      {/* Tasas de retorno */}
      <div className="space-y-3">
        <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Retorno anual por clase
        </label>
        {RATE_CLASSES.map((cls) => {
          const rateKey = `rate_${cls}` as keyof SimulationParams;
          const pctValue = Math.round((params[rateKey] as number) * 1000) / 10;
          return (
            <div key={cls} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: INSTRUMENT_TYPE_COLORS[cls] }}
              />
              <label className="text-sm text-slate-600 dark:text-slate-300 flex-1 min-w-0 truncate">
                {CLASS_LABELS[cls]}
              </label>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min={0}
                  max={50}
                  step={0.5}
                  value={pctValue}
                  onChange={(e) => setField(rateKey, Number(e.target.value) / 100)}
                  className="input w-16 text-right py-1 text-sm"
                />
                <span className="text-sm text-slate-400">%</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Reset */}
      <button
        type="button"
        onClick={onReset}
        className="w-full btn-secondary text-sm"
      >
        Restaurar defaults
      </button>
    </div>
  );
}
