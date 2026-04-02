import { createContext, useContext, useState, ReactNode } from 'react';

type Env = 'production' | 'demo';

interface EnvContextType {
  env: Env;
  toggleEnv: () => void;
}

const EnvContext = createContext<EnvContextType>({ env: 'production', toggleEnv: () => {} });

export function EnvProvider({ children }: { children: ReactNode }) {
  const [env, setEnv] = useState<Env>(() => {
    return (localStorage.getItem('app_env') as Env) || 'production';
  });

  const toggleEnv = () => {
    const next: Env = env === 'demo' ? 'production' : 'demo';
    localStorage.setItem('app_env', next);
    setEnv(next);
    window.location.reload();
  };

  return <EnvContext.Provider value={{ env, toggleEnv }}>{children}</EnvContext.Provider>;
}

export const useEnv = () => useContext(EnvContext);
