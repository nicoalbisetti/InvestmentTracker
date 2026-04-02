import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { EnvProvider } from './context/EnvContext';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Positions from './pages/Positions';
import History from './pages/History';
import Annual from './pages/Annual';
import Proventos from './pages/Proventos';
import Transactions from './pages/Transactions';
import Settings from './pages/Settings';
import ImportFixedIncome from './pages/ImportFixedIncome';
import ImportProventos from './pages/ImportProventos';
import EquityTrades from './pages/EquityTrades';

export default function App() {
  return (
    <EnvProvider>
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="positions" element={<Positions />} />
            <Route path="history" element={<History />} />
            <Route path="annual" element={<Annual />} />
            <Route path="proventos" element={<Proventos />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="settings" element={<Settings />} />
            <Route path="import/fixed-income" element={<ImportFixedIncome />} />
            <Route path="import/proventos" element={<ImportProventos />} />
            <Route path="equity-trades" element={<EquityTrades />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
    </EnvProvider>
  );
}
