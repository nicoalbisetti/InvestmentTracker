import { useLocation } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';

const ROUTE_LABELS: Record<string, string> = {
  '/': 'Dashboard',
  '/positions': 'Posiciones Actuales',
  '/history': 'Evolución Histórica',
  '/annual': 'Análisis Anual',
  '/proventos': 'Proventos y Dividendos',
  '/transactions': 'Transacciones',
  '/settings': 'Configuración',
};

export default function Header() {
  const { pathname } = useLocation();
  const { theme, toggleTheme } = useTheme();
  const title = ROUTE_LABELS[pathname] || 'InvestmentTracker';

  return (
    <header className="flex items-center justify-between px-6 py-3 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 h-14">
      <div>
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300 transition-colors"
          title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
        >
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
      </div>
    </header>
  );
}
