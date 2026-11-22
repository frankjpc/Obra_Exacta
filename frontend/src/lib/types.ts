export interface Obra {
  id: string;
  nombre: string;
  cliente: string;
  direccion?: string;
  tasa_bcv: number;
  margen_meta: number;
  presupuesto_total_usd: number;
  presupuesto_total_bs: number;
  total_gastado_usd: number;
  total_gastado_bs: number;
  estado: 'activa' | 'completada' | 'pausada';
  user_id?: string | null;
  telegram_chat_id?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface MaterialDesglose {
  material_key: string;
  nombre: string;
  unidad: string;
  cantidad: number;
  p_unit_usd: number;
  total_usd: number;
}

export interface Partida {
  id: string;
  obra_id: string;
  codigo_covenin?: string;
  tipo_partida: 'pared_bloque' | 'pintura' | 'ceramica' | 'cielo_raso' | 'lampara' | 'otro';
  descripcion: string;
  largo: number;
  alto: number;
  cantidad: number;
  area: number;
  unidad: string;
  // 6 Columnas bimonetarias
  p_unit_usd: number;
  total_usd: number;
  p_unit_bs: number;
  total_bs: number;
  // Detalle adicional
  costo_materiales_usd?: number;
  costo_mano_obra_usd?: number;
  materiales?: MaterialDesglose[];
  porcentaje_avance: number;
  created_at?: string;
  updated_at?: string;
}

export interface CatalogoPrecioUsuario {
  id?: string;
  clave_o_codigo: string;
  nombre: string;
  tipo: 'material' | 'partida' | 'mano_de_obra';
  unidad: string;
  precio_usd: number;
  proveedor_opcional?: string;
  updated_at?: string;
}

export interface HistorialEdicion {
  id?: string;
  obra_id: string;
  accion: string;
  partida_o_material: string;
  valor_anterior?: string;
  valor_nuevo: string;
  detalles?: any;
  created_at?: string;
}

export interface HojaComprasItem {
  id?: string;
  obra_id: string;
  material: string;
  unidad: string;
  cantidad_requerida: number;
  cantidad_comprada: number;
  p_unit_estimado_usd: number;
  total_estimado_usd: number;
  total_comprado_usd: number;
}

export interface CargaFiscal {
  id?: string;
  nombre: string;
  porcentaje: number;
  aplica_sobre: 'mano_de_obra' | 'materiales' | 'subtotal';
  monto_usd: number;
  monto_bs: number;
}

export interface FacturaItem {
  descripcion: string;
  cantidad: number;
  precio_unitario_usd: number;
  total_usd: number;
}

export interface Factura {
  id: string;
  obra_id: string;
  user_id?: string | null;
  proveedor: string;
  nro_control?: string;
  fecha: string;
  total_usd: number;
  total_bs: number;
  hash_sha256?: string;
  foto_url?: string;
  alerta_sobreprecio: boolean;
  alerta_fuera_partida: boolean;
  alerta_duplicada: boolean;
  detalle_alerta?: string;
  items: FacturaItem[];
  created_at?: string;
}

export interface EvidenciaAvance {
  id: string;
  partida_id?: string;
  obra_id: string;
  porcentaje_alcanzado: number;
  foto_url: string;
  notas?: string;
  created_at?: string;
}

export interface LibroObraItem {
  id: string;
  obra_id: string;
  tipo: 'parada_dano_oculto' | 'nota_general' | 'hito';
  titulo: string;
  descripcion: string;
  foto_url?: string;
  costo_adicional_usd: number;
  costo_adicional_bs: number;
  porcentaje_variacion: number;
  token_aprobacion: string;
  estado_aprobacion: 'pendiente' | 'aprobado' | 'rechazado';
  aprobado_en?: string | null;
  cliente_nombre?: string | null;
  telegram_chat_id?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface SystemStatus {
  status: string;
  project: string;
  gemini_active: boolean;
  supabase_connected: boolean;
  telegram_bot_configured: boolean;
  telegram_bot_status: {
    status: string;
    username?: string | null;
    polling: boolean;
  };
  tasa_bcv_default: number;
}

export interface PerfilTelegram {
  id?: string;
  user_id: string;
  telegram_chat_id?: string | null;
  codigo_vinculacion: string;
  api_key_mcp: string;
  created_at?: string;
  updated_at?: string;
}

export interface AuthUser {
  id: string;
  email: string;
  is_demo?: boolean;
}
