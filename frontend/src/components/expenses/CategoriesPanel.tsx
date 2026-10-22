import { useCallback, useEffect, useState } from 'react';
import { apiErrorDetail, createCategory, ExpCategory, getCategories } from '../../api/expenses';

export default function CategoriesPanel() {
  const [cats, setCats] = useState<ExpCategory[]>([]);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const load = useCallback(() => { getCategories().then(setCats).catch(() => {}); }, []);
  useEffect(load, [load]);

  const add = async () => {
    setError('');
    if (!name.trim()) return;
    try { await createCategory(name.trim()); setName(''); load(); }
    catch (e) { const st = apiErrorDetail(e); setError(st.status === 409 ? 'Ya existe esa categoría' : 'No se pudo crear'); }
  };
  return (
    <div className="space-y-3">
      <div className="card p-3 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1"><label className="text-xs text-gray-500">Nueva categoría</label>
          <input className="input text-sm py-1.5" value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && add()} /></div>
        <button className="btn-primary text-sm py-1.5" onClick={add}>Agregar</button>
        {error && <span className="text-xs text-rose-500">{error}</span>}
      </div>
      <div className="card flex flex-wrap gap-2">
        {cats.map(c => <span key={c.id} className={`badge ${c.is_system ? 'bg-slate-100 text-slate-600' : 'bg-indigo-50 text-indigo-700'}`} title={c.is_system ? 'Categoría de sistema' : ''}>{c.name}</span>)}
      </div>
    </div>
  );
}
