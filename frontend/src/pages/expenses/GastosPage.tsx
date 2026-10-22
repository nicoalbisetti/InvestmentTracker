import { useSearchParams } from 'react-router-dom';
import SummaryTab from '../../components/expenses/SummaryTab';
import MovementsTab from '../../components/expenses/MovementsTab';
import ImportTab from '../../components/expenses/ImportTab';
import ReviewTab from '../../components/expenses/ReviewTab';
import ConfigTab from '../../components/expenses/ConfigTab';

const TABS = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'movimientos', label: 'Movimientos' },
  { id: 'revisar', label: 'Revisar' },
  { id: 'importar', label: 'Importar' },
  { id: 'config', label: 'Configuración' },
];

export default function GastosPage() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some(t => t.id === params.get('tab')) ? params.get('tab')! : 'resumen';

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Gastos</h1>
      <div className="flex gap-1 border-b border-slate-200 dark:border-slate-800">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setParams({ tab: t.id })}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
              tab === t.id ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'}`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'resumen' && <SummaryTab />}
      {tab === 'movimientos' && <MovementsTab />}
      {tab === 'revisar' && <ReviewTab />}
      {tab === 'importar' && <ImportTab />}
      {tab === 'config' && <ConfigTab />}
    </div>
  );
}
