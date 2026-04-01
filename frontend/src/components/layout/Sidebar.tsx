import { NavLink } from 'react-router-dom';
import { useState } from 'react';
import {
  LayoutDashboard, Briefcase, CalendarDays, BarChart2,
  Landmark, ArrowLeftRight, Settings2, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { useEnv } from '../../context/EnvContext';

const NAV_ITEMS = [
  { to: '/',             label: 'Dashboard',      Icon: LayoutDashboard },
  { to: '/positions',    label: 'Posiciones',      Icon: Briefcase },
  { to: '/history',      label: 'Histórico',       Icon: CalendarDays },
  { to: '/annual',       label: 'Anual',           Icon: BarChart2 },
  { to: '/proventos',    label: 'Proventos',       Icon: Landmark },
  { to: '/transactions', label: 'Transacciones',   Icon: ArrowLeftRight },
  { to: '/settings',     label: 'Configuración',   Icon: Settings2 },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const { env, toggleEnv } = useEnv();

  return (
    <aside
      className={`relative flex flex-col bg-slate-900 transition-all duration-300 ease-in-out ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Logo */}
      <div className={`flex items-center h-14 border-b border-slate-800 ${collapsed ? 'justify-center px-2' : 'px-5'}`}>
        {collapsed ? (
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
            <TrendingUp size={15} className="text-white" />
          </div>
        ) : (
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
              <TrendingUp size={15} className="text-white" />
            </div>
            <span className="font-bold text-white text-sm tracking-tight">InvestTracker</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 space-y-0.5 px-2 overflow-hidden">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={17} className={`shrink-0 ${isActive ? 'text-white' : 'text-slate-500 group-hover:text-slate-300'}`} />
                {!collapsed && <span className="truncate">{label}</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Env toggle */}
      <div className={`px-2 pb-3 ${collapsed ? 'flex justify-center' : ''}`}>
        <button
          onClick={toggleEnv}
          title={env === 'demo' ? 'Cambiar a datos reales' : 'Cambiar a modo demo'}
          className={`flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold w-full transition-all ${
            env === 'demo'
              ? 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30'
              : 'bg-slate-800 text-slate-500 hover:bg-slate-700 hover:text-slate-300'
          } ${collapsed ? 'justify-center' : ''}`}
        >
          <span className={`w-2 h-2 rounded-full shrink-0 ${env === 'demo' ? 'bg-amber-400' : 'bg-slate-600'}`} />
          {!collapsed && (env === 'demo' ? 'Demo' : 'Real')}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(c => !c)}
        className="absolute -right-3 top-[52px] w-6 h-6 rounded-full bg-slate-700 hover:bg-indigo-600 border border-slate-600 hover:border-indigo-500 flex items-center justify-center transition-all shadow-sm z-10"
        title={collapsed ? 'Expandir' : 'Colapsar'}
      >
        {collapsed
          ? <ChevronRight size={12} className="text-slate-300" />
          : <ChevronLeft size={12} className="text-slate-300" />
        }
      </button>
    </aside>
  );
}
