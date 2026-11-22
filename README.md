# 🏗️ ObraExacta - MVP Track Contratistas

**ObraExacta** es la plataforma integral para contratistas e ingenieros civiles en Venezuela y Latinoamérica que une la agilidad del campo (vía notas de voz y fotos en **Telegram**) con el rigor del control financiero y de obra en un **Dashboard Next.js de Alto Contraste**.

---

## 🏛️ Arquitectura del Monorepo

```
/
├── backend/                  # Python 3.12+ / FastAPI + python-telegram-bot + Gemini 2.5 Flash
│   ├── main.py               # Servidor FastAPI con Long Polling de Telegram en evento lifespan
│   ├── config.py             # Configuración pydantic-settings
│   ├── database.sql          # Schema completo Supabase (PostgreSQL, Storage, Realtime y RLS)
│   ├── bot/
│   │   └── telegram_bot.py   # Bot Telegram v21+ asíncrono (Audio .ogg, Fotos, Texto)
│   ├── services/
│   │   ├── calculator.py     # Motor Determinista en Python (rendimientos tabulados y 6 columnas)
│   │   ├── gemini_service.py # Extracción estructurada con Gemini 2.5 Flash
│   │   ├── invoice_service.py# Pillow + SHA-256 anti-duplicados + auditoría de compras
│   │   ├── site_log_service.py# Libro de obra, variación contractual y token de aprobación
│   │   └── supabase_service.py# Cliente Supabase con fallback local reactivo
│   ├── routers/
│   │   └── api.py            # Endpoints REST (Respaldo Web Total)
│   ├── test_calculator.py    # Tests unitarios del motor determinista
│   └── test_api_integration.py# Tests de integración end-to-end
│
└── frontend/                 # Next.js App Router + TypeScript + Tailwind CSS
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx     # Shell global en modo oscuro de alto contraste
    │   │   ├── presupuestos/  # Vista 1: Tabla de 6 columnas y Hoja de Compras consolidada
    │   │   ├── compras/       # Vista 2: Presupuestado vs. Gastado y alertas de fuga
    │   │   ├── avance/        # Vista 3: Avance Global Ponderado y barras individuales (0-100%)
    │   │   ├── libro-de-obra/ # Vista 4: Registro de paradas y generador de enlaces móviles
    │   │   └── aprobar/[id]/  # Vista Pública Móvil: Aprobación en 1 toque por el cliente
    │   ├── components/        # Sidebar colapsable, Header, Modales de Respaldo Web Total
    │   └── lib/               # Clientes de API, tipos y suscripción a Supabase Realtime
```

---

## ⚡ 1. Bot de Telegram Integrado Directamente en FastAPI

- **Sin túneles ni webhooks externos:** Corre directamente mediante **Long Polling** asíncrono dentro del ciclo de vida (`lifespan`) de FastAPI en `backend/main.py`. Un solo comando `uvicorn main:app` arranca simultáneamente la API y el Bot.
- **Flujos en Campo:**
  1. **Notas de Voz (`.ogg`) / Texto de Levantamiento:** Descarga en memoria (`bytearray`), envía directo a **Gemini 2.5 Flash** (`audio/ogg`) para extraer un JSON estricto (`tipo_partida`, `largo`, `alto`, `cantidad`, `obra`), lo procesa en el motor determinista en Python, lo guarda en Supabase y responde con el resumen bimonetario (USD y Bs. BCV), lista de materiales y enlace directo a la tabla.
  2. **Foto de Factura de Ferretería:** Optimiza en memoria con **Pillow**, calcula el hash **SHA-256 anti-duplicados**, extrae ítems/montos con Gemini, descuenta del presupuesto y responde con el margen restante o **Alerta Roja** si detecta sobreprecio, material fuera de partida o duplicidad.
  3. **Foto + Audio de Avance o Daño Oculto:** Si es avance, actualiza el % de la partida y guarda la foto en Supabase Storage; si es parada técnica por daño oculto, registra la incidencia en el Libro de Obra, calcula la variación contractual y envía el enlace móvil listo para reenviar al cliente (`/aprobar/[id]`).

---

## 📐 2. Motor Determinista en Python (`calculator.py`)

> **Regla de Oro:** Gemini NUNCA calcula precios ni cantidades de materiales; solo extrae los parámetros de la voz o imagen. Todo cálculo lo ejecuta Python con rendimientos tabulados exactos:

