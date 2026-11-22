'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { 
  HardHat, 
  Lock, 
  Mail, 
  Sparkles, 
  ArrowRight, 
  Send, 
  CheckCircle2, 
  Cpu
} from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { user, login, register, loginDemo } = useAuth();

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loadingAction, setLoadingAction] = useState(false);

  // Si ya está logueado, redirigir a presupuestos
  React.useEffect(() => {
    if (user) {
      router.replace('/presupuestos');
    }
  }, [user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    if (!email || !password) {
      setErrorMsg('Por favor completa correo y contraseña.');
      return;
    }

    setLoadingAction(true);
    const res = mode === 'login' 
      ? await login(email, password)
      : await register(email, password);

    setLoadingAction(false);
    if (!res.success) {
      setErrorMsg(res.error || 'Ocurrió un error');
    } else {
      router.push('/presupuestos');
    }
  };

  const handleDemoLogin = async () => {
    setLoadingAction(true);
    await loginDemo();
    setLoadingAction(false);
    router.push('/presupuestos');
  };

  return (
    <div className="min-h-screen bg-[#070b12] text-zinc-100 flex flex-col justify-center items-center px-4 py-12">
      {/* Background Glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-orange-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo and Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-orange-600 text-white shadow-xl shadow-orange-600/30 mb-4">
            <HardHat className="w-8 h-8" />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-white">ObraExacta</h1>
          <p className="text-zinc-400 text-sm mt-1">Control Determinista para Contratistas y Cuadrillas</p>
        </div>

        {/* Card */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-6 shadow-2xl backdrop-blur-md">
          {/* Quick Demo Access Button (Recommended) */}
          <div className="mb-6 p-4 rounded-xl bg-gradient-to-r from-orange-950/40 via-zinc-900 to-amber-950/30 border border-orange-500/30">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <h3 className="text-xs font-bold text-orange-300 uppercase tracking-wider">Acceso Instantáneo de Prueba</h3>
                <p className="text-xs text-zinc-400 mt-0.5">Explora todas las funciones sin registrarte ni validar correo.</p>
                <button
                  type="button"
                  onClick={handleDemoLogin}
                  disabled={loadingAction}
                  className="mt-3 w-full py-2.5 px-4 rounded-lg bg-orange-600 hover:bg-orange-500 text-white font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-orange-600/20 transition-all cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  Entrar como Cuenta Demo
                  <ArrowRight className="w-4 h-4 ml-auto" />
                </button>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 mb-6 text-zinc-500 text-xs font-medium">
            <div className="h-px bg-zinc-800 flex-1" />
            <span>O ingresa con tu cuenta</span>
            <div className="h-px bg-zinc-800 flex-1" />
          </div>

          {/* Mode Tabs */}
          <div className="flex rounded-lg bg-zinc-950 p-1 border border-zinc-800 mb-6">
            <button
              type="button"
              onClick={() => { setMode('login'); setErrorMsg(''); }}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                mode === 'login' ? 'bg-zinc-800 text-white shadow' : 'text-zinc-400 hover:text-white'
              }`}
            >
              Iniciar Sesión
            </button>
            <button
              type="button"
              onClick={() => { setMode('register'); setErrorMsg(''); }}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                mode === 'register' ? 'bg-zinc-800 text-white shadow' : 'text-zinc-400 hover:text-white'
              }`}
            >
              Crear Cuenta
            </button>
          </div>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-lg bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
              {errorMsg}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Correo Electrónico
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ingeniero@constructora.com"
                  className="w-full pl-9 pr-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-orange-500 transition-colors"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Contraseña
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-orange-500 transition-colors"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loadingAction}
              className="w-full py-2.5 px-4 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-all cursor-pointer mt-2"
            >
              {loadingAction ? (
                <span>Procesando...</span>
              ) : mode === 'login' ? (
                <>
                  <span>Entrar al Dashboard</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              ) : (
                <>
                  <span>Registrar Cuenta</span>
                  <CheckCircle2 className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Feature Highlights */}
          <div className="mt-6 pt-5 border-t border-zinc-800/80 space-y-2 text-[11px] text-zinc-400">
            <div className="flex items-center gap-2">
              <Send className="w-3.5 h-3.5 text-emerald-400" />
              <span>Código personal para vincular el bot de Telegram</span>
            </div>
            <div className="flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-blue-400" />
              <span>API Key para conectar agentes MCP (Cursor / Antigravity)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
