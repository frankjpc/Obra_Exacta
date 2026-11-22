import os
import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from routers.api import router as api_router
from bot.telegram_bot import telegram_bot
from services.supabase_service import supabase_service
from services.bcv_service import bcv_service
from mcp_server import mcp as mcp_instance

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("==================================================================")
    print(" INICIANDO OBRAEXACTA BACKEND & TELEGRAM BOT INTEGRADO (PYTHON)")
    print("==================================================================")
    
    # 1. Asegurar carpeta de uploads locales
    os.makedirs("uploads", exist_ok=True)

    # 2. Inicializar proyecto limpio si la base de datos está vacía
    obras = supabase_service.get_obras()
    if not obras:
        print("Base de datos en blanco. Inicializando 'Proyecto Principal' limpio...")
        supabase_service.get_or_create_active_obra()
        obras = supabase_service.get_obras()

    try:
        bcv = bcv_service.get_tasa_oficial()
        tasa_oficial = bcv.get("tasa_bcv", settings.TASA_BCV_DEFAULT)
        print(f"Tasa Oficial BCV detectada: {tasa_oficial:.2f} Bs/USD ({bcv.get('fuente')})")
        for o in obras:
            curr_tasa = float(o.get("tasa_bcv", 0.0))
            if curr_tasa < 100.0:  # Tasa desactualizada
                pres_usd = float(o.get("presupuesto_total_usd", 0.0))
                gast_usd = float(o.get("total_gastado_usd", 0.0))
                supabase_service.update_obra(o["id"], {
                    "tasa_bcv": tasa_oficial,
                    "presupuesto_total_bs": round(pres_usd * tasa_oficial, 2),
                    "total_gastado_bs": round(gast_usd * tasa_oficial, 2)
                })
                print(f"Obra '{o.get('nombre')}' sincronizada con Tasa BCV: {tasa_oficial:.2f} Bs/$")
    except Exception as e:
        print(f"Aviso sincronizando tasa BCV al iniciar: {e}")

    # 3. Inicializar e iniciar Telegram Bot con Long Polling en segundo plano
    telegram_app = None
    lock_fp = None
    lock_file = os.path.join(os.path.dirname(__file__), "telegram_bot.lock")
    if settings.TELEGRAM_BOT_TOKEN:
        can_poll = False
        try:
            lock_fp = open(lock_file, "a+")
            lock_fp.seek(0)
            if sys.platform == "win32":
                import msvcrt
                try:
                    msvcrt.locking(lock_fp.fileno(), msvcrt.LK_NBLCK, 1)
                    can_poll = True
                except (IOError, OSError):
                    can_poll = False
            else:
                import fcntl
                try:
                    fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    can_poll = True
                except (IOError, OSError):
                    can_poll = False

            if can_poll:
                lock_fp.truncate(0)
                lock_fp.write(str(os.getpid()))
                lock_fp.flush()
                print(f"Bloqueo exclusivo de Telegram adquirido (PID {os.getpid()}).")
                print("Iniciando Bot de Telegram mediante Long Polling...")
                telegram_app = await telegram_bot.init_application()
                if telegram_app:
                    await telegram_app.initialize()
                    await telegram_app.start()
                    await telegram_app.updater.start_polling(drop_pending_updates=True)
                    telegram_bot.is_running = True
                    telegram_bot.bot_info["status"] = "running"
                    telegram_bot.bot_info["polling"] = True
                    print(f"Bot de Telegram activo (PID {os.getpid()}) y escuchando mensajes por Long Polling.")
            else:
                print("Aviso: Otra instancia del servidor ya está gestionando Telegram. Esta instancia operará en modo API REST.")
                telegram_bot.bot_info["status"] = "running_in_other_instance"
                telegram_bot.bot_info["polling"] = False
        except Exception as e:
            print(f"Aviso al configurar polling de Telegram: {e}")
            telegram_bot.bot_info["status"] = f"error: {e}"
    else:
        print("TELEGRAM_BOT_TOKEN vacío. El servidor funcionará en modo REST API / Web.")

    yield  # Aplicación ejecutándose

    # 4. Apagado limpio del Bot de Telegram al cerrar FastAPI
    if telegram_app:
        try:
            print("Deteniendo Bot de Telegram...")
            if telegram_app.updater and telegram_app.updater.running:
                await telegram_app.updater.stop()
            if telegram_app.running:
                await telegram_app.stop()
            await telegram_app.shutdown()
            print("Bot de Telegram detenido de forma segura.")
        except Exception as e:
            print(f"Error apagando Telegram Bot: {e}")
    if lock_fp:
        try:
            if sys.platform == "win32":
                import msvcrt
                try:
                    msvcrt.locking(lock_fp.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            lock_fp.close()
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception:
            pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MVP de ObraExacta para el track de Contratistas con Telegram Bot + Gemini 2.5 Flash + Supabase + Motor Determinista.",
    version="1.0.0",
    lifespan=lifespan
)

# Configuración de CORS para Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción acotar al dominio de Vercel/Next
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar Router de la API REST
app.include_router(api_router)

# Montar Servidor FastMCP con transporte HTTP/SSE
app.mount("/mcp", mcp_instance.http_app(transport="sse"))

@app.get("/")
def root():
    return {
        "app": "ObraExacta",
        "description": "API y Bot de Telegram integrados en un solo proceso FastAPI",
        "docs": "/docs",
        "status": "/api/status",
        "telegram_bot": telegram_bot.bot_info
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.BACKEND_PORT, reload=True)
