import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

export interface ComboOption { value: string; label: string }

const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

interface Props {
  options: ComboOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Texto de la opción vacía (si se define, se puede limpiar la selección). */
  clearLabel?: string;
  className?: string;
  disabled?: boolean;
  title?: string;
}

/** Selector con búsqueda (sin acentos ni mayúsculas) y teclado. El menú es `fixed` para no quedar recortado en tablas con scroll. */
export default function Combobox({ options, value, onChange, placeholder = 'Elegir…', clearLabel, className = '', disabled, title }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [pos, setPos] = useState({ left: 0, top: 0, width: 0 });
  const inputRef = useRef<HTMLInputElement>(null);
  const selected = options.find(o => o.value === value);

  const shown = useMemo(() => {
    const q = norm(query.trim());
    const list = q ? options.filter(o => norm(o.label).includes(q)) : options;
    return list.slice(0, 100);
  }, [options, query]);

  useLayoutEffect(() => {
    if (!open || !inputRef.current) return;
    const r = inputRef.current.getBoundingClientRect();
    setPos({ left: r.left, top: r.bottom + 2, width: Math.max(r.width, 180) });
  }, [open, query]);

  useEffect(() => { setActive(0); }, [query, open]);

  const choose = (v: string) => { onChange(v); setOpen(false); setQuery(''); };
  const items: ComboOption[] = clearLabel ? [{ value: '', label: clearLabel }, ...shown] : shown;

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive(a => Math.min(a + 1, items.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(a - 1, 0)); }
    else if (e.key === 'Enter' && open && items[active]) { e.preventDefault(); choose(items[active].value); }
    else if (e.key === 'Escape') { setOpen(false); setQuery(''); }
  };

  return (
    <div className={`relative ${className}`}>
      <input
        ref={inputRef} className="input text-xs py-1 w-full" disabled={disabled} title={title}
        value={open ? query : selected?.label ?? ''} placeholder={selected ? selected.label : placeholder}
        onFocus={() => setOpen(true)} onChange={e => { setQuery(e.target.value); setOpen(true); }}
        onBlur={() => { setOpen(false); setQuery(''); }} onKeyDown={onKey}
      />
      {open && (
        <ul className="fixed z-50 max-h-60 overflow-auto rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg text-xs"
          style={{ left: pos.left, top: pos.top, width: pos.width }}>
          {items.length === 0 && <li className="px-3 py-2 text-slate-400">Sin resultados</li>}
          {items.map((o, i) => (
            <li key={o.value || '__clear'}
              className={`px-3 py-1.5 cursor-pointer ${i === active ? 'bg-indigo-50 dark:bg-indigo-900/30' : ''} ${o.value === value ? 'font-semibold' : ''} ${o.value === '' ? 'text-slate-400' : ''}`}
              onMouseDown={e => { e.preventDefault(); choose(o.value); }} onMouseEnter={() => setActive(i)}>
              {o.label}
            </li>))}
        </ul>
      )}
    </div>
  );
}
