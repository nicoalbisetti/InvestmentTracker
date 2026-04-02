import { useLocation } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';
import { Sun, Moon } from 'lucide-react';

const ROUTE_LABELS: Record<string, string> = {
  '/':              'Dashboard',
  '/positions':     'Posiciones',
  '/history':       'Evolución',
  '/annual':        'Anual',
  '/proventos':     'Proventos',
  '/transactions':  'Transacciones',
  '/settings':      'Configuración',
};

export default function Header() {
  const { pathname } = useLocation();
  const { theme, toggleTheme } = useTheme();
  const title = ROUTE_LABELS[pathname] || 'InvestTracker';

  return (
    <header className="flex items-center justify-between px-6 h-14 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 shrink-0">
      <h1 className="text-base font-semibold text-slate-800 dark:text-slate-100 tracking-tight">{title}</h1>
      <button
        onClick={toggleTheme}
        className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors"
        title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
      >
        {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
      </button>
    </header>
  );
}
