-- ==============================================================================
-- OBRAEXACTA - SCHEMA SUPABASE (POSTGRESQL + REALTIME + STORAGE)
-- ==============================================================================

-- 1. EXTENSIONES
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. TABLA: OBRAS (PROYECTOS)
CREATE TABLE IF NOT EXISTS public.obras (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre TEXT NOT NULL,
    cliente TEXT NOT NULL,
    direccion TEXT,
    tasa_bcv NUMERIC(10, 2) NOT NULL DEFAULT 68.50,
    margen_meta NUMERIC(5, 2) NOT NULL DEFAULT 30.00,
    presupuesto_total_usd NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    presupuesto_total_bs NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    total_gastado_usd NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_gastado_bs NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    estado TEXT NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'completada', 'pausada')),
    telegram_chat_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. TABLA: PARTIDAS (PRESUPUESTO 2D)
-- Columnas tabuladas: Partida | Unidad | P. Unit $ | Total $ | P. Unit Bs | Total Bs
CREATE TABLE IF NOT EXISTS public.partidas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    obra_id UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
    tipo_partida TEXT NOT NULL CHECK (tipo_partida IN ('pared_bloque', 'pintura', 'ceramica', 'cielo_raso', 'lampara', 'otro')),
    descripcion TEXT NOT NULL,
    largo NUMERIC(10, 2) DEFAULT 0.00,
    alto NUMERIC(10, 2) DEFAULT 0.00,
    cantidad NUMERIC(10, 2) NOT NULL DEFAULT 1.00,
    area NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    unidad TEXT NOT NULL DEFAULT 'm2',
    p_unit_usd NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    total_usd NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    p_unit_bs NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_bs NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    porcentaje_avance NUMERIC(5, 2) NOT NULL DEFAULT 0.00 CHECK (porcentaje_avance BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. TABLA: HOJA DE COMPRAS ESTIMADA (CONSOLIDADA)
CREATE TABLE IF NOT EXISTS public.hoja_compras (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    obra_id UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
    material TEXT NOT NULL,
    unidad TEXT NOT NULL,
    cantidad_requerida NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    cantidad_comprada NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    p_unit_estimado_usd NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    total_estimado_usd NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_comprado_usd NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. TABLA: CARGAS FISCALES E INDIRECTOS
CREATE TABLE IF NOT EXISTS public.cargas_fiscales (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    obra_id UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    porcentaje NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    aplica_sobre TEXT NOT NULL DEFAULT 'mano_de_obra' CHECK (aplica_sobre IN ('mano_de_obra', 'materiales', 'subtotal')),
    monto_usd NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    monto_bs NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. TABLA: FACTURAS Y GASTOS DE FERRETERÍA
CREATE TABLE IF NOT EXISTS public.facturas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    obra_id UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
    proveedor TEXT NOT NULL,
    nro_control TEXT,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    total_usd NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    total_bs NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    hash_sha256 TEXT UNIQUE,
    foto_url TEXT,
    alerta_sobreprecio BOOLEAN NOT NULL DEFAULT FALSE,
    alerta_fuera_partida BOOLEAN NOT NULL DEFAULT FALSE,
    alerta_duplicada BOOLEAN NOT NULL DEFAULT FALSE,
    detalle_alerta TEXT,
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. TABLA: EVIDENCIAS DE AVANCE
CREATE TABLE IF NOT EXISTS public.evidencias_avance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    partida_id UUID NOT NULL REFERENCES public.partidas(id) ON DELETE CASCADE,
    obra_id UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
    porcentaje_alcanzado NUMERIC(5, 2) NOT NULL CHECK (porcentaje_alcanzado BETWEEN 0 AND 100),
    foto_url TEXT NOT NULL,
    notas TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. TABLA: LIBRO DE OBRA Y ADICIONALES (PARADAS / DAÑOS OCULTOS)
CREATE TABLE IF NOT EXISTS public.libro_obra (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    obra_id UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL DEFAULT 'parada_dano_oculto' CHECK (tipo IN ('parada_dano_oculto', 'nota_general', 'hito')),
    titulo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    foto_url TEXT,
    costo_adicional_usd NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    costo_adicional_bs NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    porcentaje_variacion NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    token_aprobacion TEXT UNIQUE NOT NULL,
    estado_aprobacion TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado_aprobacion IN ('pendiente', 'aprobado', 'rechazado')),
    aprobado_en TIMESTAMPTZ,
    cliente_nombre TEXT,
    telegram_chat_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. HABILITAR PUBLICACIÓN SUPABASE REALTIME
ALTER PUBLICATION supabase_realtime ADD TABLE public.obras;
ALTER PUBLICATION supabase_realtime ADD TABLE public.partidas;
ALTER PUBLICATION supabase_realtime ADD TABLE public.hoja_compras;
ALTER PUBLICATION supabase_realtime ADD TABLE public.cargas_fiscales;
ALTER PUBLICATION supabase_realtime ADD TABLE public.facturas;
ALTER PUBLICATION supabase_realtime ADD TABLE public.evidencias_avance;
ALTER PUBLICATION supabase_realtime ADD TABLE public.libro_obra;

-- 10. POLÍTICAS RLS (Row Level Security abierto para MVP o Service Role)
ALTER TABLE public.obras ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.partidas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hoja_compras ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cargas_fiscales ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.facturas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidencias_avance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.libro_obra ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Permitir todo en obras" ON public.obras FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Permitir todo en partidas" ON public.partidas FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Permitir todo en hoja_compras" ON public.hoja_compras FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Permitir todo en cargas_fiscales" ON public.cargas_fiscales FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Permitir todo en facturas" ON public.facturas FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Permitir todo en evidencias_avance" ON public.evidencias_avance FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Permitir todo en libro_obra" ON public.libro_obra FOR ALL USING (true) WITH CHECK (true);

-- 11. BUCKET DE ALMACENAMIENTO (STORAGE)
INSERT INTO storage.buckets (id, name, public) 
VALUES ('obraexacta', 'obraexacta', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Lectura publica de archivos" 
ON storage.objects FOR SELECT 
USING (bucket_id = 'obraexacta');

CREATE POLICY "Subida publica de archivos" 
ON storage.objects FOR INSERT 
WITH CHECK (bucket_id = 'obraexacta');

-- ==============================================================================
-- 12. MEJORAS DE MEMORIA OPERATIVA Y NORMA COVENIN
-- ==============================================================================

-- Agregar columna oficial COVENIN a partidas
ALTER TABLE public.partidas ADD COLUMN IF NOT EXISTS codigo_covenin TEXT DEFAULT 'E-GEN.000.001';

-- TABLA: CATÁLOGO DE PRECIOS DEL USUARIO (MEMORIA OPERATIVA)
CREATE TABLE IF NOT EXISTS public.catalogo_precios_usuario (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clave_o_codigo TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'material' CHECK (tipo IN ('material', 'partida', 'mano_de_obra')),
    unidad TEXT NOT NULL DEFAULT 'und',
    precio_usd NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    proveedor_opcional TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- TABLA: HISTORIAL DE EDICIONES CONVERSACIONALES
CREATE TABLE IF NOT EXISTS public.historial_ediciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    obra_id UUID NOT NULL REFERENCES public.obras(id) ON DELETE CASCADE,
    accion TEXT NOT NULL,
    partida_o_material TEXT NOT NULL,
    valor_anterior TEXT,
    valor_nuevo TEXT NOT NULL,
    detalles JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- PUBLICACIÓN REALTIME PARA NUEVAS TABLAS
ALTER PUBLICATION supabase_realtime ADD TABLE public.catalogo_precios_usuario;
ALTER PUBLICATION supabase_realtime ADD TABLE public.historial_ediciones;

-- POLÍTICAS RLS PARA NUEVAS TABLAS
ALTER TABLE public.catalogo_precios_usuario ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.historial_ediciones ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Permitir todo en catalogo_precios_usuario" ON public.catalogo_precios_usuario FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Permitir todo en historial_ediciones" ON public.historial_ediciones FOR ALL USING (true) WITH CHECK (true);

-- ==============================================================================
-- 13. TABLA: SESIONES DE LEVANTAMIENTO (PERSISTENCIA Y RECUPERACIÓN DE CONTEXTO)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.sesiones_levantamiento (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_chat_id TEXT NOT NULL,
    obra_id UUID REFERENCES public.obras(id) ON DELETE CASCADE,
    obra_nombre TEXT,
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'esperando_aclaracion', 'completado')),
    rondas_preguntas INT NOT NULL DEFAULT 0,
    borrador_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    historial_mensajes JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices de consulta rápida
CREATE INDEX IF NOT EXISTS idx_sesiones_levantamiento_chat_id ON public.sesiones_levantamiento(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_levantamiento_obra_id ON public.sesiones_levantamiento(obra_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_levantamiento_estado ON public.sesiones_levantamiento(estado);

-- Habilitar suscripción en Supabase Realtime (sin romper suscripciones existentes)
ALTER PUBLICATION supabase_realtime ADD TABLE public.sesiones_levantamiento;

-- Políticas de Seguridad RLS
ALTER TABLE public.sesiones_levantamiento ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Permitir todo en sesiones_levantamiento" ON public.sesiones_levantamiento FOR ALL USING (true) WITH CHECK (true);

-- ==============================================================================
-- 14. AUTENTICACIÓN MULTIUSUARIO Y PERFILES TELEGRAM
-- ==============================================================================

-- 1. Agregar columna user_id (UUID, nullable por compatibilidad con datos demo)
ALTER TABLE public.obras ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE public.sesiones_levantamiento ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE public.catalogo_precios_usuario ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE public.facturas ADD COLUMN IF NOT EXISTS user_id UUID;

-- Tabla de gastos (si no existe) y columna user_id
CREATE TABLE IF NOT EXISTS public.gastos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    obra_id UUID REFERENCES public.obras(id) ON DELETE CASCADE,
    descripcion TEXT,
    monto_usd NUMERIC(10, 2) DEFAULT 0.00,
    monto_bs NUMERIC(12, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE public.gastos ADD COLUMN IF NOT EXISTS user_id UUID;

-- 2. Tabla perfiles_telegram
CREATE TABLE IF NOT EXISTS public.perfiles_telegram (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    telegram_chat_id TEXT UNIQUE,
    codigo_vinculacion TEXT UNIQUE,
    api_key_mcp TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Índices de consulta rápida y optimización multiusuario
CREATE INDEX IF NOT EXISTS idx_obras_user_id ON public.obras(user_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_user_id ON public.sesiones_levantamiento(user_id);
CREATE INDEX IF NOT EXISTS idx_catalogo_user_id ON public.catalogo_precios_usuario(user_id);
CREATE INDEX IF NOT EXISTS idx_facturas_user_id ON public.facturas(user_id);
CREATE INDEX IF NOT EXISTS idx_gastos_user_id ON public.gastos(user_id);
CREATE INDEX IF NOT EXISTS idx_perfiles_telegram_user ON public.perfiles_telegram(user_id);
CREATE INDEX IF NOT EXISTS idx_perfiles_telegram_chat ON public.perfiles_telegram(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_perfiles_telegram_codigo ON public.perfiles_telegram(codigo_vinculacion);

-- Publicación Realtime para perfiles y sincronización reactiva
ALTER PUBLICATION supabase_realtime ADD TABLE public.perfiles_telegram;
ALTER PUBLICATION supabase_realtime ADD TABLE public.gastos;

-- Políticas RLS
ALTER TABLE public.gastos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Permitir todo en gastos" ON public.gastos FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE public.perfiles_telegram ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Permitir todo en perfiles_telegram" ON public.perfiles_telegram FOR ALL USING (true) WITH CHECK (true);

