import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || '').trim();
const supabaseAnonKey = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '').trim();

export const supabase: SupabaseClient | null = (supabaseUrl && supabaseAnonKey)
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

/**
 * Suscribe a cambios en tiempo real en Supabase para una tabla determinada.
 * Si Supabase no está configurado, invoca un intervalo de sondeo ligero (polling)
 * para garantizar la reactividad instantánea del MVP.
 */
export function subscribeToTable(
  tableName: string,
  callback: (payload: any) => void
): () => void {
  if (supabase) {
    const channel = supabase
      .channel(`realtime_${tableName}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: tableName },
        (payload) => {
          callback(payload);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }

  // Fallback reactivo con sondeo cada 4 segundos
  const interval = setInterval(() => {
    callback({ eventType: 'POLL_SYNC', table: tableName });
  }, 4000);

  return () => clearInterval(interval);
}
