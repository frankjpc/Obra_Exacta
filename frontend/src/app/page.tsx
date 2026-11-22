'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/presupuestos');
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-[60vh] text-zinc-500 text-xs font-mono">
      Cargando ObraExacta...
    </div>
  );
}
