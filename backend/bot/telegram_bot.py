import io
import re
import uuid
import asyncio
from typing import Optional, Any
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from config import settings
from services.supabase_service import supabase_service
from services.calculator import ConstructionCalculator, PartidaInput
from services.gemini_service import gemini_service
from services.invoice_service import invoice_service
from services.site_log_service import site_log_service
from services.bcv_service import bcv_service
from services.pdf_generator import PDFPresupuestoGenerator
from services.levantamiento_skill import levantamiento_skill
from services.session_manager import session_manager

class ObraExactaTelegramBot:
    def __init__(self):
        self.app: Optional[Application] = None
        self.is_running: bool = False
        self.bot_info: dict = {
            "status": "stopped",
            "username": None,
            "polling": False
        }

    async def init_application(self) -> Optional[Application]:
        token = settings.TELEGRAM_BOT_TOKEN
        if not token or token.strip() == "":
            print("TELEGRAM_BOT_TOKEN no configurado en .env. El bot de Telegram permanecerá inactivo (modo REST API).")
            self.bot_info["status"] = "unconfigured"
            return None

        try:
            builder = ApplicationBuilder().token(token)
            self.app = builder.build()

            # Comandos
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("ayuda", self.cmd_ayuda))
            self.app.add_handler(CommandHandler("vincular", self.cmd_vincular))
            self.app.add_handler(CommandHandler("obras", self.cmd_obras))
            self.app.add_handler(CommandHandler("activa", self.cmd_activa))
            self.app.add_handler(CommandHandler("estado", self.cmd_estado))
            self.app.add_handler(CommandHandler("bcv", self.cmd_bcv))
            self.app.add_handler(CommandHandler("cuadrilla", self.cmd_cuadrilla))
            self.app.add_handler(CommandHandler("avance", self.cmd_cuadrilla))
            self.app.add_handler(CommandHandler("limpiar", self.cmd_limpiar))
            self.app.add_handler(CommandHandler("reset", self.cmd_limpiar))

            # Manejador de Botones Interactivos (Inline Keyboard para la cuadrilla)
            self.app.add_handler(CallbackQueryHandler(self.handle_callback_query))

            # Manejador de Notas de Voz (.ogg)
            self.app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))

            # Manejador de Fotos (con o sin caption)
            self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))

            # Manejador de Audio / Archivos
            self.app.add_handler(MessageHandler(filters.AUDIO, self.handle_audio_file))

            # Manejador de Mensajes de Texto libres
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

            # Manejador de Errores Global (Prevención de bucle de conflicto)
            self.app.add_error_handler(self.global_error_handler)

            self.bot_info["status"] = "ready"
            return self.app
        except Exception as e:
            print(f"Error inicializando Telegram Bot: {e}")
            self.bot_info["status"] = f"error: {e}"
            return None

    async def global_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Captura errores de Telegram de forma limpia evitando loops de reintento en caso de conflicto."""
        err_str = str(context.error) if context.error else ""
        if "conflict" in err_str.lower() or "terminated by other getupdates" in err_str.lower():
            print("Aviso Telegram: Conflicto de instancia detectado (otra instancia solicitó updates). Deteniendo polling para evitar colisión.")
            self.bot_info["status"] = "stopped_conflict"
            self.bot_info["polling"] = False
            if self.app and self.app.updater and self.app.updater.running:
                try:
                    await self.app.updater.stop()
                except Exception:
                    pass
            return
        print(f"Aviso Telegram Bot: {context.error}")

    # --------------------------------------------------------------------------
    # COMANDOS DE TELEGRAM
    # --------------------------------------------------------------------------
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        perfil = supabase_service.get_perfil_by_chat_id(chat_id)
        user_id = perfil.get("user_id") if perfil else None
        obra = supabase_service.get_or_create_active_obra(chat_id, user_id=user_id)
        tasa = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))
        
        vinculacion_str = "🟢 *Cuenta Web Vinculada*" if perfil else "🟡 *Chat no vinculado.* Usa `/vincular <codigo>`"
        
        texto = (
            "🏗️ *¡Bienvenido a ObraExacta Bot!* \n\n"
            "Tu copiloto de cubicación, control de compras y libro de obra para contratistas y cuadrillas.\n\n"
            f"👤 *Estado:* {vinculacion_str}\n"
            f"📍 *Obra activa:* `{obra.get('nombre')}`\n"
            f"💵 *Tasa BCV Oficial:* `{tasa:,.2f} Bs/USD`\n\n"
            "👷‍♂️ *¿Cómo puede reportar la cuadrilla en campo?*\n"
            "• *Comando rápido:* `/avance` para ver partidas y actualizar en 1 toque.\n"
            "• *Foto de trabajo:* Con caption 'Pared al 85%' o 'Avance pintura'.\n"
            "• *Nota de voz:* 'Terminamos la cerámica en el piso 8'.\n\n"
            "🧾 *Otras funciones:*\n"
            "• `/vincular <codigo>` - Enlazar este chat a tu cuenta en la app web.\n"
            "• `/bcv` - Sincronizar y consultar la Tasa Oficial del Banco Central de Venezuela.\n"
            "• Envía foto de factura de ferretería para auditar sobreprecio y duplicados.\n"
            "• Envía nota de voz dictando medidas para calcular nuevo presupuesto 2D.\n"
            "• Reporta daño oculto para generar link móvil de aprobación al cliente.\n\n"
            "Usa /ayuda para ver todos los comandos."
        )
        await update.message.reply_text(texto, parse_mode="Markdown")

    async def cmd_ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        texto = (
            "📋 *Comandos de ObraExacta:*\n\n"
            "/vincular <codigo> - Enlazar este chat a tu cuenta de la app web\n"
            "/avance o /cuadrilla - Ver y actualizar avances por partida en 1 toque\n"
            "/bcv - Consultar y sincronizar Tasa Oficial del BCV en vivo\n"
            "/estado - Ver balance presupuestario y avance global ponderado\n"
            "/obras - Listar todas tus obras registradas\n"
            "/activa <id> - Cambiar la obra activa para este chat\n"
            "/limpiar o /reset - Borrar partidas y empezar en limpio desde cero ($0.00)\n"
            "/start - Iniciar el bot y ver obra activa\n"
            "/ayuda - Ver esta guía"
        )
        await update.message.reply_text(texto, parse_mode="Markdown")

    async def cmd_limpiar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Limpia completamente todas las partidas, facturas y registros de prueba."""
        chat_id = update.effective_chat.id
        levantamiento_skill.clear_session(chat_id)
        session_manager.clear_chat_sessions(chat_id)
        status_msg = await update.message.reply_text("🧹 *Limpiando toda la base de datos y partidas...*", parse_mode="Markdown")
        try:
            _ = await asyncio.to_thread(supabase_service.clear_all_data, create_default=True)
            obra = supabase_service.get_or_create_active_obra(chat_id)
            tasa = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))
            texto = (
                "✅ *¡Base de datos limpiada con éxito!*\n\n"
                "Se han eliminado todas las partidas anteriores, facturas de ferretería, hojas de compra y datos de prueba.\n\n"
                f"🏗️ *Obra activa:* `{obra.get('nombre')}`\n"
                f"💵 *Tasa BCV:* `{tasa:,.2f} Bs/USD`\n"
                "💰 *Presupuesto actual:* `$0.00` | `Bs. 0.00`\n"
                "📊 *Total Partidas:* `0`\n\n"
                "🎙️ *Listo. Puedes dictar tus medidas por nota de voz o subir facturas reales sin datos anteriores mezclados.*"
            )
            await status_msg.edit_text(texto, parse_mode="Markdown")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error al limpiar la base de datos: {e}")

    async def cmd_bcv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Consulta y sincroniza la tasa oficial en vivo del BCV."""
        chat_id = update.effective_chat.id
        obra = supabase_service.get_or_create_active_obra(chat_id)
        status_msg = await update.message.reply_text("🔄 *Consultando Tasa Oficial BCV en tiempo real...*", parse_mode="Markdown")
        try:
            bcv_info = await asyncio.to_thread(bcv_service.get_tasa_oficial)
            tasa = bcv_info.get("tasa_bcv", settings.TASA_BCV_DEFAULT)
            fuente = bcv_info.get("fuente", "BCV")
            fecha = bcv_info.get("fecha", "Hoy")

            # Actualizar en base de datos para la obra activa
            pres_usd = float(obra.get("presupuesto_total_usd", 0.0))
            gast_usd = float(obra.get("total_gastado_usd", 0.0))
            supabase_service.update_obra(obra["id"], {
                "tasa_bcv": tasa,
                "presupuesto_total_bs": round(pres_usd * tasa, 2),
                "total_gastado_bs": round(gast_usd * tasa, 2)
            })

            texto = (
                f"💵 *TASA OFICIAL BCV ACTUALIZADA*\n\n"
                f"🏛️ *Fuente:* {fuente}\n"
                f"📈 *Tasa Vigente:* `{tasa:,.2f} Bs/USD`\n"
                f"📅 *Fecha:* {fecha}\n"
                f"🏗️ *Obra Activa:* `{obra['nombre']}`\n\n"
                f"✅ Obra sincronizada en tiempo real con el Dashboard web."
            )
            await status_msg.edit_text(texto, parse_mode="Markdown")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error al consultar Tasa BCV: {str(e)}")

    async def cmd_cuadrilla(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Menú interactivo mobile-first en Telegram para la cuadrilla de obra."""
        chat_id = update.effective_chat.id
        obra = supabase_service.get_or_create_active_obra(chat_id)
        partidas = supabase_service.get_partidas(obra["id"])
        
        if not partidas:
            await update.message.reply_text(
                "⚠️ No hay partidas registradas en la obra activa. Dicta una nota de voz para crear el presupuesto inicial.",
                parse_mode="Markdown"
            )
            return

        avance_global = site_log_service.calculate_global_progress(obra["id"])
        barra_global = site_log_service.render_progress_bar(avance_global)

        lineas = [
            "👷‍♂️ *PANEL DE AVANCE DE CUADRILLA*",
            f"🏗️ *Obra:* {obra['nombre']}",
            f"🌐 *Avance Global Ponderado:* {barra_global}\n",
            "*Partidas en Ejecución:*"
        ]

        keyboard = []
        for p in partidas:
            pct = p.get("porcentaje_avance", 0)
            bar = site_log_service.render_progress_bar(pct, length=6)
            lineas.append(f"• *{p['descripcion']}*: {bar}")
            # Botón para que la cuadrilla seleccione partida
            keyboard.append([
                InlineKeyboardButton(
                    f"🔨 Actualizar: {p['descripcion'][:24]}... ({pct:.0f}%)", 
                    callback_data=f"sel_p:{p['id']}"
                )
            ])

        lineas.append("\n📸 *También puedes enviar una FOTO de la obra con el avance en texto o nota de voz.*")

        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query and update.callback_query.message:
            await update.callback_query.edit_message_text("\n".join(lineas), reply_markup=reply_markup, parse_mode="Markdown")
        elif update.message:
            await update.message.reply_text("\n".join(lineas), reply_markup=reply_markup, parse_mode="Markdown")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los toques en botones interactivos de la cuadrilla."""
        query = update.callback_query
        await query.answer()

        data = query.data
        chat_id = update.effective_chat.id
        obra = supabase_service.get_or_create_active_obra(chat_id)

        # 1. Cuadrilla seleccionó una partida para actualizar
        if data.startswith("sel_p:"):
            partida_id = data.split("sel_p:")[1]
            partidas = supabase_service.get_partidas(obra["id"])
            target = next((p for p in partidas if p["id"] == partida_id), None)
            
            if not target:
                await query.edit_message_text("❌ Partida no encontrada.")
                return

            keyboard = [
                [
                    InlineKeyboardButton("25%", callback_data=f"set_p:{partida_id}:25"),
                    InlineKeyboardButton("50%", callback_data=f"set_p:{partida_id}:50"),
                    InlineKeyboardButton("75%", callback_data=f"set_p:{partida_id}:75"),
                    InlineKeyboardButton("100% ✅", callback_data=f"set_p:{partida_id}:100")
                ],
                [
                    InlineKeyboardButton("🔙 Volver a la lista", callback_data="back_cuadrilla")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"👷‍♂️ *Actualizar avance para:*\n"
                f"📌 *{target['descripcion']}*\n"
                f"Avance actual: {target.get('porcentaje_avance', 0):.0f}%\n\n"
                f"Selecciona el nuevo porcentaje alcanzado por la cuadrilla:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

        # 2. Cuadrilla fijó el porcentaje
        elif data.startswith("set_p:"):
            _, partida_id, pct_str = data.split(":")
            nuevo_pct = float(pct_str)
            user_name = update.effective_user.first_name or "Cuadrilla"
            
            partida = supabase_service.update_partida_avance(partida_id, nuevo_pct)
            
            # Registrar evidencia
            supabase_service.save_evidencia({
                "partida_id": partida_id,
                "obra_id": obra["id"],
                "porcentaje_alcanzado": nuevo_pct,
                "foto_url": "https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?auto=format&fit=crop&w=600&q=80",
                "notas": f"Avance fijado vía Telegram por {user_name} ({nuevo_pct:.0f}%)"
            })

            avance_global = site_log_service.calculate_global_progress(obra["id"])
            barra_partida = site_log_service.render_progress_bar(nuevo_pct)
            barra_global = site_log_service.render_progress_bar(avance_global)

            msg = (
                f"✅ *¡AVANCE DE CUADRILLA ACTUALIZADO!*\n\n"
                f"🏗️ *Obra:* {obra['nombre']}\n"
                f"👤 *Reportó:* {user_name}\n"
                f"📌 *Partida:* {partida.get('descripcion')}\n"
                f"📈 *Avance Partida:* {barra_partida}\n"
                f"🌐 *Nuevo Avance Global de Obra:* {barra_global}\n\n"
                f"🔄 Sincronizado en tiempo real con el Dashboard de Next.js.\n"
                f"🔗 [Ver en Pantalla]({settings.FRONTEND_URL}/avance?obra_id={obra['id']})"
            )
            await query.edit_message_text(msg, parse_mode="Markdown")

        # 3. Volver al menú
        elif data == "back_cuadrilla":
            await self.cmd_cuadrilla(update, context)

    async def cmd_vincular(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        args = context.args or []
        if not args:
            perfil_actual = supabase_service.get_perfil_by_chat_id(chat_id)
            if perfil_actual:
                await update.message.reply_text(
                    f"✅ *Este chat ya está vinculado a ObraExacta.*\n\n"
                    f"👤 *Usuario ID:* `{perfil_actual.get('user_id')}`\n"
                    f"🔑 *Código:* `{perfil_actual.get('codigo_vinculacion')}`\n\n"
                    "Todas tus notas de voz, fotos y facturas se asocian a tus obras privadas.",
                    parse_mode="Markdown"
                )
                return

            texto = (
                "🔗 *Vinculación de Cuenta con ObraExacta*\n\n"
                "Para sincronizar este chat de Telegram con tu cuenta de la app web:\n\n"
                "1. Abre ObraExacta en tu navegador.\n"
                "2. En el menú lateral (Sidebar), copia tu *Código de Vinculación* de 6 dígitos.\n"
                "3. Escribe aquí:\n"
                "   👉 `/vincular <codigo>`\n"
                "   Ejemplo: `/vincular 482910`"
            )
            await update.message.reply_text(texto, parse_mode="Markdown")
            return

        codigo = args[0].strip()
        perfil = supabase_service.vincular_telegram_chat(codigo, chat_id)
        if perfil:
            user_id = perfil.get("user_id", "demo")
            texto = (
                "✅ *¡Cuenta Vinculada Exitosamente!*\n\n"
                f"Este chat de Telegram (`{chat_id}`) ahora está enlazado a tu usuario de ObraExacta.\n\n"
                "🏗️ *A partir de este momento:*\n"
                "• Todas las cubicaciones por voz se registran en tus proyectos personales.\n"
                "• Tus facturas de compra y auditorías se guardan en tu cuenta.\n"
                "• El catálogo de precios aprendidos se aplicará a tus presupuestos.\n\n"
                "🎙️ *¡Comienza a medir!* Envíame un audio diciendo: _'Cúbícame 20 metros cuadrados de bloque en la Obra Torre Polar'_"
            )
            await update.message.reply_text(texto, parse_mode="Markdown")
        else:
            texto = (
                "❌ *Código de vinculación inválido o no encontrado.*\n\n"
                f"El código `{codigo}` no coincide con ninguna cuenta activa.\n"
                "Verifica tu código en el menú lateral de la app web de ObraExacta e inténtalo de nuevo."
            )
            await update.message.reply_text(texto, parse_mode="Markdown")

    async def cmd_obras(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        perfil = supabase_service.get_perfil_by_chat_id(chat_id)
        user_id = perfil.get("user_id") if perfil else None
        obras = supabase_service.get_obras(user_id=user_id)
        if not obras:
            await update.message.reply_text("No hay obras registradas. Usa /start para crear una obra inicial.")
            return

        lineas = ["🏗️ *Tus Obras Disponibles:*"]
        for o in obras:
            lineas.append(f"• `{o['id']}`: *{o['nombre']}* ({o['cliente']}) - ${o.get('presupuesto_total_usd', 0):,.2f}")
        lineas.append("\nPara cambiar a una obra: `/activa <id>`")
        await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

    async def cmd_activa(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        args = context.args
        if not args:
            await update.message.reply_text("Por favor indica el ID de la obra: `/activa <id>`", parse_mode="Markdown")
            return
        
        target_id = args[0]
        obra = supabase_service.get_obra(target_id)
        if not obra:
            await update.message.reply_text("❌ No se encontró ninguna obra con ese ID.")
            return

        supabase_service.update_obra(target_id, {"telegram_chat_id": chat_id, "estado": "activa"})
        await update.message.reply_text(f"✅ Obra activa cambiada a: *{obra['nombre']}*", parse_mode="Markdown")

    async def cmd_estado(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        obra = supabase_service.get_or_create_active_obra(chat_id)
        pres_usd = float(obra.get("presupuesto_total_usd", 0.0))
        gast_usd = float(obra.get("total_gastado_usd", 0.0))
        tasa_bcv = float(obra.get("tasa_bcv", 68.50))
        disp_usd = max(0.0, pres_usd - gast_usd)
        
        avance_global = site_log_service.calculate_global_progress(obra["id"])
        barra_global = site_log_service.render_progress_bar(avance_global)

        texto = (
            f"📊 *ESTADO DE LA OBRA*\n"
            f"🏗️ *{obra['nombre']}*\n\n"
            f"💰 *Presupuestado:* ${pres_usd:,.2f} (Bs. {pres_usd * tasa_bcv:,.2f})\n"
            f"🛒 *Gastado Real:* ${gast_usd:,.2f} (Bs. {gast_usd * tasa_bcv:,.2f})\n"
            f"🟢 *Disponible:* ${disp_usd:,.2f}\n"
            f"📈 *Avance Global Ponderado:* {barra_global}\n\n"
            f"🔗 Ver en Dashboard: {settings.FRONTEND_URL}/avance?obra_id={obra['id']}"
        )
        await update.message.reply_text(texto, parse_mode="Markdown")

    # --------------------------------------------------------------------------
    # 1. NOTAS DE VOZ (.ogg) INTELIGENTES (AVANCE CUADRILLA O LEVANTAMIENTO)
    # --------------------------------------------------------------------------
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        obra = supabase_service.get_or_create_active_obra(chat_id)
        user_name = update.effective_user.first_name or "Cuadrilla"
        
        status_msg = await update.message.reply_text("🎙️ *Escuchando y analizando nota de voz con IA...*", parse_mode="Markdown")

        try:
            voice = update.message.voice
            file_obj = await context.bot.get_file(voice.file_id)
            
            voice_buffer = io.BytesIO()
            await file_obj.download_to_memory(out=voice_buffer)
            audio_bytes = voice_buffer.getvalue()

            # Extracción unificada en 1 sola llamada (clasificación + partidas)
            extracted = await asyncio.to_thread(
                gemini_service.process_audio_or_field_message,
                audio_bytes=audio_bytes,
                mime_type="audio/ogg"
            )

            if extracted.get("error") and not extracted.get("partidas"):
                await status_msg.edit_text(f"⚠️ {extracted['error']}")
                return

            # Resolver contexto orquestado de obra y sesión
            context_res = await asyncio.to_thread(
                session_manager.resolve_context,
                chat_id=chat_id,
                audio_transcript=extracted.get("descripcion")
            )
            obra = context_res.obra

            if context_res.mensaje_aviso and context_res.accion in ["retoma_obra", "nueva_obra"]:
                await update.message.reply_text(context_res.mensaje_aviso, parse_mode="Markdown")

            levantamiento_skill.sync_session_from_db(chat_id, context_res.session_db)

            intencion = extracted.get("intencion", "levantamiento_nuevo")

            # Si es respuesta al loop de aclaración o levantamiento en curso
            if context_res.accion == "respuesta_aclaracion" or levantamiento_skill.has_active_session(chat_id):
                if intencion not in ["avance_cuadrilla", "parada_dano_oculto"]:
                    await self._process_levantamiento_flow(
                        update=update,
                        obra=obra,
                        audio_bytes=audio_bytes,
                        mime_type="audio/ogg",
                        status_msg=status_msg,
                        pre_extracted=extracted,
                        session_db=context_res.session_db
                    )
                    return

            if intencion == "avance_cuadrilla":
                await self._process_incident_or_progress_flow(
                    update=update,
                    obra=obra,
                    image_bytes=None,
                    audio_bytes=audio_bytes,
                    text_or_audio=extracted.get("descripcion") or "Reporte de avance por nota de voz de la cuadrilla",
                    chat_id=chat_id,
                    responsable_nombre=f"Cuadrilla ({user_name})",
                    status_msg=status_msg
                )
            elif intencion == "parada_dano_oculto":
                await self._process_incident_or_progress_flow(
                    update=update,
                    obra=obra,
                    image_bytes=None,
                    audio_bytes=audio_bytes,
                    text_or_audio=extracted.get("descripcion") or "Reporte de parada técnica o daño imprevisto por voz",
                    chat_id=chat_id,
                    responsable_nombre=f"Cuadrilla ({user_name})",
                    status_msg=status_msg
                )
            elif intencion == "editar_presupuesto":
                await self._process_edicion_presupuesto_flow(
                    update=update,
                    obra=obra,
                    edicion_data=extracted.get("edicion") or {},
                    status_msg=status_msg
                )
            else:
                await self._process_levantamiento_flow(
                    update=update,
                    obra=obra,
                    audio_bytes=audio_bytes,
                    mime_type="audio/ogg",
                    status_msg=status_msg,
                    pre_extracted=extracted,
                    session_db=context_res.session_db
                )
        except Exception as e:
            print(f"Error procesando voz en Telegram: {e}")
            await status_msg.edit_text(f"❌ Error al procesar audio: {str(e)}\n\nPuedes enviar las medidas por texto o intentar de nuevo.")

    async def handle_audio_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        obra = supabase_service.get_or_create_active_obra(chat_id)
        status_msg = await update.message.reply_text("🎵 *Procesando archivo de audio con IA...*", parse_mode="Markdown")

        try:
            audio = update.message.audio
            file_obj = await context.bot.get_file(audio.file_id)
            audio_buffer = io.BytesIO()
            await file_obj.download_to_memory(out=audio_buffer)
            audio_bytes = audio_buffer.getvalue()

            await self._process_levantamiento_flow(
                update=update,
                obra=obra,
                audio_bytes=audio_bytes,
                mime_type=audio.mime_type or "audio/ogg",
                status_msg=status_msg
            )
        except Exception as e:
            print(f"Error procesando archivo de audio: {e}")
            await status_msg.edit_text(f"❌ Error al procesar archivo de audio: {str(e)}")

    async def _process_levantamiento_flow(
        self, 
        update: Update, 
        obra: dict, 
        audio_bytes: Optional[bytes] = None, 
        text_prompt: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "audio/ogg",
        status_msg: Optional[Any] = None,
        pre_extracted: Optional[dict] = None,
        session_db: Optional[dict] = None
    ):
        if not status_msg:
            status_msg = await update.message.reply_text("📐 *Analizando levantamiento técnico con IA...*", parse_mode="Markdown")
        else:
            await status_msg.edit_text("📐 *Analizando levantamiento técnico con IA...*", parse_mode="Markdown")
        
        try:
            chat_id = update.effective_chat.id
            obra_id = obra["id"]
            obra_nombre = obra.get("nombre", "Obra")

            if pre_extracted and not text_prompt:
                text_prompt = pre_extracted.get("descripcion")

            # Asegurar contexto de sesión en Supabase si no vino precargado
            if not session_db:
                context_res = await asyncio.to_thread(
                    session_manager.resolve_context,
                    chat_id=chat_id,
                    text=text_prompt
                )
                session_db = context_res.session_db

            historial_mensajes = session_db.get("historial_mensajes") or []

            # Si se adjuntó una foto del área de trabajo, subirla a Supabase Storage / local
            foto_url = None
            if image_bytes:
                try:
                    foto_url = await asyncio.to_thread(
                        supabase_service.upload_file,
                        image_bytes,
                        "foto_area_levantamiento.jpg",
                        "image/jpeg"
                    )
                except Exception as efoto:
                    print(f"Aviso subiendo foto de área de trabajo: {efoto}")

            # Evaluar y acumular datos en el Loop de Levantamiento Incisivo
            resultado = await asyncio.to_thread(
                levantamiento_skill.evaluar_o_acumular,
                chat_id=chat_id,
                obra_id=obra_id,
                obra_nombre=obra_nombre,
                texto_usuario=text_prompt,
                audio_bytes=audio_bytes,
                image_bytes=image_bytes,
                foto_url=foto_url,
                historial_mensajes=historial_mensajes,
                mime_type=mime_type
            )

            # ------------------------------------------------------------------
            # 1. ESTADO: NECESITA ACLARACIÓN
            # El bot guarda el borrador en progreso y responde con la pregunta corta
            # y solicita foto del área de trabajo si aún no se tiene.
            # ------------------------------------------------------------------
            if resultado.estado == "necesita_aclaracion":
                pregunta = resultado.pregunta_corta or "¿Podrías indicar las dimensiones y tipo de material?"
                if resultado.solicitar_foto and not resultado.datos_acumulados.foto_area_url:
                    if "foto" not in pregunta.lower():
                        pregunta += "\n\n📸 *Por favor envía también una foto del área donde se va a trabajar.*"

                # Persistir sesión en estado 'esperando_aclaracion' con el borrador actualizado y los mensajes
                session_id = session_db.get("id") or str(uuid.uuid4())
                current_session = levantamiento_skill.get_session(chat_id)
                current_rounds = current_session.round_count if current_session else 1
                await asyncio.to_thread(
                    session_manager.save_session_state,
                    chat_id=chat_id,
                    session_id=session_id,
                    obra_id=obra_id,
                    obra_nombre=obra_nombre,
                    estado="esperando_aclaracion",
                    rondas_preguntas=current_rounds,
                    borrador_json=resultado.datos_acumulados.model_dump(),
                    user_msg=text_prompt,
                    bot_msg=pregunta
                )
                
                await status_msg.edit_text(pregunta, parse_mode="Markdown")
                return

            # ------------------------------------------------------------------
            # 2. ESTADO: LISTO PARA PRESUPUESTAR
            # Pasa datos_acumulados a calculator.py, genera y envía el PDF COVENIN y limpia sesión
            # ------------------------------------------------------------------
            partidas_input = levantamiento_skill.convertir_a_partidas_calculator(resultado.datos_acumulados)
            if not partidas_input:
                levantamiento_skill.clear_session(chat_id)
                session_id = session_db.get("id") if session_db else None
                if session_id:
                    await asyncio.to_thread(session_manager.complete_session, chat_id, session_id)
                await status_msg.edit_text("⚠️ No se identificaron partidas de construcción. Por favor detalla dimensiones (ej. pared 6x2.80, 30m2 pintura).")
                return

            tasa_bcv = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))
            precios_dict = supabase_service.get_catalogo_precios_dict()
            presupuesto_calc = ConstructionCalculator.procesar_presupuesto(
                partidas_raw=partidas_input,
                tasa_bcv=tasa_bcv,
                precios_personalizados=precios_dict
            )

            obra_id = obra["id"]
            for p in presupuesto_calc.partidas:
                p_data = p.model_dump()
                p_data["obra_id"] = obra_id
                supabase_service.save_partida(p_data)

            hoja_items = [h.model_dump() for h in presupuesto_calc.hoja_compras]
            supabase_service.save_hoja_compras(obra_id, hoja_items)

            supabase_service.update_obra(obra_id, {
                "presupuesto_total_usd": presupuesto_calc.total_general_usd,
                "presupuesto_total_bs": presupuesto_calc.total_general_bs
            })

            # Si se recibió foto del área de trabajo, registrarla en el diario de obra
            if resultado.datos_acumulados.foto_area_url:
                try:
                    supabase_service.save_diario_obra({
                        "obra_id": obra_id,
                        "tipo": "inspeccion",
                        "titulo": "Levantamiento Inicial y Cómputos Métricos",
                        "descripcion": "Foto del área de trabajo inspeccionada para cómputos métricos COVENIN.",
                        "foto_url": resultado.datos_acumulados.foto_area_url,
                        "responsable_nombre": "Inspección Técnica"
                    })
                except Exception as ed:
                    print(f"Aviso guardando diario de obra con foto de área: {ed}")

            lineas_partidas = []
            for p in presupuesto_calc.partidas:
                lineas_partidas.append(f"• `[{p.codigo_covenin}]` *{p.descripcion}*: ${p.total_usd:,.2f} | Bs. {p.total_bs:,.2f}")

            lineas_materiales = []
            for m in presupuesto_calc.hoja_compras[:5]:
                lineas_materiales.append(f"  - {m.material}: {m.cantidad_requerida:g} {m.unidad}")
            if len(presupuesto_calc.hoja_compras) > 5:
                lineas_materiales.append(f"  - y {len(presupuesto_calc.hoja_compras) - 5} materiales más...")

            link_web = f"{settings.FRONTEND_URL}/presupuestos?obra_id={obra_id}"
            foto_tag = "📸 *Foto del Área:* Registrada e inspeccionada con IA\n" if resultado.datos_acumulados.foto_area_url else ""

            respuesta = (
                f"✅ *PRESUPUESTO ESTIMADO (NORMA COVENIN)*\n"
                f"🏗️ *Obra:* `{obra['nombre']}`\n"
                f"💵 *Tasa BCV:* `{tasa_bcv:,.2f} Bs/$`\n"
                f"{foto_tag}\n"
                "*Partidas de Obra (Cómputos Métricos):*\n" + "\n".join(lineas_partidas) + "\n\n"
                "📦 *Lista Resumida de Compras:*\n" + "\n".join(lineas_materiales) + "\n\n"
                f"💼 *Subtotal:* ${presupuesto_calc.subtotal_usd:,.2f} (Bs. {presupuesto_calc.subtotal_bs:,.2f})\n"
                f"🏛️ *Cargas e Indirectos (Ley Pensiones):* ${presupuesto_calc.total_cargas_usd:,.2f}\n"
                f"💰 *TOTAL PRESUPUESTO:* *${presupuesto_calc.total_general_usd:,.2f}* (Bs. {presupuesto_calc.total_general_bs:,.2f})\n\n"
                f"🔗 *Ver tabla completa y compras:* [Abrir Presupuesto]({link_web})"
            )
            await status_msg.edit_text(respuesta, parse_mode="Markdown")

            # Generar y enviar PDF oficial por Telegram listo para el cliente final
            try:
                pdf_buffer = PDFPresupuestoGenerator.generar_presupuesto_pdf(
                    obra=obra,
                    presupuesto=presupuesto_calc,
                    codigo_presupuesto=f"OBX-PRE-{str(obra_id)[:8].upper()}"
                )
                clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', obra.get("nombre", "Obra"))[:25]
                caption_pdf = (
                    f"📄 *Presupuesto Formal (Norma COVENIN)* listo para cliente.\n"
                    f"💰 Total: *${presupuesto_calc.total_general_usd:,.2f} USD* | Bs. {presupuesto_calc.total_general_bs:,.2f}"
                )
                await update.message.reply_document(
                    document=pdf_buffer,
                    filename=f"Presupuesto_{clean_name}.pdf",
                    caption=caption_pdf,
                    parse_mode="Markdown"
                )
            except Exception as epdf:
                print(f"Aviso generando/enviando PDF en Telegram: {epdf}")

            # Persistir estado completado en Supabase y liberar sesión
            session_id = session_db.get("id") if session_db else None
            if session_id:
                await asyncio.to_thread(
                    session_manager.complete_session,
                    chat_id=chat_id,
                    session_id=session_id,
                    borrador_final=resultado.datos_acumulados.model_dump()
                )
            levantamiento_skill.clear_session(chat_id)

        except Exception as e:
            print(f"Error procesando levantamiento: {e}")
            await status_msg.edit_text(f"❌ Ocurrió un error al procesar el levantamiento: {str(e)}")

    # --------------------------------------------------------------------------
    # EDICIÓN CONVERSACIONAL DE PRESUPUESTOS Y MEMORIA OPERATIVA
    # --------------------------------------------------------------------------
    async def _process_edicion_presupuesto_flow(
        self,
        update: Update,
        obra: dict,
        edicion_data: dict,
        status_msg: Optional[Any] = None
    ):
        if not status_msg:
            status_msg = await update.message.reply_text("✏️ *Aplicando ajuste al presupuesto y guardando en tu memoria de precios...*", parse_mode="Markdown")
        else:
            await status_msg.edit_text("✏️ *Aplicando ajuste al presupuesto y guardando en tu memoria de precios...*", parse_mode="Markdown")

        try:
            obra_id = obra["id"]
            accion = edicion_data.get("accion", "modificar_precio")
            target = str(edicion_data.get("partida_o_material", "")).strip().lower()
            nombre_ref = edicion_data.get("nombre_referencia", target)
            nuevo_val = float(edicion_data.get("nuevo_valor", 0.0))
            proveedor = edicion_data.get("proveedor")
            unidad = edicion_data.get("unidad", "und")

            # 1. Obtener partidas actuales de la obra
            partidas_actuales = supabase_service.get_partidas(obra_id)
            if not partidas_actuales:
                await status_msg.edit_text("⚠️ No hay partidas registradas en el presupuesto actual para modificar. Envía primero tus medidas o una nota de voz.")
                return

            cambio_desc = ""
            valor_anterior_str = "Catálogo estándar"

            # 2. Registrar el cambio y actualizar catálogo de precios del usuario
            if accion == "modificar_precio":
                supabase_service.save_catalogo_precio({
                    "clave_o_codigo": target,
                    "nombre": nombre_ref,
                    "tipo": edicion_data.get("tipo_objetivo", "material"),
                    "unidad": unidad,
                    "precio_usd": nuevo_val,
                    "proveedor_opcional": proveedor
                })
                prov_str = f" con {proveedor}" if proveedor else ""
                cambio_desc = f"Precio de *{nombre_ref}* ajustado a *${nuevo_val:,.2f}/{unidad}*{prov_str}"

                supabase_service.save_edicion({
                    "obra_id": obra_id,
                    "accion": "modificar_precio",
                    "partida_o_material": target,
                    "valor_anterior": valor_anterior_str,
                    "valor_nuevo": f"${nuevo_val:,.2f} USD{prov_str}",
                    "detalles": edicion_data
                })

            elif accion == "modificar_cantidad":
                found = False
                for p in partidas_actuales:
                    if p.get("tipo_partida") == target or target in p.get("descripcion", "").lower():
                        cant_orig = float(p.get("cantidad", 1.0))
                        valor_anterior_str = f"{cant_orig:g} {p.get('unidad', 'und')}"
                        # Si dijo 'agrega 4 más'
                        if "agrega" in str(edicion_data).lower() or "suma" in str(edicion_data).lower() or "mas" in str(edicion_data).lower():
                            nueva_cant = cant_orig + nuevo_val
                        else:
                            nueva_cant = nuevo_val
                        p["cantidad"] = nueva_cant
                        if p.get("unidad") == "m2" and p.get("largo") and p.get("alto"):
                            p["area"] = round(nueva_cant, 2)
                        supabase_service.update_partida(p["id"], {"cantidad": nueva_cant, "area": p.get("area", nueva_cant)})
                        cambio_desc = f"Cantidad de *{p.get('descripcion')}* actualizada de {valor_anterior_str} a *{nueva_cant:g} {p.get('unidad')}*"
                        found = True
                        break
                
                if not found and partidas_actuales:
                    p = partidas_actuales[0]
                    p["cantidad"] = nuevo_val
                    supabase_service.update_partida(p["id"], {"cantidad": nuevo_val})
                    cambio_desc = f"Cantidad de *{p.get('descripcion')}* ajustada a *{nuevo_val:g}*"

                supabase_service.save_edicion({
                    "obra_id": obra_id,
                    "accion": "modificar_cantidad",
                    "partida_o_material": target,
                    "valor_anterior": valor_anterior_str,
                    "valor_nuevo": f"{nuevo_val:g}",
                    "detalles": edicion_data
                })

            # 3. Recalcular determinísticamente todo el presupuesto con memoria de precios
            precios_dict = supabase_service.get_catalogo_precios_dict()
            tasa_bcv = float(obra.get("tasa_bcv", settings.TASA_BCV_DEFAULT))
            
            partidas_input = [
                PartidaInput(
                    tipo_partida=p.get("tipo_partida", "otro"),
                    descripcion=p.get("descripcion"),
                    codigo_covenin=p.get("codigo_covenin"),
                    largo=p.get("largo", 0.0),
                    alto=p.get("alto", 0.0),
                    cantidad=p.get("cantidad", 1.0),
                    area=p.get("area", 0.0),
                    unidad=p.get("unidad", "m2")
                )
                for p in partidas_actuales
            ]

            presupuesto_calc = ConstructionCalculator.procesar_presupuesto(
                partidas_raw=partidas_input,
                tasa_bcv=tasa_bcv,
                precios_personalizados=precios_dict
            )

            # 4. Actualizar partidas en base de datos
            for idx, p_calc in enumerate(presupuesto_calc.partidas):
                if idx < len(partidas_actuales):
                    p_orig_id = partidas_actuales[idx]["id"]
                    supabase_service.update_partida(p_orig_id, {
                        "p_unit_usd": p_calc.p_unit_usd,
                        "total_usd": p_calc.total_usd,
                        "p_unit_bs": p_calc.p_unit_bs,
                        "total_bs": p_calc.total_bs,
                        "costo_materiales_usd": p_calc.costo_materiales_usd,
                        "costo_mano_obra_usd": p_calc.costo_mano_obra_usd
                    })

            hoja_items = [h.model_dump() for h in presupuesto_calc.hoja_compras]
            supabase_service.save_hoja_compras(obra_id, hoja_items)

            supabase_service.update_obra(obra_id, {
                "presupuesto_total_usd": presupuesto_calc.total_general_usd,
                "presupuesto_total_bs": presupuesto_calc.total_general_bs
            })

            lineas_partidas = [
                f"• `[{p.codigo_covenin}]` *{p.descripcion}*: ${p.total_usd:,.2f} | Bs. {p.total_bs:,.2f}"
                for p in presupuesto_calc.partidas
            ]

            link_web = f"{settings.FRONTEND_URL}/presupuestos?obra_id={obra_id}"
            respuesta = (
                f"✏️ *PRESUPUESTO ACTUALIZADO (v2)*\n"
                f"🏗️ *Obra:* `{obra['nombre']}`\n\n"
                f"🔧 *Ajuste aplicado:* {cambio_desc}\n"
                f"💾 *Memoria Operativa:* Guardado en tu catálogo para futuros presupuestos.\n\n"
                f"*Partidas Recalculadas (COVENIN):*\n" + "\n".join(lineas_partidas) + "\n\n"
                f"💼 *Subtotal:* ${presupuesto_calc.subtotal_usd:,.2f} (Bs. {presupuesto_calc.subtotal_bs:,.2f})\n"
                f"🏛️ *Cargas e Indirectos:* ${presupuesto_calc.total_cargas_usd:,.2f}\n"
                f"💰 *NUEVO TOTAL PRESUPUESTO:* *${presupuesto_calc.total_general_usd:,.2f}* (Bs. {presupuesto_calc.total_general_bs:,.2f})\n\n"
                f"🔗 *Ver en vivo:* [Abrir Presupuesto]({link_web})"
            )
            await status_msg.edit_text(respuesta, parse_mode="Markdown")

            # 5. Generar y enviar PDF v2 actualizado por Telegram
            try:
                pdf_buffer = PDFPresupuestoGenerator.generar_presupuesto_pdf(
                    obra=obra,
                    presupuesto=presupuesto_calc,
                    codigo_presupuesto=f"OBX-PRE-{str(obra_id)[:8].upper()}-V2"
                )
                clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', obra.get("nombre", "Obra"))[:25]
                caption_pdf = (
                    f"📄 *Presupuesto Actualizado v2 (Norma COVENIN)* con tus nuevos precios aplicados.\n"
                    f"💰 Total: *${presupuesto_calc.total_general_usd:,.2f} USD* | Bs. {presupuesto_calc.total_general_bs:,.2f}"
                )
                await update.message.reply_document(
                    document=pdf_buffer,
                    filename=f"Presupuesto_{clean_name}_v2.pdf",
                    caption=caption_pdf,
                    parse_mode="Markdown"
                )
            except Exception as epdf:
                print(f"Aviso generando/enviando PDF v2 en Telegram: {epdf}")

        except Exception as e:
            print(f"Error procesando edición de presupuesto: {e}")
            await status_msg.edit_text(f"❌ Error al aplicar ajuste al presupuesto: {str(e)}")

    # --------------------------------------------------------------------------
    # 2. FOTOS DE LA CUADRILLA: AVANCE O FACTURAS
    # --------------------------------------------------------------------------
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        obra = supabase_service.get_or_create_active_obra(chat_id)
        user_name = update.effective_user.first_name or "Cuadrilla"
        caption = update.message.caption or ""
        caption_lower = caption.lower()

        photo = update.message.photo[-1]
        file_obj = await context.bot.get_file(photo.file_id)
        
        photo_buffer = io.BytesIO()
        await file_obj.download_to_memory(out=photo_buffer)
        image_bytes = photo_buffer.getvalue()

        # Detección:
        es_factura = any(w in caption_lower for w in ["factura", "compra", "ferreteria", "recibo", "nota de entrega", "gasto", "epa"])
        es_dano = any(w in caption_lower for w in ["dano", "daño", "parada", "paro", "tuberia", "filtracion", "roto", "fuga", "oculto"])

        if es_factura:
            await self._process_invoice_flow(update, obra, image_bytes)
        elif es_dano:
            await self._process_incident_or_progress_flow(
                update=update,
                obra=obra,
                image_bytes=image_bytes,
                text_or_audio=caption,
                chat_id=chat_id,
                responsable_nombre=f"Cuadrilla ({user_name})"
            )
        elif levantamiento_skill.has_active_session(chat_id):
            # El usuario está enviando la foto solicitada del área donde se va a trabajar
            context_res = await asyncio.to_thread(
                session_manager.resolve_context,
                chat_id=chat_id,
                text=caption
            )
            obra = context_res.obra
            levantamiento_skill.sync_session_from_db(chat_id, context_res.session_db)
            status_msg = await update.message.reply_text("📸 *Analizando foto del área de trabajo con IA...*", parse_mode="Markdown")
            await self._process_levantamiento_flow(
                update=update,
                obra=obra,
                image_bytes=image_bytes,
                text_prompt=caption or None,
                status_msg=status_msg,
                session_db=context_res.session_db
            )
        elif any(w in caption_lower for w in ["levantamiento", "cotizar", "presupuesto", "pared", "medidas", "m2", "metro"]):
            # Nueva solicitud de levantamiento iniciada con foto del área y medidas en caption
            context_res = await asyncio.to_thread(
                session_manager.resolve_context,
                chat_id=chat_id,
                text=caption
            )
            obra = context_res.obra
            levantamiento_skill.sync_session_from_db(chat_id, context_res.session_db)
            status_msg = await update.message.reply_text("📐 *Iniciando levantamiento desde foto con IA...*", parse_mode="Markdown")
            await self._process_levantamiento_flow(
                update=update,
                obra=obra,
                image_bytes=image_bytes,
                text_prompt=caption,
                status_msg=status_msg,
                session_db=context_res.session_db
            )
        else:
            # Por defecto en obra de campo: una foto subida por la cuadrilla es EVIDENCIA DE AVANCE
            await self._process_incident_or_progress_flow(
                update=update,
                obra=obra,
                image_bytes=image_bytes,
                text_or_audio=caption or "Evidencia fotográfica de avance físico de obra",
                chat_id=chat_id,
                responsable_nombre=f"Cuadrilla ({user_name})"
            )

    async def _process_invoice_flow(self, update: Update, obra: dict, image_bytes: bytes):
        status_msg = await update.message.reply_text("🧾 *Analizando factura con Pillow, Gemini y verificación anti-fraude...*", parse_mode="Markdown")
        try:
            res = await asyncio.to_thread(
                invoice_service.audit_and_process_invoice,
                image_bytes=image_bytes,
                obra_id=obra["id"],
                filename="factura_telegram.jpg"
            )

            if res.get("status") == "error_duplicate":
                await status_msg.edit_text(
                    f"🚨 *ALERTA ROJA - FACTURA DUPLICADA RECHAZADA*\n\n"
                    f"{res['detalle_alerta']}\n"
                    f"🔒 *Seguridad SHA-256:* Se evitó un desembolso duplicado no autorizado.",
                    parse_mode="Markdown"
                )
                return

            if res.get("status") == "error_unreadable":
                await status_msg.edit_text(
                    f"⚠️ *NO SE PUDO LEER LA FACTURA*\n\n"
                    f"{res.get('detalle_alerta')}\n\n"
                    f"💡 *Sugerencias:*\n"
                    f"• Toma una foto clara, perpendicular y con buena luz.\n"
                    f"• O escribe el gasto en texto: `Factura Ferretería EPA $120`.",
                    parse_mode="Markdown"
                )
                return

            factura = res.get("factura", {})
            total_usd = float(factura.get("total_usd", 0.0))
            total_bs = float(factura.get("total_bs", 0.0))
            proveedor = factura.get("proveedor", "Proveedor")
            margen_restante_usd = res.get("margen_restante_usd", 0.0)
            margen_restante_pct = res.get("margen_restante_pct", 0.0)
            alerta_roja = res.get("alerta_roja", False)

            alerta_banner = ""
            if alerta_roja:
                alerta_banner = f"\n\n🚨 *ALERTA DE AUDITORÍA:*\n⚠️ {res.get('detalle_alerta')}\n"

            msg = (
                f"🧾 *FACTURA PROCESADA EXITOSAMENTE*\n"
                f"🏬 *Proveedor:* {proveedor}\n"
                f"💵 *Monto:* ${total_usd:,.2f} | Bs. {total_bs:,.2f}\n"
                f"📊 *Nuevo Total Gastado:* ${res.get('nuevo_gastado_usd', 0):,.2f}\n"
                f"💼 *Margen Restante:* ${margen_restante_usd:,.2f} ({margen_restante_pct}% de la obra)"
                f"{alerta_banner}\n\n"
                f"🔗 *Ver en Compras:* [Ver Dashboard]({settings.FRONTEND_URL}/compras?obra_id={obra['id']})"
            )
            await status_msg.edit_text(msg, parse_mode="Markdown")

        except Exception as e:
            print(f"Error procesando factura: {e}")
            await status_msg.edit_text(f"❌ Error al procesar factura: {str(e)}")

    async def _process_incident_or_progress_flow(
        self, 
        update: Update, 
        obra: dict, 
        image_bytes: Optional[bytes], 
        text_or_audio: str, 
        chat_id: int,
        audio_bytes: Optional[bytes] = None,
        responsable_nombre: str = "Cuadrilla",
        status_msg: Optional[Any] = None
    ):
        if not status_msg:
            status_msg = await update.message.reply_text("🔍 *Procesando reporte de cuadrilla con IA...*", parse_mode="Markdown")
        else:
            await status_msg.edit_text("🔍 *Evaluando reporte de cuadrilla con IA...*", parse_mode="Markdown")

        try:
            result = await asyncio.to_thread(
                site_log_service.process_progress_or_incident,
                obra_id=obra["id"],
                image_bytes=image_bytes,
                text_or_audio=text_or_audio,
                audio_bytes=audio_bytes,
                filename="evidencia_cuadrilla.jpg",
                chat_id=chat_id,
                responsable_nombre=responsable_nombre
            )

            if result.get("tipo") == "parada_dano_oculto":
                msg = (
                    f"⚠️ *PARADA POR DAÑO OCULTO REGISTRADA*\n\n"
                    f"📋 *Incidencia:* {result['incidencia']['titulo']}\n"
                    f"📝 *Detalle:* {result['incidencia']['descripcion']}\n"
                    f"👤 *Reportó:* {responsable_nombre}\n\n"
                    f"💰 *Costo Adicional Estimado:* ${result['costo_adicional_usd']:,.2f} (Bs. {result['costo_adicional_bs']:,.2f})\n"
                    f"📈 *Variación Contrato Base:* `+{result['porcentaje_variacion']:.2f}%`\n\n"
                    f"📲 *ENLACE MÓVIL PARA REENVIAR AL CLIENTE:*\n"
                    f"{result['link_aprobacion']}\n\n"
                    f"El cliente podrá ver la foto y aprobar el adicional en 1 click desde su celular."
                )
                await status_msg.edit_text(msg, parse_mode="Markdown")
            else:
                msg = result.get("mensaje") or (
                    f"📈 *¡AVANCE DE CUADRILLA REGISTRADO!*\n\n"
                    f"✅ {result.get('porcentaje', 0):.0f}% completado.\n"
                    f"📸 Foto guardada y transmitida en vivo al Dashboard.\n"
                    f"🔗 [Ver en Dashboard]({settings.FRONTEND_URL}/avance?obra_id={obra['id']})"
                )
                await status_msg.edit_text(msg, parse_mode="Markdown")

        except Exception as e:
            print(f"Error procesando reporte: {e}")
            await status_msg.edit_text(f"❌ Error al registrar reporte: {str(e)}")

    # --------------------------------------------------------------------------
    # 3. MENSAJES DE TEXTO
    # --------------------------------------------------------------------------
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_name = update.effective_user.first_name or "Cuadrilla"
        texto = update.message.text or ""
        lower = texto.lower()

        # Si el usuario quiere cancelar o reiniciar el levantamiento activo
        if lower.strip() in ["cancelar", "cancelar levantamiento", "salir", "reiniciar"]:
            levantamiento_skill.clear_session(chat_id)
            session_manager.clear_chat_sessions(chat_id)
            await update.message.reply_text("❌ Levantamiento técnico cancelado.")
            return

        # Resolver contexto orquestado de obra y sesión
        context_res = await asyncio.to_thread(
            session_manager.resolve_context,
            chat_id=chat_id,
            text=texto
        )
        obra = context_res.obra

        # Si detectó retoma de obra o nueva obra, enviar aviso
        if context_res.mensaje_aviso and context_res.accion in ["retoma_obra", "nueva_obra"]:
            await update.message.reply_text(context_res.mensaje_aviso, parse_mode="Markdown")

        # Sincronizar el borrador persistente en levantamiento_skill
        levantamiento_skill.sync_session_from_db(chat_id, context_res.session_db)

        # REGLA 4: Si ya tiene una sesión en estado 'esperando_aclaracion', asume que el mensaje es la respuesta
        if context_res.accion == "respuesta_aclaracion" or levantamiento_skill.has_active_session(chat_id):
            await self._process_levantamiento_flow(
                update=update,
                obra=obra,
                text_prompt=texto,
                session_db=context_res.session_db
            )
            return

        # Si menciona edición de presupuesto o cambios de precio / cantidad
        if any(w in lower for w in ["cambia", "cámbiale", "sube", "baja", "ajusta", "agrega", "pon el bloque", "pon la pintura", "precio de"]):
            extracted = await asyncio.to_thread(
                gemini_service.process_audio_or_field_message,
                text_prompt=texto
            )
            if extracted.get("intencion") == "editar_presupuesto" and extracted.get("edicion"):
                await self._process_edicion_presupuesto_flow(
                    update=update,
                    obra=obra,
                    edicion_data=extracted["edicion"]
                )
                return

        # Si el texto describe una parada o daño
        if any(w in lower for w in ["dano", "daño", "parada", "paro", "tuberia", "filtracion", "roto", "oculto"]):
            await self._process_incident_or_progress_flow(
                update=update, 
                obra=obra, 
                image_bytes=None, 
                text_or_audio=texto, 
                chat_id=chat_id,
                responsable_nombre=f"Cuadrilla ({user_name})"
            )
        # Si menciona avance de cuadrilla
        elif any(w in lower for w in ["avance", "%", "completado", "terminado", "terminamos", "listo", "listas", "colocado", "frisado", "pintado", "cuadrilla"]):
            await self._process_incident_or_progress_flow(
                update=update, 
                obra=obra, 
                image_bytes=None, 
                text_or_audio=texto, 
                chat_id=chat_id,
                responsable_nombre=f"Cuadrilla ({user_name})"
            )
        # Si es levantamiento o cubicación
        else:
            await self._process_levantamiento_flow(
                update=update,
                obra=obra,
                text_prompt=texto,
                session_db=context_res.session_db
            )

    # --------------------------------------------------------------------------
    # NOTIFICACIÓN AUTOMÁTICA AL INGENIERO TRAS APROBACIÓN
    # --------------------------------------------------------------------------
    async def notificar_aprobacion_adicional(self, chat_id: int, incidencia: dict):
        if not self.app or not self.app.bot:
            return
        try:
            costo = float(incidencia.get("costo_adicional_usd", 0.0))
            tasa = settings.TASA_BCV_DEFAULT
            bs = float(incidencia.get("costo_adicional_bs", costo * tasa))
            msg = (
                f"🎉 *¡ADICIONAL APROBADO POR EL CLIENTE!*\n\n"
                f"✅ El cliente *{incidencia.get('cliente_nombre', 'Cliente')}* acaba de aprobar el adicional:\n"
                f"📌 *{incidencia.get('titulo')}*\n"
                f"💰 *Monto Aprobado:* ${costo:,.2f} (Bs. {bs:,.2f})\n"
                f"📈 *Variación Contrato:* `+{incidencia.get('porcentaje_variacion', 0):.2f}%`\n"
                f"⏰ *Fecha:* {incidencia.get('aprobado_en', 'Reciente')}\n\n"
                f"Los trabajos pueden continuar de inmediato."
            )
            await self.app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            print(f"Error enviando notificación Telegram de aprobación: {e}")

telegram_bot = ObraExactaTelegramBot()
