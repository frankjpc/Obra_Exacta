'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { supabase } from './supabase';
import { api } from './api';
import { AuthUser, PerfilTelegram } from './types';

interface AuthContextType {
  user: AuthUser | null;
  perfil: PerfilTelegram | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  loginDemo: () => Promise<void>;
  logout: () => Promise<void>;
  refreshPerfil: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const DEMO_USER: AuthUser = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'demo@obraexacta.com',
  is_demo: true,
};

const SESSION_STORAGE_KEY = 'obraexacta_user_session';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [perfil, setPerfil] = useState<PerfilTelegram | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchPerfil = useCallback(async (userId: string) => {
    try {
      const p = await api.getPerfil(userId);
      if (p) {
        setPerfil(p);
      }
    } catch (e) {
      console.warn('No se pudo cargar el perfil del usuario:', e);
    }
  }, []);

  const refreshPerfil = useCallback(async () => {
    if (user?.id) {
      await fetchPerfil(user.id);
    }
  }, [user, fetchPerfil]);

  // Inicializar sesión desde Supabase Auth o LocalStorage
  useEffect(() => {
    let mounted = true;

    async function initSession() {
      try {
        // 1. Revisar sesión en Supabase si está disponible
        if (supabase) {
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.user && mounted) {
            const authUser: AuthUser = {
              id: session.user.id,
              email: session.user.email || 'usuario@obraexacta.com',
              is_demo: false,
            };
            setUser(authUser);
            await fetchPerfil(authUser.id);
            setLoading(false);
            return;
          }
        }

        // 2. Revisar si hay sesión demo en localStorage
        if (typeof window !== 'undefined') {
          const saved = localStorage.getItem(SESSION_STORAGE_KEY);
          if (saved && mounted) {
            try {
              const parsed = JSON.parse(saved) as AuthUser;
              setUser(parsed);
              await fetchPerfil(parsed.id);
              setLoading(false);
              return;
            } catch {
              localStorage.removeItem(SESSION_STORAGE_KEY);
            }
          }
        }
      } catch (err) {
        console.error('Error al inicializar sesión:', err);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    initSession();

    // Listener para cambios de sesión en Supabase
    if (supabase) {
      const { data: { subscription } } = supabase.auth.onAuthStateChange(
        async (_event, session) => {
          if (!mounted) return;
          if (session?.user) {
            const authUser: AuthUser = {
              id: session.user.id,
              email: session.user.email || 'usuario@obraexacta.com',
              is_demo: false,
            };
            setUser(authUser);
            localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(authUser));
            await fetchPerfil(authUser.id);
          }
        }
      );

      return () => {
        mounted = false;
        subscription.unsubscribe();
      };
    }

    return () => {
      mounted = false;
    };
  }, [fetchPerfil]);

  const loginDemo = async () => {
    setLoading(true);
    setUser(DEMO_USER);
    if (typeof window !== 'undefined') {
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(DEMO_USER));
    }
    await fetchPerfil(DEMO_USER.id);
    setLoading(false);
  };

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    setLoading(true);
    try {
      if (supabase) {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) {
          setLoading(false);
          return { success: false, error: error.message };
        }
        if (data.user) {
          const authUser: AuthUser = {
            id: data.user.id,
            email: data.user.email || email,
            is_demo: false,
          };
          setUser(authUser);
          localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(authUser));
          await fetchPerfil(authUser.id);
          setLoading(false);
          return { success: true };
        }
      }

      // Fallback si Supabase no está conectado
      const fallbackUser: AuthUser = {
        id: 'user-' + btoa(email).substring(0, 12).toLowerCase(),
        email: email,
        is_demo: false,
      };
      setUser(fallbackUser);
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(fallbackUser));
      await fetchPerfil(fallbackUser.id);
      setLoading(false);
      return { success: true };
    } catch (err: any) {
      setLoading(false);
      return { success: false, error: err?.message || 'Error al iniciar sesión' };
    }
  };

  const register = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    setLoading(true);
    try {
      if (supabase) {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) {
          setLoading(false);
          return { success: false, error: error.message };
        }
        if (data.user) {
          const authUser: AuthUser = {
            id: data.user.id,
            email: data.user.email || email,
            is_demo: false,
          };
          setUser(authUser);
          localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(authUser));
          await fetchPerfil(authUser.id);
          setLoading(false);
          return { success: true };
        }
      }

      // Fallback
      return await login(email, password);
    } catch (err: any) {
      setLoading(false);
      return { success: false, error: err?.message || 'Error al registrar usuario' };
    }
  };

  const logout = async () => {
    if (supabase) {
      try {
        await supabase.auth.signOut();
      } catch (e) {
        console.warn('Error cerrando sesión en Supabase:', e);
      }
    }
    if (typeof window !== 'undefined') {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
    setUser(null);
    setPerfil(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        perfil,
        loading,
        login,
        register,
        loginDemo,
        logout,
        refreshPerfil,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de un AuthProvider');
  }
  return context;
}
