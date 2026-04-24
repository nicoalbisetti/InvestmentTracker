import { useState, useRef, useEffect } from 'react';
import { X, ChevronDown, Search } from 'lucide-react';

interface Instrument {
  id: number;
  name: string;
  custodian: string;
}

interface Props {
  value: number | '';
  onChange: (id: number | '') => void;
  instruments: Instrument[];
  placeholder?: string;
  disabled?: boolean;
}

export default function InstrumentCombobox({
  value,
  onChange,
  instruments,
  placeholder = 'Buscar instrumento...',
  disabled = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = instruments.find(i => i.id === value) ?? null;

  const filtered = instruments.filter(i => {
    const q = search.toLowerCase();
    return i.name.toLowerCase().includes(q) || i.custodian.toLowerCase().includes(q);
  });

  useEffect(() => {
    if (open) {
      setSearch('');
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleSelect = (id: number) => {
    onChange(id);
    setOpen(false);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange('');
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen(o => !o)}
        className="input flex items-center justify-between w-full text-left gap-2 pr-2"
      >
        <span className={`truncate flex-1 ${!selected ? 'text-gray-400' : ''}`}>
          {selected ? selected.name : placeholder}
        </span>
        <span className="flex items-center gap-1 shrink-0">
          {selected && !disabled && (
            <span
              onClick={handleClear}
              className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 cursor-pointer"
            >
              <X size={13} className="text-gray-400" />
            </span>
          )}
          <ChevronDown size={14} className="text-gray-400" />
        </span>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
          <div className="p-2 border-b border-gray-100 dark:border-gray-800 flex items-center gap-2">
            <Search size={13} className="text-gray-400 shrink-0" />
            <input
              ref={inputRef}
              type="text"
              className="text-sm bg-transparent outline-none w-full placeholder-gray-400"
              placeholder="Buscar..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <ul className="overflow-y-auto" style={{ maxHeight: 200 }}>
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-gray-400">Sin resultados</li>
            ) : (
              filtered.map(i => (
                <li
                  key={i.id}
                  onClick={() => handleSelect(i.id)}
                  className={`flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 ${
                    value === i.id ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''
                  }`}
                >
                  <span className="text-sm font-medium truncate">{i.name}</span>
                  <span className="text-xs text-gray-400 ml-2 shrink-0">{i.custodian}</span>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
