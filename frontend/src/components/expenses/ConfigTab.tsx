import { useSearchParams } from 'react-router-dom';
import AccountsTab from './AccountsTab';
import CategoriesPanel from './CategoriesPanel';
import FxTab from './FxTab';
import RulesTab from './RulesTab';

const SECTIONS = [
  { id: 'cuentas', label: 'Cuentas' },
  { id: 'reglas', label: 'Reglas' },
  { id: 'fx', label: 'Tipos de cambio' },
  { id: 'categorias', label: 'Categorías' },
];

export default function ConfigTab() {
  const [params, setParams] = useSearchParams();
  const section = SECTIONS.some(s => s.id === params.get('section')) ? params.get('section')! : 'cuentas';
  const setSection = (id: string) => setParams({ tab: 'config', section: id });
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {SECTIONS.map(s => (
          <button key={s.id} onClick={() => setSection(s.id)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium ${section === s.id ? 'bg-indigo-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200'}`}>
            {s.label}
          </button>))}
      </div>
      {section === 'cuentas' && <AccountsTab />}
      {section === 'reglas' && <RulesTab />}
      {section === 'fx' && <FxTab />}
      {section === 'categorias' && <CategoriesPanel />}
    </div>
  );
}
