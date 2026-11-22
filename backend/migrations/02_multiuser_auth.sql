-- ==============================================================================
-- OBRAEXACTA - MIGRACIÓN 02: AUTENTICACIÓN MULTIUSUARIO Y PERFILES TELEGRAM
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
