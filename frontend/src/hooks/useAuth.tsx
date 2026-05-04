/**
 * Auth context — cookie-based session management.
 *
 * Token storage strategy
 * ----------------------
 * The JWT is kept exclusively in an httpOnly cookie managed by the
 * backend.  This file never reads or writes `localStorage` for auth
 * purposes, eliminating the XSS-based token theft vector.
 *
 * Session rehidration
 * -------------------
 * On mount, AuthProvider calls GET /auth/me.  If the httpOnly cookie is
 * still valid the backend returns the user profile; otherwise it returns
 * 401 and the provider leaves `user` as null (redirecting to login).
 *
 * Logout
 * ------
 * `logout()` calls POST /auth/logout so the backend can expire the
 * httpOnly cookie (JS cannot delete it directly).
 */
import {
  useState,
  useEffect,
  createContext,
  useContext,
  useCallback,
} from 'react';
import type { ReactNode } from 'react';
import client from '../api/client';

export type Role = 'SUPER_ADMIN' | 'ADMIN' | 'MANAGER' | 'AGENT';

export interface User {
  id: string;
  email: string;
  fullName?: string;
  role: Role;
  tenantId: string | null;
  mustChangePassword?: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  /** Call after a successful login to persist the user profile in context. */
  login: (userData: User) => void;
  /** Expires the server-side cookie and clears local state. */
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: try to rehidrate from the server via /auth/me.
  // This works as long as the httpOnly cookie is still valid.
  useEffect(() => {
    client
      .get<{
        id: string;
        email: string;
        full_name: string;
        role: Role;
        tenant_id: string | null;
        must_change_password: boolean;
      }>('/auth/me')
      .then(({ data }) => {
        setUser({
          id: data.id,
          email: data.email,
          fullName: data.full_name,
          role: data.role,
          tenantId: data.tenant_id,
          mustChangePassword: data.must_change_password,
        });
      })
      .catch(() => {
        // 401 means no valid session — stay logged out
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback((userData: User) => {
    // The JWT cookie is already set by the backend response.
    // We only need to store the user profile in React state.
    setUser(userData);
  }, []);

  const logout = useCallback(async () => {
    try {
      // Ask the backend to expire the httpOnly cookie.
      await client.post('/auth/logout');
    } catch {
      // Even if the request fails, clear local state.
    } finally {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
