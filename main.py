import flet as ft
import sqlite3
from datetime import datetime
import urllib.parse

# === CONFIGURACIÓN DE BASE DE DATOS CON SUPER PARCHE ===
def init_db():
    conn = sqlite3.connect("inversiones_gl.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prestamos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            cedula TEXT,
            telefono TEXT,
            capital REAL,
            total_usd REAL,
            fecha TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS finanzas (
            id INTEGER PRIMARY KEY,
            capital_disponible REAL,
            capital_inicial REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_ganancias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monto_ganado REAL,
            fecha TEXT
        )
    """)
    
    columnas_finanzas = [col[1] for col in cursor.execute("PRAGMA table_info(finanzas)")]
    if "capital_inicial" not in columnas_finanzas:
        try:
            cursor.execute("ALTER TABLE finanzas ADD COLUMN capital_inicial REAL")
            conn.commit()
        except: pass

    cursor.execute("SELECT COUNT(*) FROM finanzas")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO finanzas (id, capital_disponible, capital_inicial) VALUES (1, 500.0, 500.0)")
    else:
        cursor.execute("UPDATE finanzas SET capital_inicial = 500.0 WHERE capital_inicial IS NULL")
    conn.commit(); conn.close()

def main(page: ft.Page):
    page.theme_mode = ft.ThemeMode.DARK
    page.title = "Inversiones G.L."
    page.scroll = "adaptive"
    page.padding = ft.padding.only(top=60, left=15, right=15, bottom=60)
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    init_db()
    PIN_CORRECTO = "2026"

    # --- CAMPOS GLOBALES ---
    txt_nombre = ft.TextField(label="Nombre del Cliente", border_radius=10)
    txt_cedula = ft.TextField(label="Cédula", border_radius=10, keyboard_type="number")
    txt_telefono = ft.TextField(label="Teléfono", border_radius=10, keyboard_type="phone")
    txt_monto = ft.TextField(label="Monto Prestado ($)", border_radius=10, keyboard_type="number")
    txt_interes = ft.TextField(label="Interés (%)", value="30", border_radius=10, keyboard_type="number")
    txt_tasa = ft.TextField(label="Tasa BCV (Bs)", value="48.50", border_radius=10, keyboard_type="number")
    txt_nuevo_capital = ft.TextField(label="Capital Base ($)", border_radius=10, keyboard_type="number", width=250)
    
    lbl_total_usd = ft.Text("$ 0.00", size=28, weight="bold")
    lbl_total_bs = ft.Text("0.00 Bs.", size=18)
    col_lista = ft.Column(spacing=10, horizontal_alignment="center")

    def cambiar_tema(e):
        page.theme_mode = ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        btn_tema.text = "MODO OSCURO" if page.theme_mode == ft.ThemeMode.LIGHT else "MODO CLARO"
        page.update()

    btn_tema = ft.TextButton("MODO CLARO", on_click=cambiar_tema)

    def obtener_finanzas():
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT capital_disponible, capital_inicial FROM finanzas WHERE id = 1")
        res = cursor.fetchone()
        conn.close()
        return float(res[0]), float(res[1])

    # CORRECCIÓN: Uso de page.launch_url para compatibilidad móvil
    def enviar_whatsapp(nombre, telefono, monto, tipo, int_aplicado="30"):
        num = "".join(filter(str.isdigit, str(telefono)))
        if not num.startswith("58"): num = "58" + num.lstrip("0")
        tasa_bcv = float(txt_tasa.value or 48.50)
        
        if tipo == "comprobante":
            mensaje = (
                "💰 *INVERSIONES G.L.*\n\n"
                f"👤 *Cliente:* {nombre}\n"
                f"💵 *Préstamo:* ${monto:.2f}\n"
                f"📈 *Interés:* {int_aplicado}%\n"
                "📝 *Nota:* Pagos a tasa BCV."
            )
        else:
            mensaje = (
                "🔔 *RECORDATORIO DE PAGO*\n"
                "━━━━━━━━━━━━━━━\n"
                f"👤 *Cliente:* {nombre}\n"
                f"💰 *Monto a pagar:* ${monto:.2f}\n"
                f"📊 *Tasa BCV:* {tasa_bcv:.2f} Bs.\n\n"
                "📌 *DATOS PAGO MÓVIL*\n"
                "🏦 Banco Mercantil (0105)\n"
                "📱 0412-0495246\n"
                "🆔 CI: 28.589.939"
            )
        # page.launch_url es mucho más estable en Android/iOS que webbrowser
        url = f"https://wa.me/{num}?text={urllib.parse.quote(mensaje)}"
        page.launch_url(url)

    def registrar_pago(e):
        if txt_nombre.value and txt_monto.value:
            m_p = float(txt_monto.value)
            int_val = float(txt_interes.value or 30)
            m_f = m_p * (1 + (int_val / 100))
            
            hoy = datetime.now().strftime("%d/%m/%Y")
            cap_disp, _ = obtener_finanzas()
            conn = sqlite3.connect("inversiones_gl.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE finanzas SET capital_disponible = ?", (cap_disp - m_p,))
            cursor.execute("INSERT INTO prestamos (cliente, cedula, telefono, capital, total_usd, fecha) VALUES (?,?,?,?,?,?)",
                           (txt_nombre.value, txt_cedula.value, txt_telefono.value, m_p, m_f, hoy))
            conn.commit(); conn.close()
            
            # Enviar WhatsApp antes de cambiar de pantalla
            enviar_whatsapp(txt_nombre.value, txt_telefono.value, m_f, "comprobante", int_aplicado=str(int_val))
            ir_menu_principal()

    def ir_menu_principal(e=None):
        page.controls.clear()
        cap_disp, cap_init = obtener_finanzas()
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(capital) FROM prestamos")
        res = cursor.fetchone()
        inv_calle = float(res[0]) if res[0] else 0.0
        conn.close()
        ganancia_neta = (cap_disp + inv_calle) - cap_init

        page.add(
            ft.Column([
                ft.Row([btn_tema, ft.TextButton("SALIR", on_click=lambda _: cargar_login(), style=ft.ButtonStyle(color="red"))], alignment="spaceBetween"),
                ft.Text("INVERSIONES G.L.", size=28, weight="bold", color="blue400"),
                ft.Container(
                    content=ft.Column([
                        ft.Text("EN BÓVEDA", size=11, color="white"),
                        ft.Text(f"$ {cap_disp:.2f}", size=32, weight="bold", color="white"),
                        ft.Text(f"Capital Inicial: $ {cap_init:.2f}", size=11, color="blue200"),
                    ], horizontal_alignment="center"),
                    bgcolor="blue700", padding=15, border_radius=20, width=page.width
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("GANANCIA DISPONIBLE", size=11),
                        ft.Text(f"$ {ganancia_neta:.2f}", size=24, color="green" if ganancia_neta >= 0 else "red", weight="bold"),
                        ft.TextButton("HISTORIAL DE CIERRES", on_click=mostrar_historial),
                    ], horizontal_alignment="center"),
                    bgcolor="surfacevariant", padding=15, border_radius=15, width=page.width
                ),
                ft.ElevatedButton("NUEVO PRÉSTAMO", on_click=mostrar_registro, width=page.width, height=50),
                ft.ElevatedButton("COBRANZAS", on_click=mostrar_cobros, width=page.width, height=50),
                ft.TextButton("AJUSTES Y CIERRE", on_click=mostrar_config, style=ft.ButtonStyle(color="grey")),
            ], horizontal_alignment="center", spacing=15)
        )
        page.update()

    def mostrar_historial(e):
        page.controls.clear()
        col_hist = ft.Column(spacing=10)
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT monto_ganado, fecha FROM historial_ganancias ORDER BY id DESC")
        for r in cursor.fetchall():
            col_hist.controls.append(ft.Container(content=ft.Row([ft.Text(r[1]), ft.Text(f"+$ {r[0]:.2f}", weight="bold", color="green")], alignment="space_between"), bgcolor="surfacevariant", padding=12, border_radius=10))
        conn.close()
        page.add(ft.Column([ft.TextButton("VOLVER", on_click=ir_menu_principal), ft.Text("HISTORIAL", size=20, weight="bold"), col_hist], horizontal_alignment="center"))
        page.update()

    def mostrar_config(e):
        page.controls.clear()
        cap_disp, cap_init = obtener_finanzas()
        txt_nuevo_capital.value = str(cap_init)
        page.add(ft.Column([ft.TextButton("VOLVER", on_click=ir_menu_principal), ft.Text("CONFIGURACIÓN", size=22, weight="bold"), txt_nuevo_capital, ft.ElevatedButton("ACTUALIZAR BASE", on_click=actualizar_base), ft.Divider(height=30), ft.ElevatedButton("CERRAR MES Y REINICIAR", on_click=lambda _: reset_confirmar(0), bgcolor="green", color="white")], horizontal_alignment="center"))
        page.update()

    def actualizar_base(e):
        val = float(txt_nuevo_capital.value or 0)
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE finanzas SET capital_inicial = ?, capital_disponible = ?", (val, val))
        conn.commit(); conn.close(); ir_menu_principal()

    def reset_confirmar(g):
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM prestamos")
        cursor.execute("UPDATE finanzas SET capital_disponible = capital_inicial")
        conn.commit(); conn.close(); ir_menu_principal()

    def mostrar_registro(e):
        page.controls.clear()
        page.add(ft.Column([ft.TextButton("VOLVER", on_click=ir_menu_principal), ft.Text("REGISTRO", size=22, weight="bold"), txt_nombre, txt_cedula, txt_telefono, txt_monto, txt_interes, txt_tasa, ft.ElevatedButton("GUARDAR", on_click=registrar_pago, width=page.width, height=50, bgcolor="blue700")], horizontal_alignment="center"))
        page.update()

    def mostrar_cobros(e):
        page.controls.clear()
        page.add(ft.Column([ft.TextButton("VOLVER", on_click=ir_menu_principal), ft.Container(content=ft.Column([lbl_total_usd, lbl_total_bs], horizontal_alignment="center"), bgcolor="surfacevariant", padding=15, border_radius=15, width=page.width), txt_tasa, col_lista], horizontal_alignment="center"))
        actualizar_lista(); calcular_totales()

    def actualizar_lista():
        col_lista.controls.clear()
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, cliente, total_usd, telefono FROM prestamos ORDER BY id DESC")
        for r in cursor.fetchall():
            col_lista.controls.append(ft.Container(content=ft.Column([ft.Text(r[1], weight="bold"), ft.Row([ft.Text(f"${r[2]:.2f}", expand=True, color="blue400"), ft.TextButton("COBRAR", on_click=lambda e, n=r[1], t=r[3], m=r[2]: enviar_whatsapp(n, t, m, "cobro")), ft.TextButton("BORRAR", on_click=lambda e, i=r[0]: borrar_pago(i), style=ft.ButtonStyle(color="red"))])]), bgcolor="surfacevariant", padding=12, border_radius=10))
        conn.close(); page.update()

    def borrar_pago(idx):
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM prestamos WHERE id = ?", (idx,))
        conn.commit(); conn.close(); actualizar_lista(); calcular_totales()

    def calcular_totales():
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_usd) FROM prestamos")
        res = cursor.fetchone()[0]
        total = float(res) if res else 0.0
        conn.close(); t = float(txt_tasa.value or 48.50)
        lbl_total_usd.value = f"$ {total:.2f}"; lbl_total_bs.value = f"{total * t:,.2f} Bs."; page.update()

    def validar_pin(e):
        if txt_pin.value == PIN_CORRECTO: ir_menu_principal()
        else: txt_pin.error_text = "ERROR"; page.update()

    txt_pin = ft.TextField(label="PIN", password=True, text_align="center", keyboard_type="number", width=220)
    
    def cargar_login():
        page.controls.clear()
        page.add(
            ft.Column([
                ft.Container(height=80),
                ft.Text("G.L.", size=70, weight="bold", color="blue400"),
                ft.Text("SISTEMA DE GESTIÓN", size=18, weight="bold"),
                ft.Text("Bienvenido, Administrador", size=14, color="grey"),
                ft.Container(height=20),
                txt_pin, 
                ft.ElevatedButton("ENTRAR AL SISTEMA", on_click=validar_pin, width=220, height=50)
            ], horizontal_alignment="center")
        )
        page.update()

    cargar_login()

ft.app(target=main)
