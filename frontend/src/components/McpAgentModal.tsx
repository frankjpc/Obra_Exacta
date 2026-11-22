'use client';

import React, { useState } from 'react';
import { 
  Bot, 
  X, 
  Send, 
  Sparkles, 
  Wrench, 
  CheckCircle2, 
  Code, 
  ChevronDown, 
  ChevronUp,
  Loader2,
  Building2,
  DollarSign,
  Calculator,
  Layers
} from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

interface McpAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
  obraActivaNombre?: string;
}

interface MessageHistory {
  role: 'user' | 'assistant';
  text: string;
  toolCalled?: string | null;
  toolArgs?: Record<string, any>;
  toolResult?: Record<string, any>;
}

export default function McpAgentModal({ isOpen, onClose, obraActivaNombre }: McpAgentModalProps) {
  const { perfil } = useAuth();
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [showJson, setShowJson] = useState<number | null>(null);
  
  const [messages, setMessages] = useState<MessageHistory[]>([
    {
      role: 'assistant',
      text: '¡Hola! Soy tu Asistente Técnico y Financiero impulsado por **Gemini 2.5 Flash** y conectado a tu **Servidor MCP de ObraExacta**.\n\nPuedo consultar tus obras, leer tus precios aprendidos, evaluar levantamientos bajo la norma COVENIN y auditar gastos en tiempo real.',
    }
  ]);

  if (!isOpen) return null;

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || prompt).trim();
    if (!query || loading) return;

    setPrompt('');
    setMessages(prev => [...prev, { role: 'user', text: query }]);
    setLoading(true);

    try {
      const apiKeyMcp = perfil?.api_key_mcp || 'obx_mcp_demo_7f8a9b2c3d4e5f6a7b8c9d0e';
      const data = await api.mcpChat(query, apiKeyMcp);

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: data.response || 'Sin respuesta.',
          toolCalled: data.tool_called,
          toolArgs: data.tool_args,
          toolResult: data.tool_result
        }
      ]);
    } catch (e: any) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          text: `❌ Error al conectar con el servidor MCP: ${e.message || 'Error desconocido'}`
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sugerencias = [
    {
      label: 'Listar Obras y Margen',
      icon: Building2,
      query: '¿Cuáles son las obras activas que tengo y cuánto presupuesto tengo disponible?'
    },
    {
      label: 'Catálogo COVENIN',
      icon: Layers,
      query: '¿Qué precios unitarios y partidas COVENIN tenemos vigentes?'
    },
    {
      label: 'Cotizar Pared de Bloque',
      icon: Calculator,
      query: `Cotízame una pared de bloques de 15cm de 10 metros de largo por 3 de alto en la obra ${obraActivaNombre || 'Galpón Central'} con eso basta calcula ya`
    },
    {
      label: 'Resumen Financiero',
      icon: DollarSign,
      query: `Dame el resumen financiero, partidas y gastos de la obra ${obraActivaNombre || 'Galpón Central'}`
    }
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl bg-zinc-950 border border-purple-500/30 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-950/80 border border-purple-500/40 flex items-center justify-center text-purple-400 shadow-inner">
              <Bot className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-white text-base">Agente IA de Obra</h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800 flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-purple-400" /> Gemini + MCP
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                Conectado a <code className="text-purple-300 font-mono text-[11px]">{typeof window !== 'undefined' ? `${window.location.origin}/mcp/sse` : 'http://localhost:8000/mcp/sse'}</code>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mensajes / Chat Scroll */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-purple-600 text-white rounded-br-none shadow-md'
                    : 'bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-bl-none'
                }`}
              >
                {/* Badge de Herramienta MCP ejecutada */}
                {m.toolCalled && (
                  <div className="mb-2.5 pb-2.5 border-b border-zinc-800">
                    <div className="flex items-center justify-between text-xs font-mono text-purple-300 bg-purple-950/70 px-2.5 py-1.5 rounded-lg border border-purple-800/60">
                      <span className="flex items-center gap-1.5">
                        <Wrench className="w-3.5 h-3.5 text-purple-400" />
                        Herramienta MCP: <strong>{m.toolCalled}</strong>
                      </span>
                      <button
                        onClick={() => setShowJson(showJson === idx ? null : idx)}
                        className="text-[11px] text-zinc-400 hover:text-white flex items-center gap-0.5 cursor-pointer"
                      >
                        <Code className="w-3 h-3" />
                        {showJson === idx ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>
                    </div>

                    {/* Drawer con JSON de la herramienta */}
                    {showJson === idx && (
                      <pre className="mt-2 p-2.5 rounded bg-zinc-950 border border-zinc-800 text-[11px] font-mono text-emerald-400 max-h-48 overflow-y-auto whitespace-pre-wrap">
                        {JSON.stringify(m.toolResult, null, 2)}
                      </pre>
                    )}
                  </div>
                )}

                <div className="whitespace-pre-wrap">{m.text}</div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2.5 text-zinc-400 text-xs py-2 bg-zinc-900/50 px-4 rounded-xl border border-zinc-800/80 w-fit">
              <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
              <span>Gemini está consultando las herramientas deterministas del servidor MCP...</span>
            </div>
          )}
        </div>

        {/* Sugerencias Rápidas */}
        <div className="px-6 py-2.5 bg-zinc-950 border-t border-zinc-900 flex items-center gap-2 overflow-x-auto">
          <span className="text-[11px] text-zinc-500 font-medium shrink-0">Prueba rápido:</span>
          {sugerencias.map((s, i) => {
            const Icon = s.icon;
            return (
              <button
                key={i}
                onClick={() => handleSend(s.query)}
                disabled={loading}
                className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 transition shrink-0 cursor-pointer disabled:opacity-50"
              >
                <Icon className="w-3 h-3 text-purple-400" />
                <span>{s.label}</span>
              </button>
            );
          })}
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-900/30 flex items-center gap-2">
          <input
            type="text"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="Pregúntale a Gemini sobre tus obras, precios COVENIN o cotizaciones..."
            disabled={loading}
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-purple-500 transition"
          />
          <button
            onClick={() => handleSend()}
            disabled={!prompt.trim() || loading}
            className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-medium text-sm flex items-center gap-2 transition cursor-pointer"
          >
            <Send className="w-4 h-4" />
            <span>Enviar</span>
          </button>
        </div>

      </div>
    </div>
  );
}
