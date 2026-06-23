import { useSimulation } from '../hooks/useSimulation';
import SimulationControls from '../components/SimulationControls';
import SimulationChart from '../components/SimulationChart';
import SimulationSummary from '../components/SimulationSummary';

export default function SimulationPage() {
  const { data, isLoading, error, params, setParams, resetDefaults } = useSimulation();

  function handleRetry() {
    setParams({ ...params });
  }

  const snapshotLabel = data?.snapshot_date
    ? (() => {
        const [y, m] = data.snapshot_date.split('-');
        const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
        return `${months[parseInt(m) - 1]} ${y}`;
      })()
    : '—';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-white">Simulación de Cartera</h1>
        <p className="text-sm text-slate-500 mt-0.5">Snapshot: {snapshotLabel}</p>
      </div>

      {/* Two-column layout */}
      <div className="flex flex-col md:flex-row gap-6 items-start">
        {/* Left: controls */}
        <div className="w-full md:w-72 shrink-0">
          <SimulationControls params={params} onChange={setParams} onReset={resetDefaults} />
        </div>

        {/* Right: summary + chart */}
        <div className="flex-1 min-w-0 space-y-4">
          <SimulationSummary result={data} params={params} isLoading={isLoading} />
          <SimulationChart
            data={data?.data ?? []}
            isLoading={isLoading}
            error={error}
            onRetry={handleRetry}
          />
        </div>
      </div>
    </div>
  );
}
