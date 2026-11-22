import io
import datetime
from typing import Dict, Any, Optional
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from services.calculator import PresupuestoCompleto

def clean_pdf_str(text: Any) -> str:
    """Sanitiza texto para fuentes estándar de PDF (latin-1) reemplazando símbolos especiales."""
    if text is None:
        return ""
    s = str(text)
    s = s.replace("•", "-").replace("—", "-").replace("–", "-")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("²", "2").replace("³", "3")
    return s.encode("latin-1", errors="replace").decode("latin-1")


class ObraExactaPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.obra_nombre = "Obra"
        self.tasa_bcv = 918.77

    def header(self):
        # Fondo decorativo superior
        self.set_fill_color(15, 23, 42)  # Slate 900
        self.rect(0, 0, 210, 18, 'F')
        
        self.set_font('helvetica', 'B', 10)
        self.set_text_color(249, 115, 22)  # Orange 500
        self.set_xy(10, 4)
        self.cell(0, 5, 'OBRAEXACTA  |  SISTEMA DE CONTROL DE OBRAS Y PRESUPUESTOS', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        self.set_font('helvetica', '', 7)
        self.set_text_color(203, 213, 225)  # Slate 300
        self.set_xy(10, 10)
        self.cell(0, 4, clean_pdf_str(f'Norma COVENIN Venezuela  |  Tasa Oficial BCV: {self.tasa_bcv:,.2f} Bs/USD'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        self.set_text_color(0, 0, 0)
        self.ln(6)

    def footer(self):
        self.set_y(-12)
        self.set_font('helvetica', 'I', 7)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, clean_pdf_str(f'ObraExacta  |  Página {self.page_no()}/{{nb}}  |  Presupuesto de Obra formal para cliente final'), align='C')


class PDFPresupuestoGenerator:
    """
    Generador de presupuestos oficiales de obra en formato PDF.
    Cero dependencias del sistema operativo (usa fpdf2).
    Genera en memoria (BytesIO) listo para despacho directo por Telegram o descarga web.
    """

    @classmethod
    def generar_presupuesto_pdf(
        cls,
        obra: Dict[str, Any],
        presupuesto: PresupuestoCompleto,
        codigo_presupuesto: Optional[str] = None
    ) -> io.BytesIO:
        pdf = ObraExactaPDF(orientation='P', unit='mm', format='A4')
        pdf.alias_nb_pages()
        tasa_bcv = float(presupuesto.tasa_bcv)
        pdf.tasa_bcv = tasa_bcv
        pdf.obra_nombre = obra.get("nombre", "Proyecto de Obra")
        
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(10, 15, 10)
        pdf.add_page()

        # 1. BLOQUE DE DATOS DE LA OBRA / CLIENTE
        cod_pres = codigo_presupuesto or f"OBX-PRE-{str(obra.get('id', '00000001'))[:8].upper()}"
        fecha_str = datetime.datetime.now().strftime("%d/%m/%Y")

        pdf.set_font('helvetica', 'B', 15)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, 'PRESUPUESTO ESTIMADO DE OBRA', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 5, 'Estructura de Costos y Partidas según Norma COVENIN Venezuela (Licitaciones y Contratos)', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        # Recuadro con datos del proyecto
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(10, pdf.get_y(), 190, 26, 'FD')
        
        y_box = pdf.get_y() + 2
        pdf.set_xy(13, y_box)
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(20, 5, 'OBRA:')
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(80, 5, clean_pdf_str(str(obra.get("nombre", "Proyecto Principal"))[:48]))

        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(32, 5, 'COD. PRESUPUESTO:')
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(234, 88, 12)
        pdf.cell(40, 5, clean_pdf_str(cod_pres), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(13, y_box + 6)
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(20, 5, 'CLIENTE:')
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(80, 5, clean_pdf_str(str(obra.get("cliente", "Cliente General"))[:48]))

        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(32, 5, 'FECHA EMISION:')
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(40, 5, fecha_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(13, y_box + 12)
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(20, 5, 'DIRECCION:')
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(80, 5, clean_pdf_str(str(obra.get("direccion") or "Caracas, Venezuela")[:48]))

        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(32, 5, 'TASA OFICIAL BCV:')
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(5, 150, 105)
        pdf.cell(40, 5, f"{tasa_bcv:,.2f} Bs/USD", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(10, y_box + 22)
        pdf.ln(5)

        # 2. TABLA PRINCIPAL DE PARTIDAS (7 COLUMNAS COVENIN)
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, '1. PARTIDAS DE OBRA Y COMPUTOS METRICOS (NORMA COVENIN)', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

        # Anchos en mm para A4 (190 mm utilizables):
        col_widths = (28, 58, 14, 16, 22, 24, 28)
        text_aligns = ('L', 'L', 'C', 'R', 'R', 'R', 'R')

        headings_style = FontFace(emphasis='B', color=(255, 255, 255), fill_color=(30, 41, 59))
        row_white = FontFace(color=(15, 23, 42), fill_color=(255, 255, 255))
        row_light = FontFace(color=(15, 23, 42), fill_color=(248, 250, 252))

        pdf.set_draw_color(226, 232, 240)
        with pdf.table(
            col_widths=col_widths, 
            text_align=text_aligns, 
            line_height=5,
            headings_style=headings_style,
            cell_fill_color=(255, 255, 255)
        ) as table:
            # Fila de cabecera
            header_row = table.row()
            titulos = ['Cod. COVENIN', 'Descripcion de Partida', 'Und', 'Cant.', 'P. Unit ($)', 'Total ($)', 'Total (Bs. BCV)']
            for t in titulos:
                header_row.cell(clean_pdf_str(t))

            for idx, p in enumerate(presupuesto.partidas):
                row_style = row_light if idx % 2 == 1 else row_white
                row = table.row(style=row_style)
                row.cell(clean_pdf_str(p.codigo_covenin or "E-GEN.000.001"))
                row.cell(clean_pdf_str(p.descripcion[:70]))
                row.cell(clean_pdf_str(p.unidad))
                cant_str = f"{p.area:.2f}" if p.unidad == "m2" and p.area > 0 else f"{p.cantidad:.2f}"
                row.cell(cant_str)
                row.cell(f"${p.p_unit_usd:,.2f}")
                row.cell(f"${p.total_usd:,.2f}")
                row.cell(f"{p.total_bs:,.2f}")

        pdf.ln(3)

        # 3. CUADRO RESUMEN: SUBTOTALES, CARGAS FISCALES Y TOTAL
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(203, 213, 225)
        box_y = pdf.get_y()
        # Verificar si cabe o salta de página
        if box_y > 215:
            pdf.add_page()
            box_y = pdf.get_y()

        pdf.rect(100, box_y, 100, 48, 'FD')

        pdf.set_xy(103, box_y + 2)
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(50, 5, 'Subtotal Materiales:')
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(42, 5, f"${presupuesto.total_materiales_usd:,.2f}", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(103, box_y + 7)
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(50, 5, 'Subtotal Mano de Obra:')
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(42, 5, f"${presupuesto.total_mano_obra_usd:,.2f}", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(103, box_y + 13)
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(50, 5, 'SUBTOTAL DIRECTO:')
        pdf.cell(42, 5, f"${presupuesto.subtotal_usd:,.2f}", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Cargas
        pdf.set_xy(103, box_y + 19)
        pdf.set_font('helvetica', '', 7.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(50, 4.5, '+ Ley Protección Pensiones (9% s/MO):')
        pension_usd = round(presupuesto.total_mano_obra_usd * 0.09, 2)
        pdf.cell(42, 4.5, f"${pension_usd:,.2f}", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(103, box_y + 24)
        pdf.cell(50, 4.5, '+ Gastos Admin. e Imprevistos (10%):')
        admin_usd = round(presupuesto.subtotal_usd * 0.10, 2)
        pdf.cell(42, 4.5, f"${admin_usd:,.2f}", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Gran Total Banner
        pdf.set_fill_color(15, 23, 42)
        pdf.rect(100, box_y + 31, 100, 17, 'F')

        pdf.set_xy(103, box_y + 32)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(249, 115, 22)  # Orange
        pdf.cell(45, 5, 'TOTAL PRESUPUESTO:')
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(47, 5, f"${presupuesto.total_general_usd:,.2f} USD", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(103, box_y + 38)
        pdf.set_font('helvetica', 'B', 8.5)
        pdf.set_text_color(52, 211, 153)  # Emerald 400
        pdf.cell(45, 5, 'EQUIVALENTE BCV:')
        pdf.cell(47, 5, f"Bs. {presupuesto.total_general_bs:,.2f}", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(10, box_y + 52)
        pdf.ln(4)

        # 4. ANEXO: LISTA ESTIMADA DE MATERIALES (HOJA DE COMPRAS)
        if pdf.get_y() > 220:
            pdf.add_page()

        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, '2. ANEXO: LISTA ESTIMADA DE COMPRA DE MATERIALES', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

        mat_widths = (65, 20, 25, 25, 25, 30)
        mat_aligns = ('L', 'C', 'R', 'R', 'R', 'R')

        mat_headings_style = FontFace(emphasis='B', color=(255, 255, 255), fill_color=(51, 65, 85))
        pdf.set_draw_color(226, 232, 240)

        with pdf.table(
            col_widths=mat_widths, 
            text_align=mat_aligns, 
            line_height=5,
            headings_style=mat_headings_style,
            cell_fill_color=(255, 255, 255)
        ) as table:
            m_header = table.row()
            for h in ['Material Estimado', 'Unidad', 'Cant. Requerida', 'P. Unit ($)', 'Total ($)', 'Total (Bs. BCV)']:
                m_header.cell(clean_pdf_str(h))

            for idx, m in enumerate(presupuesto.hoja_compras):
                m_style = row_light if idx % 2 == 1 else row_white
                m_row = table.row(style=m_style)
                m_row.cell(clean_pdf_str(m.material[:40]))
                m_row.cell(clean_pdf_str(m.unidad))
                m_row.cell(f"{m.cantidad_requerida:g}")
                m_row.cell(f"${m.p_unit_estimado_usd:,.2f}")
                m_row.cell(f"${m.total_estimado_usd:,.2f}")
                total_bs = round(m.total_estimado_usd * tasa_bcv, 2)
                m_row.cell(f"{total_bs:,.2f}")

        # Retornar BytesIO listo
        buf = io.BytesIO()
        pdf.output(buf)
        buf.seek(0)
        return buf
