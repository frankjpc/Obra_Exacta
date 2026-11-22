import { Obra, Partida, HojaComprasItem, Factura, LibroObraItem, SystemStatus, EvidenciaAvance, CatalogoPrecioUsuario, HistorialEdicion, PerfilTelegram } from './types';

const API_BASE_URL = typeof window !== 'undefined'
  ? '/api'
  : (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api');

export const api = {
  // Estado del sistema
  async getStatus(): Promise<SystemStatus> {
    try {
      const res = await fetch(`${API_BASE_URL}/status`, { cache: 'no-store' });
      if (!res.ok) throw new Error('Error al consultar estado');
      return await res.json();
    } catch {
      return {
        status: 'online-fallback',
        project: 'ObraExacta',
        gemini_active: true,
        supabase_connected: false,
        telegram_bot_configured: false,
        telegram_bot_status: { status: 'running', polling: true },
        tasa_bcv_default: 918.77
      };
    }
  },

  // Cargar obra demo
  async seedDemo(): Promise<{ status: string; obra_id: string; message: string }> {
    const res = await fetch(`${API_BASE_URL}/seed-demo`, { method: 'POST' });
    if (!res.ok) throw new Error('Error al cargar obra demo');
    return await res.json();
  },

  // Limpiar / resetear base de datos
  async resetData(): Promise<{ status: string; message: string }> {
    const res = await fetch(`${API_BASE_URL}/reset-data`, { method: 'POST' });
    if (!res.ok) throw new Error('Error al limpiar base de datos');
    return await res.json();
  },

  // Obras
  async getObras(userId?: string): Promise<Obra[]> {
    try {
      const url = userId ? `${API_BASE_URL}/obras?user_id=${encodeURIComponent(userId)}` : `${API_BASE_URL}/obras`;
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) throw new Error('Error al obtener obras');
      return await res.json();
    } catch {
      return [];
    }
  },

  async getObra(id: string): Promise<Obra | null> {
    try {
      const res = await fetch(`${API_BASE_URL}/obras/${id}`, { cache: 'no-store' });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  },

  async updateObra(id: string, data: Partial<Obra>): Promise<Obra> {
    const res = await fetch(`${API_BASE_URL}/obras/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Error al actualizar obra');
    return await res.json();
  },

  // Partidas
  async getPartidas(obraId: string): Promise<Partida[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/obras/${obraId}/partidas`, { cache: 'no-store' });
      if (!res.ok) throw new Error('Error al obtener partidas');
      return await res.json();
    } catch {
      return [];
    }
  },

  async addPartida(obraId: string, partida: Partial<Partida>): Promise<Partida> {
    const res = await fetch(`${API_BASE_URL}/obras/${obraId}/partidas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...partida, obra_id: obraId })
    });
    if (!res.ok) throw new Error('Error al agregar partida');
    return await res.json();
  },

  async updatePartidaAvance(partidaId: string, porcentaje: number): Promise<Partida> {
    const res = await fetch(`${API_BASE_URL}/partidas/${partidaId}/avance`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ porcentaje })
    });
    if (!res.ok) throw new Error('Error al actualizar avance');
    return await res.json();
  },

  // Hoja de Compras
  async getHojaCompras(obraId: string): Promise<HojaComprasItem[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/obras/${obraId}/hoja-compras`, { cache: 'no-store' });
      if (!res.ok) throw new Error('Error al obtener hoja de compras');
      return await res.json();
    } catch {
      return [];
    }
  },

  // Facturas y Compras
  async getFacturas(obraId: string): Promise<Factura[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/obras/${obraId}/facturas`, { cache: 'no-store' });
      if (!res.ok) throw new Error('Error al obtener facturas');
      return await res.json();
    } catch {
      return [];
    }
  },

  async uploadFactura(obraId: string, file: File): Promise<any> {
    const formData = new FormData();
    formData.append('obra_id', obraId);
    formData.append('factura_img', file);

    const res = await fetch(`${API_BASE_URL}/facturas/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Error al subir factura');
    return await res.json();
  },

  // Evidencias de Avance
  async getEvidencias(obraId: string): Promise<EvidenciaAvance[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/obras/${obraId}/evidencias`, { cache: 'no-store' });
      if (!res.ok) throw new Error('Error al obtener evidencias');
      return await res.json();
    } catch {
      return [];
    }
  },

  async uploadEvidencia(formData: FormData): Promise<EvidenciaAvance> {
    const res = await fetch(`${API_BASE_URL}/evidencias/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Error al subir evidencia');
    return await res.json();
  },

  // Libro de Obra e Incidencias
  async getLibroObra(obraId: string): Promise<LibroObraItem[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/obras/${obraId}/libro-obra`, { cache: 'no-store' });
      if (!res.ok) throw new Error('Error al obtener libro de obra');
      return await res.json();
    } catch {
      return [];
    }
  },

  async reportarIncidencia(formData: FormData): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/incidencias/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Error al reportar parada');
    return await res.json();
  },

  // Ruta Pública Móvil de Aprobación
  async getIncidenciaParaAprobar(token: string): Promise<{ incidencia: LibroObraItem; obra: Obra }> {
    const res = await fetch(`${API_BASE_URL}/aprobar/${token}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Incidencia no encontrada o ya procesada');
    return await res.json();
  },

  async aprobarIncidencia(token: string, clienteNombre?: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/aprobar/${token}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cliente_nombre: clienteNombre || 'Cliente Autorizado' })
    });
    if (!res.ok) throw new Error('Error al aprobar el adicional');
    return await res.json();
  },

  // Respaldo Web Total: Levantamiento por texto o audio
  async procesarLevantamientoTexto(obraId: string, texto: string, tasaBcv?: number): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/levantamiento/texto`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ obra_id: obraId, texto, tasa_bcv: tasaBcv })
    });
    if (!res.ok) throw new Error('Error al procesar cubicación');
    return await res.json();
  },

  async procesarLevantamientoAudio(obraId: string, audioBlob: Blob): Promise<any> {
    const formData = new FormData();
    formData.append('obra_id', obraId);
    formData.append('audio', audioBlob, 'levantamiento_mic.ogg');

    const res = await fetch(`${API_BASE_URL}/levantamiento/audio`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Error al procesar audio de levantamiento');
    return await res.json();
  },

  // Tasa Oficial BCV
  async getBcvRate(): Promise<{ tasa_bcv: number; fuente: string; fecha: string }> {
    try {
      const res = await fetch(`${API_BASE_URL}/bcv`, { cache: 'no-store' });
      if (!res.ok) throw new Error('Error al consultar BCV');
      return await res.json();
    } catch {
      return { tasa_bcv: 918.77, fuente: 'BCV Oficial', fecha: 'Hoy' };
    }
  },

  async syncBcvRate(obraId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/bcv/sincronizar/${obraId}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Error al sincronizar tasa BCV oficial');
    return await res.json();
  },

  // Memoria Operativa de Precios e Historial de Ediciones
  async getMemoriaPrecios(userId?: string): Promise<CatalogoPrecioUsuario[]> {
    try {
      const url = userId ? `${API_BASE_URL}/memoria-precios?user_id=${encodeURIComponent(userId)}` : `${API_BASE_URL}/memoria-precios`;
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) return [];
      return await res.json();
    } catch {
      return [];
    }
  },

  async saveMemoriaPrecio(data: Partial<CatalogoPrecioUsuario>): Promise<CatalogoPrecioUsuario> {
    const res = await fetch(`${API_BASE_URL}/memoria-precios`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Error al guardar precio en memoria');
    return await res.json();
  },

  // Perfiles Telegram y Servidor MCP
  async getPerfil(userId?: string): Promise<PerfilTelegram | null> {
    try {
      const url = userId ? `${API_BASE_URL}/perfil?user_id=${encodeURIComponent(userId)}` : `${API_BASE_URL}/perfil`;
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  },

  async vincularTelegram(codigo: string, chatId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/perfil/vincular`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo, chat_id: chatId })
    });
    if (!res.ok) throw new Error('Error al vincular chat de Telegram');
    return await res.json();
  },

  async getHistorialEdiciones(obraId: string): Promise<HistorialEdicion[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/obras/${obraId}/historial-ediciones`, { cache: 'no-store' });
      if (!res.ok) return [];
      return await res.json();
    } catch {
      return [];
    }
  },

  getPresupuestoPdfUrl(obraId: string): string {
    return `${API_BASE_URL}/obras/${obraId}/presupuesto/pdf`;
  },

  // Agente Inteligente MCP + Gemini
  async mcpChat(prompt: string, apiKeyMcp?: string): Promise<{
    status: string;
    tool_called?: string | null;
    tool_args?: Record<string, any>;
    tool_result?: Record<string, any>;
    response: string;
  }> {
    const res = await fetch(`${API_BASE_URL}/mcp/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, api_key_mcp: apiKeyMcp })
    });
    if (!res.ok) throw new Error('Error al consultar Agente MCP');
    return await res.json();
  }
};
