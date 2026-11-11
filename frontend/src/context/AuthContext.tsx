import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, loginAdmin, governanceRequest } from '../api/client';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY_USER = 'anpr_auth_user';
const STORAGE_KEY_TOKEN = 'anpr_auth_token';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    if (!localStorage.getItem(STORAGE_KEY_TOKEN)) { setLoading(false); return; }
    governanceRequest<User>('auth/me').then(current => {
      if (active) { setUser(current); localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(current)); }
    }).catch(() => {
      localStorage.removeItem(STORAGE_KEY_USER); localStorage.removeItem(STORAGE_KEY_TOKEN);
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      localStorage.removeItem(STORAGE_KEY_USER);
      localStorage.removeItem(STORAGE_KEY_TOKEN);
    };
    window.addEventListener('justmeter:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('justmeter:unauthorized', handleUnauthorized);
  }, []);

  const login = async (email: string, pass: string) => {
    const data = await loginAdmin(email, pass);
    setUser(data.user);
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(data.user));
    localStorage.setItem(STORAGE_KEY_TOKEN, data.token);
  };

  const logout = () => {
    governanceRequest('auth/logout', 'POST').then(() => {
      setUser(null);
      localStorage.removeItem(STORAGE_KEY_USER);
      localStorage.removeItem(STORAGE_KEY_TOKEN);
    }).catch(error => window.alert(`Could not revoke the session: ${error.message}`));
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
