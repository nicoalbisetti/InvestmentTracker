import { useState, useEffect, useRef } from 'react';
import {
  fetchSimulation,
  SimulationParams,
  SimulationResult,
  DEFAULT_PARAMS,
} from '../api/simulation';

export function useSimulation() {
  const [params, setParams] = useState<SimulationParams>(DEFAULT_PARAMS);
  const [data, setData] = useState<SimulationResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setIsLoading(true);
      setError(null);
      fetchSimulation(params)
        .then((result) => {
          setData(result);
          setIsLoading(false);
        })
        .catch((err) => {
          setError(err?.response?.data?.detail ?? err.message ?? 'Error loading simulation');
          setIsLoading(false);
        });
    }, 400);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [params]);

  const resetDefaults = () => setParams(DEFAULT_PARAMS);

  return { data, isLoading, error, params, setParams, resetDefaults };
}
