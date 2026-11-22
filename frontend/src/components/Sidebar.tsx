'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { 
  Calculator, 
  ShoppingCart, 
  TrendingUp, 
  FileText, 
  ChevronLeft, 
  ChevronRight, 
  HardHat, 
  Send, 
  Radio, 
  Copy, 
  Check, 
  Key, 
  User, 
  LogOut, 
  Sparkles 
} from 'lucide-react';
import { Obra } from '@/lib/types';
import { useAuth } from '@/lib/auth-context';

interface SidebarProps {
  obraActiva: Obra | null;
  telegramStatus?: {
    status: string;
    polling: boolean;
  };
}

export default function Sidebar({ obraActiva }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [copiedTg, setCopiedTg] = useState(false);
  const [copiedMcp, setCopiedMcp] = useState(false);
  const [copiedMcpUrl, setCopiedMcpUrl] = useState(false);
  const [currentOrigin, setCurrentOrigin] = useState('http://localhost:8000');
  const pathname = usePathname();
  const router = useRouter();
  const { user, perfil, logout } = useAuth();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setCurrentOrigin(window.location.origin);
    }
  }, []);

  // No mostrar sidebar en la ruta pública móvil de aprobación del cliente ni en login
  if (pathname.startsWith('/aprobar') || pathname.startsWith('/login')) {
    return null;
  }

  const navItems = [
    {
      name: 'Presupuestos (Voz / Telegram)',
      href: '/presupuestos',
      icon: Calculator,
      badge: '6 Col.'
    },
    {
      name: 'Compras y Gastos',
      href: '/compras',
      icon: ShoppingCart,
      badge: 'Auditoría'
    },
    {
      name: 'Avance por Partida',
      href: '/avance',
      icon: TrendingUp,
      badge: '0-100%'
    },
    {
      name: 'Libro de Obra y Adicionales',
      href: '/libro-de-obra',
      icon: FileText,
      badge: 'Link Móvil'
    }
  ];

  const codigoTg = perfil?.codigo_vinculacion || '482910';
  const comandoTg = `/vincular ${codigoTg}`;
  const apiKeyMcp = perfil?.api_key_mcp || 'obx_mcp_demo_7f8a9b2c3d4e5f6a';
  const mcpEndpointUrl = `${currentOrigin}/mcp/sse`;

  const handleCopyTg = () => {
    navigator.clipboard.writeText(comandoTg);
    setCopiedTg(true);
    setTimeout(() => setCopiedTg(false), 2000);
  };

  const handleCopyMcp = () => {
    navigator.clipboard.writeText(apiKeyMcp);
    setCopiedMcp(true);
    setTimeout(() => setCopiedMcp(false), 2000);
  };

  const handleCopyMcpUrl = () => {
    navigator.clipboard.writeText(mcpEndpointUrl);
    setCopiedMcpUrl(true);
    setTimeout(() => setCopiedMcpUrl(false), 2000);
  };

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  return (
    <aside 
      className={`h-screen sticky top-0 flex flex-col justify-between border-r border-zinc-800 bg-[#070b12] text-zinc-200 transition-all duration-300 z-40 select-none ${
        collapsed ? 'w-20' : 'w-72'
      }`}
    >
      {/* Top Section */}
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {/* Top Header */}
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          {!collapsed ? (
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-orange-600 flex items-center justify-center font-black text-white text-xl shadow-lg shadow-orange-600/20">
                <HardHat className="w-6 h-6" />
              </div>
              <div>
                <span className="font-extrabold text-lg text-white tracking-tight">ObraExacta</span>
                <p className="text-[10px] text-zinc-400 font-medium uppercase tracking-wider">Control Determinista</p>
              </div>
            </div>
          ) : (
            <div className="w-10 h-10 mx-auto rounded-lg bg-orange-600 flex items-center justify-center text-white">
              <HardHat className="w-6 h-6" />
            </div>
          )}

          <button 
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white transition cursor-pointer"
            title={collapsed ? "Expandir Menú" : "Colapsar Menú"}
          >
            {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
          </button>
        </div>

        {/* Telegram Bot Live Indicator */}
        <div className={`p-3 mx-2 my-3 rounded-lg border border-emerald-900/50 bg-emerald-950/20 ${collapsed ? 'text-center' : ''}`}>
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                    <Send className="w-3 h-3" /> Bot Telegram Activo
                  </span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                    Polling
                  </span>
                </div>
                <p className="text-[10px] text-zinc-400 truncate mt-0.5">Escuchando audio, fotos y texto</p>
              </div>
            )}
          </div>
        </div>

        {/* Navigation List */}
        <nav className="px-2 space-y-1.5 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={obraActiva ? `${item.href}?obra_id=${obraActiva.id}` : item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive 
                    ? 'bg-zinc-800 text-white font-semibold border-l-4 border-orange-500 pl-2' 
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                }`}
                title={collapsed ? item.name : undefined}
              >
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? 'text-orange-400' : 'text-zinc-400'}`} />
                {!collapsed && (
                  <div className="flex items-center justify-between w-full">
                    <span className="truncate">{item.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                      {item.badge}
                    </span>
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Integraciones Copiables: Telegram + MCP */}
        {!collapsed && (
          <div className="px-2 mt-4 space-y-3">
            {/* Telegram Linking Box */}
            <div className="p-2.5 rounded-xl bg-zinc-900/70 border border-zinc-800 hover:border-zinc-700 transition">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-bold text-zinc-300 flex items-center gap-1.5">
                  <Send className="w-3.5 h-3.5 text-blue-400" /> Vinculación Telegram
                </span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-medium ${
                  perfil?.telegram_chat_id 
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/60'
                    : 'bg-amber-950/60 text-amber-400 border border-amber-800/60'
                }`}>
                  {perfil?.telegram_chat_id ? 'Vinculado' : 'Pendiente'}
                </span>
              </div>
              <p className="text-[10px] text-zinc-400 mb-2 leading-relaxed">
                Envía este comando al bot para sincronizar este chat:
              </p>
              <div className="flex items-center justify-between bg-zinc-950 px-2.5 py-1.5 rounded-lg border border-zinc-800 group">
                <code className="text-xs text-orange-400 font-mono font-semibold tracking-wider">
                  {comandoTg}
                </code>
                <button
                  onClick={handleCopyTg}
                  className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white transition cursor-pointer"
                  title="Copiar comando de vinculación"
                >
                  {copiedTg ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* MCP API Key & Endpoint Box */}
            <div className="p-2.5 rounded-xl bg-zinc-900/70 border border-zinc-800 hover:border-zinc-700 transition">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-bold text-zinc-300 flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-purple-400" /> Servidor MCP
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/60 font-mono">
                  Gemini / AGY
                </span>
              </div>
              
              {/* Endpoint SSE */}
              <div className="mb-2">
                <span className="text-[9px] text-zinc-400 block mb-1">URL Endpoint (SSE):</span>
                <div className="flex items-center justify-between bg-zinc-950 px-2 py-1 rounded-lg border border-zinc-800 group">
                  <code className="text-[10px] text-purple-300 font-mono truncate max-w-[170px]">
                    {mcpEndpointUrl}
                  </code>
                  <button
                    onClick={handleCopyMcpUrl}
                    className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white transition cursor-pointer shrink-0"
                    title="Copiar URL Endpoint MCP"
                  >
                    {copiedMcpUrl ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              {/* API Key */}
              <div>
                <span className="text-[9px] text-zinc-400 block mb-1">API Key personal:</span>
                <div className="flex items-center justify-between bg-zinc-950 px-2 py-1 rounded-lg border border-zinc-800 group">
                  <code className="text-[10px] text-zinc-300 font-mono truncate max-w-[170px]">
                    {apiKeyMcp}
                  </code>
                  <button
                    onClick={handleCopyMcp}
                    className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white transition cursor-pointer shrink-0"
                    title="Copiar API Key MCP"
                  >
                    {copiedMcp ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Section: Obra Activa & User Profile */}
      <div className="border-t border-zinc-800/80 bg-zinc-950/60">
        {!collapsed && (
          <div className="p-2.5 mx-2 my-2 rounded-xl bg-zinc-900/60 border border-zinc-800/80">
            <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
              <span className="flex items-center gap-1 font-semibold uppercase tracking-wider text-[10px] text-orange-400">
                <Radio className="w-3 h-3 animate-pulse" /> Obra en Pantalla
              </span>
              <span className="text-[10px] px-1.5 py-0.2 bg-zinc-800 rounded font-mono text-zinc-300">
                {obraActiva?.tasa_bcv ? `${obraActiva.tasa_bcv.toFixed(2)} Bs/$` : '918.77 Bs/$'}
              </span>
            </div>
            <p className="font-semibold text-white text-xs truncate">
              {obraActiva ? obraActiva.nombre : 'Cargando obra...'}
            </p>
            <p className="text-[11px] text-zinc-400 truncate">
              {obraActiva?.cliente || 'Cliente'}
            </p>
          </div>
        )}

        {/* User Account / Profile Footer */}
        <div className="p-3 flex items-center justify-between">
          {!collapsed ? (
            <div className="flex items-center gap-2.5 min-w-0 flex-1">
              <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0 text-zinc-300">
                <User className="w-4 h-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <p className="text-xs font-semibold text-zinc-200 truncate">
                    {user?.email || 'demo@obraexacta.com'}
                  </p>
                  {user?.is_demo && (
                    <span className="text-[9px] px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono">
                      Demo
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-zinc-400 truncate">
                  {user?.id ? `ID: ${user.id.substring(0, 8)}...` : 'Autenticado'}
                </p>
              </div>
              <button
                onClick={handleLogout}
                className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-red-400 transition cursor-pointer"
                title="Cerrar sesión"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={handleLogout}
              className="w-10 h-10 mx-auto rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-red-400 flex items-center justify-center transition cursor-pointer"
              title={`Cerrar sesión (${user?.email || 'demo'})`}
            >
              <LogOut className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
