import flet as ft
import sqlite3
from datetime import datetime, timedelta
import urllib.parse
import asyncio

# === CONFIGURACIÓN DE BASE DE DATOS ===
def init_db():
    conn = sqlite3.connect("inversiones_gl.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prestamos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT, cedula TEXT, telefono TEXT,
            capital REAL, total_usd REAL, fecha TEXT, vencimiento TEXT
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS finanzas (id INTEGER PRIMARY KEY, capital_disponible REAL, capital_inicial REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS historial_ganancias (id INTEGER PRIMARY KEY AUTOINCREMENT, monto_ganado REAL, fecha TEXT)")
    
    columnas = [col[1] for col in cursor.execute("PRAGMA table_info(prestamos)")]
    if "vencimiento" not in columnas:
        cursor.execute("ALTER TABLE prestamos ADD COLUMN vencimiento TEXT")

    cursor.execute("SELECT COUNT(*) FROM finanzas")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO finanzas (id, capital_disponible, capital_inicial) VALUES (1, 500.0, 500.0)")
    conn.commit()
    conn.close()

async def main(page: ft.Page):
    page.theme_mode = ft.ThemeMode.DARK
    page.title = "Inversiones G.L."
    page.window_prevent_close = True
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.padding = ft.Padding(left=20, top=50, right=20, bottom=40)
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    init_db()
    PIN_CORRECTO = "2026"

    # --- CAMPOS GLOBALES ---
    txt_nombre = ft.TextField(label="Nombre del Cliente", border_radius=12)
    txt_cedula = ft.TextField(label="Cédula", border_radius=12, keyboard_type=ft.KeyboardType.NUMBER)
    txt_telefono = ft.TextField(label="Teléfono", border_radius=12, keyboard_type=ft.KeyboardType.PHONE)
    txt_monto = ft.TextField(label="Monto Prestado ($)", border_radius=12, keyboard_type=ft.KeyboardType.NUMBER)
    txt_interes = ft.TextField(label="Interés (%)", value="30", border_radius=12)
    txt_tasa = ft.TextField(label="Tasa BCV (Bs)", value="48.50", border_radius=12, text_align=ft.TextAlign.CENTER)
    txt_nuevo_capital = ft.TextField(label="Capital Base ($)", border_radius=12, width=250)
    
    lbl_total_usd = ft.Text("$ 0.00", size=30, weight="bold")
    lbl_total_bs = ft.Text("0.00 Bs.", size=18, color="grey")
    col_lista = ft.Column(spacing=12, horizontal_alignment="center")

    def obtener_finanzas():
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT capital_disponible, capital_inicial FROM finanzas WHERE id = 1")
        res = cursor.fetchone()
        conn.close()
        return float(res[0]), float(res[1])

    async def enviar_whatsapp(nombre, cedula, telefono, monto, tipo, vence=""):
        num = "".join(filter(str.isdigit, str(telefono)))
        if not num.startswith("58"): num = "58" + num.lstrip("0")
        
        datos_pago = (
            "━━━━━━━━━━━━━━━\n"
            "*DATOS DEL PAGO*\n"
            "Pago Móvil\n"
            "Inversiones G L\n"
            "Mercantil 0105\n"
            "0412-049-5246\n"
            "C.I: 28.589.939"
        )

        if tipo == "comprobante":
            mensaje = (
                "[*] *INVERSIONES G.L. VIP*\n\n"
                "Saludos, Muy Buenas Tardes. La gerencia de nuestro fondo de inversión le saluda "
                "y le informa que el día de hoy usted entra con un *PRÉSTAMO ACTIVO* "
                "bajo la siguiente modalidad:\n\n"
                f"[-] *Cliente:* {nombre}\n"
                f"[-] *Cédula:* {cedula}\n"
                f"[-] *Monto:* ${monto:.2f}\n"
                f"[-] *Vencimiento:* {vence}\n"
                "━━━━━━━━━━━━━━━\n"
                "[!] *NOTA:* En caso de no pagar puntual el préstamo total, "
                "el interés se sumará al capital."
            )
        else:
            mensaje = (
                "[*] *INVERSIONES G.L. VIP*\n\n"
                f"[-] *Cliente:* {nombre}\n"
                f"[-] *Préstamo activo:* ${monto:.2f}\n"
                f"[-] *Vencimiento:* {vence}\n"
                "━━━━━━━━━━━━━━━\n"
                "[V] *Pagos a tasa BCV del día.*\n"
                "━━━━━━━━━━━━━━━\n"
                f"{datos_pago}"
            )
        
        texto_final = urllib.parse.quote(mensaje)
        url_whatsapp = f"https://api.whatsapp.com/send?phone={num}&text={texto_final}"
        await page.launch_url(url_whatsapp)

    async def registrar_pago(e):
        if txt_nombre.value and txt_monto.value:
            try:
                m_p = float(txt_monto.value)
                m_f = m_p * (1 + (float(txt_interes.value or 30) / 100))
                v_str = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
                cap_d, _ = obtener_finanzas()
                
                conn = sqlite3.connect("inversiones_gl.db"); cursor = conn.cursor()
                cursor.execute("UPDATE finanzas SET capital_disponible = ?", (cap_d - m_p,))
                cursor.execute("INSERT INTO prestamos (cliente, cedula, telefono, capital, total_usd, fecha, vencimiento) VALUES (?,?,?,?,?,?,?)",
                               (txt_nombre.value, txt_cedula.value, txt_telefono.value, m_p, m_f, datetime.now().strftime("%d/%m/%Y"), v_str))
                conn.commit(); conn.close()
                
                n, c, t = txt_nombre.value, txt_cedula.value, txt_telefono.value
                txt_nombre.value = ""; txt_cedula.value = ""; txt_telefono.value = ""; txt_monto.value = ""
                
                await enviar_whatsapp(n, c, t, m_f, "comprobante", vence=v_str)
                await ir_menu_principal()
            except: pass

    async def liquidar_final(idx, cap_p, monto_t):
        ganancia = monto_t - cap_p
        cap_disp, _ = obtener_finanzas()
        conn = sqlite3.connect("inversiones_gl.db"); cursor = conn.cursor()
        cursor.execute("INSERT INTO historial_ganancias (monto_ganado, fecha) VALUES (?,?)", (ganancia, datetime.now().strftime("%d/%m/%Y")))
        cursor.execute("UPDATE finanzas SET capital_disponible = ?", (cap_disp + monto_t,))
        cursor.execute("DELETE FROM prestamos WHERE id = ?", (idx,))
        conn.commit(); conn.close()
        await mostrar_cobros(None)

    async def eliminar_prestamo(idx, cap_p):
        cap_disp, _ = obtener_finanzas()
        conn = sqlite3.connect("inversiones_gl.db"); cursor = conn.cursor()
        cursor.execute("UPDATE finanzas SET capital_disponible = ?", (cap_disp + cap_p,))
        cursor.execute("DELETE FROM prestamos WHERE id = ?", (idx,))
        conn.commit(); conn.close()
        await mostrar_cobros(None)

    async def ir_menu_principal(e=None):
        page.controls.clear()
        cap_disp, _ = obtener_finanzas()
        conn = sqlite3.connect("inversiones_gl.db"); cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_usd), COUNT(id) FROM prestamos")
        res_calle = cursor.fetchone()
        en_calle = float(res_calle[0] or 0.0)
        num_clientes = int(res_calle[1] or 0)
        cursor.execute("SELECT SUM(monto_ganado) FROM historial_ganancias")
        ganancia_total = float(cursor.fetchone()[0] or 0.0)
        conn.close()

        async def cambiar_tema(e):
            page.theme_mode = ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
            btn_tema.text = "TEMA OSCURO" if page.theme_mode == ft.ThemeMode.LIGHT else "TEMA CLARO"
            page.update()

        btn_tema = ft.TextButton("TEMA CLARO", on_click=cambiar_tema)

        page.add(
            ft.Column([
                ft.Row([btn_tema, ft.TextButton("SALIR", on_click=lambda _: asyncio.create_task(cargar_login()), style=ft.ButtonStyle(color="red"))], alignment="spaceBetween"),
                ft.Text("INVERSIONES G.L.", size=28, weight="bold", color="blue400"),
                ft.Container(content=ft.Column([ft.Text("EN BÓVEDA", size=12, weight="w500"), ft.Text(f"$ {cap_disp:.2f}", size=36, weight="bold")], horizontal_alignment="center"), bgcolor="blue700", padding=20, border_radius=25, width=page.width),
                ft.Container(content=ft.Column([ft.Text("GANANCIAS REALES", size=11, weight="w500"), ft.Text(f"$ {ganancia_total:.2f}", size=26, color="green300", weight="bold"), ft.TextButton("VER HISTORIAL", on_click=lambda e: asyncio.create_task(mostrar_historial(e)))], horizontal_alignment="center", spacing=5), bgcolor="white10", padding=15, border_radius=20, width=page.width),
                ft.Row([
                    ft.Container(content=ft.Column([ft.Text("CLIENTES", size=10), ft.Text(f"{num_clientes}", size=20, weight="bold")], horizontal_alignment="center"), bgcolor="white5", padding=15, border_radius=20, expand=True),
                    ft.Container(content=ft.Column([ft.Text("EN CALLE", size=10), ft.Text(f"$ {en_calle:.2f}", size=20, color="orange400", weight="bold")], horizontal_alignment="center"), bgcolor="white5", padding=15, border_radius=20, expand=True),
                ], spacing=10),
                ft.Divider(height=10, color="transparent"),
                ft.Row([
                    ft.ElevatedButton("NUEVO", on_click=lambda e: asyncio.create_task(mostrar_registro(e)), expand=True, height=75, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15))),
                    ft.ElevatedButton("COBRAR", on_click=lambda e: asyncio.create_task(mostrar_cobros(e)), expand=True, height=75, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15))),
                ], spacing=10),
                ft.TextButton("AJUSTES DEL SISTEMA", on_click=lambda e: asyncio.create_task(mostrar_config(e)), style=ft.ButtonStyle(color="grey")),
            ], horizontal_alignment="center", spacing=15)
        )
        page.update()

    async def mostrar_cobros(e):
        page.controls.clear()
        col_lista.controls.clear()
        conn = sqlite3.connect("inversiones_gl.db"); cursor = conn.cursor()
        cursor.execute("SELECT id, cliente, cedula, telefono, vencimiento, total_usd, capital FROM prestamos ORDER BY id DESC")
        rows = cursor.fetchall()
        for r in rows:
            col_lista.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{r[1]}", weight="bold", size=16),
                        ft.Text(f"Vence: {r[4]}", size=12, color="grey"),
                        ft.Row([
                            ft.Text(f"${r[5]:.2f}", expand=True, color="blue400", size=18, weight="bold"),
                            ft.TextButton("WS", on_click=lambda e, n=r[1], c=r[2], t=r[3], m=r[5], v=r[4]: asyncio.create_task(enviar_whatsapp(n, c, t, m, "cobro", v))),
                            ft.TextButton("PAGÓ", on_click=lambda e, i=r[0], cap=r[6], tot=r[5]: asyncio.create_task(liquidar_final(i, cap, tot)), style=ft.ButtonStyle(color="green")),
                            ft.TextButton("X", on_click=lambda e, i=r[0], cap=r[6]: asyncio.create_task(eliminar_prestamo(i, cap)), style=ft.ButtonStyle(color="red")),
                        ])
                    ]), bgcolor="white5", padding=15, border_radius=15
                )
            )
        total_c = sum(float(r[5]) for r in rows)
        lbl_total_usd.value = f"TOTAL: $ {total_c:.2f}"
        lbl_total_bs.value = f"{(total_c * float(txt_tasa.value)):,.2f} Bs."
        
        page.add(ft.Column([
            ft.Row([ft.TextButton("VOLVER", on_click=lambda e: asyncio.create_task(ir_menu_principal(e)))], alignment="start"),
            ft.Container(content=ft.Column([lbl_total_usd, lbl_total_bs], horizontal_alignment="center"), bgcolor="white10", padding=20, border_radius=20),
            ft.Text("Tasa BCV del día:", size=12),
            txt_tasa,
            col_lista
        ], horizontal_alignment="center", spacing=15))
        conn.close(); page.update()

    async def mostrar_historial(e):
        page.controls.clear()
        col_h = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, height=500)
        conn = sqlite3.connect("inversiones_gl.db"); cursor = conn.cursor()
        cursor.execute("SELECT monto_ganado, fecha FROM historial_ganancias ORDER BY id DESC")
        for r in cursor.fetchall():
            col_h.controls.append(ft.Container(content=ft.Row([ft.Text(r[1]), ft.Text(f"+$ {r[0]:.2f}", weight="bold", color="green300")], alignment="spaceBetween"), bgcolor="white5", padding=15, border_radius=12))
        conn.close()
        page.add(ft.Column([
            ft.Row([ft.TextButton("VOLVER", on_click=lambda e: asyncio.create_task(ir_menu_principal(e)))], alignment="start"),
            ft.Text("HISTORIAL", size=22, weight="bold"),
            col_h
        ], horizontal_alignment="center"))
        page.update()

    async def mostrar_config(e):
        page.controls.clear()
        _, cap_i = obtener_finanzas()
        txt_nuevo_capital.value = str(cap_i)
        page.add(ft.Column([
            ft.Row([ft.TextButton("VOLVER", on_click=lambda e: asyncio.create_task(ir_menu_principal(e)))], alignment="start"),
            ft.Text("AJUSTES", size=22, weight="bold"),
            txt_nuevo_capital,
            ft.ElevatedButton("ACTUALIZAR CAPITAL", on_click=lambda e: asyncio.create_task(actualizar_base(e)), width=250),
            ft.Divider(height=30),
            ft.ElevatedButton("BORRAR TODO", on_click=lambda e: asyncio.create_task(reset_sistema(e)), bgcolor="red", color="white", width=250)
        ], horizontal_alignment="center"))
        page.update()

    async def actualizar_base(e):
        try:
            v = float(txt_nuevo_capital.value or 0)
            conn = sqlite3.connect("inversiones_gl.db"); cursor = conn.cursor()
            cursor.execute("UPDATE finanzas SET capital_inicial = ?, capital_disponible = ?", (v, v))
            conn.commit(); conn.close(); await ir_menu_principal()
        except: pass

    async def reset_sistema(e):
        conn = sqlite3.connect("inversiones_gl.db"); cursor = conn.cursor()
        cursor.execute("DELETE FROM prestamos"); cursor.execute("DELETE FROM historial_ganancias")
        cursor.execute("UPDATE finanzas SET capital_disponible = capital_inicial")
        conn.commit(); conn.close(); await ir_menu_principal()

    async def mostrar_registro(e):
        page.controls.clear()
        page.add(ft.Column([
            ft.Row([ft.TextButton("VOLVER", on_click=lambda e: asyncio.create_task(ir_menu_principal(e)))], alignment="start"),
            ft.Text("NUEVO PRÉSTAMO", size=22, weight="bold"),
            txt_nombre, txt_cedula, txt_telefono, txt_monto, txt_interes, txt_tasa,
            ft.ElevatedButton("GUARDAR Y ENVIAR WS", on_click=lambda e: asyncio.create_task(registrar_pago(e)), width=page.width, height=60, bgcolor="blue700")
        ], horizontal_alignment="center", spacing=15))
        page.update()

    async def cargar_login():
        page.controls.clear()
        txt_pin = ft.TextField(label="PIN DE ACCESO", password=True, text_align="center", keyboard_type=ft.KeyboardType.NUMBER, width=250, border_radius=15)
        page.add(
            ft.Column([
                ft.Container(height=80),
                ft.Text("G.L.", size=80, weight="bold", color="blue400"),
                ft.Text("SISTEMA DE GESTIÓN", size=18, weight="bold"),
                ft.Container(height=40),
                txt_pin,
                ft.ElevatedButton("ENTRAR", on_click=lambda e: asyncio.create_task(ir_menu_principal(e)) if txt_pin.value == PIN_CORRECTO else None, width=250, height=60)
            ], horizontal_alignment="center")
        )
        page.update()

    await cargar_login()

if __name__ == "__main__":
    ft.app(target=main)
    
