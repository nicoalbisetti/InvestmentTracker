import { useEffect, useRef, useState } from 'react';
import { getTickerQuotes, TickerItem } from '../api/ticker';

const POLL_INTERVAL = 5 * 60 * 1000; // 5 minutos

function formatPrice(price: number, currency: 'BRL' | 'USD'): string {
  if (currency === 'BRL') {
    return `R$ ${price.toFixed(2).replace('.', ',')}`;
  }
  return `US$ ${price.toFixed(2)}`;
}

function TickerItemDisplay({ item }: { item: TickerItem }) {
  const isPositive = item.change_pct > 0;
  const isNegative = item.change_pct < 0;
  const arrow = isPositive ? '▲' : isNegative ? '▼' : '▬';
  const changeClass = isPositive
    ? 'text-emerald-400'
    : isNegative
    ? 'text-red-400'
    : 'text-gray-400';
  const sign = isPositive ? '+' : '';
  const changePct = `${sign}${item.change_pct.toFixed(2).replace('.', ',')}%`;

  return (
    <span className="inline-flex items-center gap-1.5 px-12">
      <span className="text-white font-semibold">{item.ticker}</span>
      <span className="text-gray-300">{formatPrice(item.price, item.currency)}</span>
      <span className={changeClass}>
        {arrow} {changePct}
      </span>
    </span>
  );
}

export default function TickerBand() {
  const [items, setItems] = useState<TickerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchQuotes = () => {
    getTickerQuotes()
      .then(res => {
        setItems(res.items);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchQuotes();
    intervalRef.current = setInterval(fetchQuotes, POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  if (loading) {
    return (
      <div className="w-full h-9 bg-gray-900 animate-pulse" />
    );
  }

  if (items.length === 0) {
    return null;
  }

  const duration = 20 + items.length * 3;
  const doubled = [...items, ...items];

  return (
    <div
      className="w-full h-9 bg-gray-900 overflow-hidden flex items-center"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className="flex whitespace-nowrap text-xs"
        style={{
          animation: `ticker-scroll ${duration}s linear infinite`,
          animationPlayState: hovered ? 'paused' : 'running',
        }}
      >
        {doubled.map((item, i) => (
          <TickerItemDisplay key={i} item={item} />
        ))}
      </div>
      <style>{`
        @keyframes ticker-scroll {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}
