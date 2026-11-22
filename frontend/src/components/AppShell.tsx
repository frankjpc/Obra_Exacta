'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import VoiceRecordModal from '@/components/VoiceRecordModal';
import InvoiceUploadModal from '@/components/InvoiceUploadModal';
import IncidentUploadModal from '@/components/IncidentUploadModal';
import McpAgentModal from '@/components/McpAgentModal';
import { Obra } from '@/lib/types';
import { api } from '@/lib/api';
import { subscribeToTable } from '@/lib/supabase';
import { useAuth } from '@/lib/auth-context';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [obras, setObras] = useState<Obra[]>([]);
  const [obraActiva, setObraActiva] = useState<Obra | null>(null);
  const [telegramStatus, setTelegramStatus] = useState<{ status: string; polling: boolean }>({
    status: 'running',
    polling: true
  });

  // Modals state
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [showInvoiceModal, setShowInvoiceModal] = useState(false);
  const [showIncidentModal, setShowIncidentModal] = useState(false);
  const [showMcpModal, setShowMcpModal] = useState(false);

  const isAprobarRoute = pathname.startsWith('/aprobar');
  const isLoginRoute = pathname.startsWith('/login');

  const loadData = useCallback(async () => {
    try {
      const list = await api.getObras(user?.id);
      setObras(list);
      if (list.length > 0 && !obraActiva) {
        setObraActiva(list[0]);
      } else if (list.length > 0 && obraActiva) {
        const found = list.find(o => o.id === obraActiva.id);
        if (found) setObraActiva(found);
      }
      const st = await api.getStatus();
      if (st.telegram_bot_status) {
        setTelegramStatus(st.telegram_bot_status);
      }
    } catch (e) {
      console.error(e);
    }
  }, [user?.id, obraActiva]);

  // Si no está autenticado y no es ruta pública, redirigir al login
  useEffect(() => {
    if (!authLoading && !user && !isAprobarRoute && !isLoginRoute) {
      router.replace('/login');
    }
  }, [user, authLoading, isAprobarRoute, isLoginRoute, router]);

  useEffect(() => {
    if (user || isAprobarRoute) {
      loadData();
    }

    // Supabase Realtime para obras
    const unsub = subscribeToTable('obras', () => {
      loadData();
    });

    return () => unsub();
  }, [user, isAprobarRoute, loadData]);

  // Rutas especiales sin Shell (Login y Aprobación externa móvil)
  if (isAprobarRoute || isLoginRoute) {
    return <main>{children}</main>;
  }

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#070b12] text-zinc-500 text-xs font-mono">
        Cargando ObraExacta...
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#070b12]">
      {/* Sidebar Colapsable */}
      <Sidebar 
        obraActiva={obraActiva} 
        telegramStatus={telegramStatus} 
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          obras={obras}
          obraActiva={obraActiva}
          onSelectObra={(obra) => {
            setObraActiva(obra);
            router.push(`${pathname}?obra_id=${obra.id}`);
          }}
          onRefreshData={loadData}
          onOpenVoiceModal={() => setShowVoiceModal(true)}
          onOpenInvoiceModal={() => setShowInvoiceModal(true)}
          onOpenIncidentModal={() => setShowIncidentModal(true)}
          onOpenMcpAgentModal={() => setShowMcpModal(true)}
        />

        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>

      {/* Modals de Respaldo Web Total */}
      {showVoiceModal && obraActiva && (
        <VoiceRecordModal
          isOpen={showVoiceModal}
          onClose={() => setShowVoiceModal(false)}
          obraId={obraActiva.id}
          tasaBcv={obraActiva.tasa_bcv || 918.77}
          onSuccess={() => {
            setShowVoiceModal(false);
            loadData();
          }}
        />
      )}

      {showInvoiceModal && obraActiva && (
        <InvoiceUploadModal
          isOpen={showInvoiceModal}
          onClose={() => setShowInvoiceModal(false)}
          obraId={obraActiva.id}
          onSuccess={() => {
            setShowInvoiceModal(false);
            loadData();
          }}
        />
      )}

      {showIncidentModal && obraActiva && (
        <IncidentUploadModal
          isOpen={showIncidentModal}
          onClose={() => setShowIncidentModal(false)}
          obraId={obraActiva.id}
          presupuestoBaseUsd={obraActiva.presupuesto_total_usd || 0}
          onSuccess={() => {
            setShowIncidentModal(false);
            loadData();
          }}
        />
      )}

      {/* Modal Interactivo del Agente IA (Gemini + MCP) */}
      <McpAgentModal
        isOpen={showMcpModal}
        onClose={() => setShowMcpModal(false)}
        obraActivaNombre={obraActiva?.nombre}
      />
    </div>
  );
}