- `pared_bloque`: Área (largo × alto) → 14 bloques/m², 0.08 m³ arena/m², 0.35 sacos cemento/m².
- `pintura`: Área → 0.04 galones/m² (2 manos).
- `ceramica`: Área → 1.05 m² cerámica (5% desperdicio) + 0.25 sacos pego/m².
- `cielo_raso`: Área → láminas yeso 1.05 m² + perfilería 1.80 ml/m².
- `lampara`: piezas + mano de obra unitaria.
- **Tabla Bimonetaria de 6 Columnas:** `Partida | Unidad | P. Unit $ | Total $ | P. Unit Bs | Total Bs` a Tasa BCV editable.
- **Cargas Fiscales:** Bloque editable (ej. 9% Ley de Protección de Pensiones sobre mano de obra, imprevistos/administración).
- **Hoja de Compras Estimada:** Consolidación automática agrupando todos los materiales de todas las partidas.

---

## 🖥️ 3. Dashboard en Next.js (4 Vistas + Ruta Móvil de Aprobación)

1. **Presupuestos (Voz / Telegram):** Tabla interactiva de 6 columnas, tasa BCV editable en el header, bloque de pensiones/indirectos y pestaña para la Hoja de Compras.
2. **Compras y Gastos:** Barra de Presupuestado vs. Gastado Real, margen restante, control SHA-256 e historial con alertas de sobreprecio.
3. **Avance por Partida:** Barra maestra de **Avance Global Ponderado**, barras individuales (0-100%) y galería fotográfica de respaldo.
4. **Libro de Obra y Adicionales:** Bitácora de paradas con cálculo de % de variación y generador de enlace `/aprobar/[id]`.
5. **Ruta Pública Móvil (`/aprobar/[id]`):** Interfaz mobile-first donde el cliente revisa la foto del daño, el costo en USD/Bs., presiona *"Aprobar Adicional"* y notifica automáticamente al chat de Telegram del contratista en tiempo real.
- **Botón Discreto "Cargar Obra Demo":** Permite probar inmediatamente toda la funcionalidad sin configurar base de datos externa ni claves.

---

## 🚀 Puesta en Marcha Rápida

### Backend (Python + FastAPI + Bot de Telegram)
```bash
cd backend
# Crear y activar entorno virtual
python -m venv .venv
# En Windows:
.venv\Scripts\activate
# En Linux/macOS:
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt  # o uv pip install ...

# Ejecutar tests deterministas y de integración
python test_calculator.py
python test_api_integration.py

# Iniciar servidor y Bot
uvicorn main:app --reload --port 8000
```
uvicorn main:app --reload --port 8000
### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
# Abrir http://localhost:3000
```

---

## 🤖 4. Conexión del Servidor MCP (Model Context Protocol) en Gemini / Antigravity / Cursor

ObraExacta expone un servidor **FastMCP** con transporte HTTP/SSE y aislamiento estricto por usuario:

### URL de Conexión MCP
- **Endpoint Integrado (FastAPI):** `http://localhost:8000/mcp/sse`
- **Endpoint Servidor Dedicado:** `http://localhost:8001/sse` (ejecutando `python mcp_server.py --port 8001`)

### Autenticación Multiusuario
Cada contratista tiene una clave personal `api_key_mcp` (visible y copiable en la barra lateral del dashboard, ej: `obx_mcp_demo_7f8a9b2c3d4e5f6a7b8c9d0e`).
El servidor MCP valida la clave mediante:
- Header HTTP: `Authorization: Bearer <api_key_mcp>` o `X-API-Key: <api_key_mcp>`
- Parámetro de herramienta: `api_key_mcp="<tu_clave>"` (opcional para clientes que no envían headers personalizados).

### 🛠️ Las 4 Herramientas Deterministas Expuestas

1. `listar_obras_usuario()`:
   - Devuelve las obras activas, presupuesto base contratado, total gastado y margen disponible exclusivamente de ese contratista.
2. `consultar_precios_y_covenin()`:
   - Devuelve el catálogo de partidas oficiales COVENIN de Venezuela y los precios unitarios de materiales y mano de obra personalizados por ese contratista.
3. `evaluar_levantamiento(obra_nombre, descripcion_trabajo)`:
   - Aplica el Loop Incisivo: si faltan datos críticos, formula hasta 2 preguntas aclaratorias cortas de campo; si la información está completa, calcula deterministamente el presupuesto COVENIN.
4. `obtener_resumen_obra(obra_nombre)`:
   - Devuelve el resumen integral de la obra: partidas, avance ponderado y por cuadrilla, facturas/gastos registrados y variación por órdenes de trabajo adicionales (daños ocultos).

### 📋 Configuración en Clientes MCP

#### En Gemini / Antigravity / Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "obraexacta": {
      "url": "http://localhost:8000/mcp/sse",
      "headers": {
        "Authorization": "Bearer obx_mcp_demo_7f8a9b2c3d4e5f6a7b8c9d0e"
      }
    }
  }
}
```

#### Modo CLI Stdio (Opcional):
```json
{
  "mcpServers": {
    "obraexacta_local": {
      "command": "python",
      "args": ["c:/SaaS/backend/mcp_server.py", "--transport", "stdio"]
    }
  }
}
```

