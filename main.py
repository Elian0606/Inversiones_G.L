import flet as ft
import sqlite3
from datetime import datetime, timedelta
import urllib.parse

# === CONFIGURACIÓN DE BASE DE DATOS ===
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
    conn.commit()
    conn.close()

def main(page: ft.Page):
    page.title = "Inversiones G.L."
    page.theme_mode = "light"
    page.scroll = "adaptive"
    page.padding = 20
    init_db()

    PIN_CORRECTO = "2026"

    # --- CAMPOS DE FORMULARIO ---
    txt_nombre = ft.TextField(label="Nombre del Cliente", border_radius=10)
    txt_cedula = ft.TextField(label="Cédula de Identidad", border_radius=10, keyboard_type="number")
    txt_telefono = ft.TextField(label="Teléfono (ej: 04121234567)", border_radius=10, keyboard_type="phone")
    txt_monto = ft.TextField(label="Monto Prestado ($)", border_radius=10, keyboard_type="number")
    txt_tasa = ft.TextField(label="Tasa BCV (Bs)", value="48.50", border_radius=10, keyboard_type="number")
    
    lbl_total_usd = ft.Text("$ 0.00", size=30, weight="bold", color="green")
    lbl_total_bs = ft.Text("0.00 Bs.", size=20, color="blue")
    col_lista = ft.Column(spacing=10, horizontal_alignment="center")

    # --- LÓGICA DE NAVEGACIÓN ---
    def cerrar_sesion(e):
        page.controls.clear()
        page.add(login_screen)
        txt_pin.value = ""
        page.update()

    def ir_menu_principal(e):
        page.controls.clear()
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(total_usd) FROM prestamos")
        res = cursor.fetchone()
        conteo = res[0] if res[0] else 0
        total_calle = float(res[1]) if res[1] else 0.0
        conn.close()

        page.add(
            ft.Column([
                ft.Row([ft.TextButton("CERRAR SESIÓN", on_click=cerrar_sesion, style=ft.ButtonStyle(color="red"))], alignment="end"),
                ft.Text("INVERSIONES G.L.", size=28, weight="bold", color="blue"),
                ft.Text("Gestión de Cartera - Elian Garcia", size=16, color="grey"),
                ft.Divider(height=20, color="transparent"),
                
                ft.Container(
                    content=ft.Column([
                        ft.Text("RESUMEN DE CARTERA", weight="bold", size=14, color="blue"),
                        ft.Row([
                            ft.Column([ft.Text("Clientes", size=12), ft.Text(f"{conteo}", size=20, weight="bold")], horizontal_alignment="center"),
                            ft.VerticalDivider(),
                            ft.Column([ft.Text("Total en Calle", size=12), ft.Text(f"${total_calle:.2f}", size=20, weight="bold", color="green")], horizontal_alignment="center"),
                        ], alignment="center", spacing=30)
                    ], horizontal_alignment="center"),
                    bgcolor="#f0f4f8", padding=15, border_radius=15, border=ft.border.all(1, "#d1d9e0")
                ),
                
                ft.Divider(height=20, color="transparent"),
                ft.ElevatedButton("REGISTRAR NUEVO", on_click=mostrar_registro, width=300, height=55),
                ft.Container(height=10),
                ft.ElevatedButton("VER COBRANZAS", on_click=mostrar_cobros, width=300, height=55),
                container_principal
            ], horizontal_alignment="center")
        )
        container_principal.controls.clear()
        page.update()

    # --- LÓGICA DE WHATSAPP ---
    def abrir_whatsapp(nombre, numero, monto):
        mensaje = f"Hola {nombre}, te recuerda Elian Garcia (Inversiones G.L.) el pago mensual de ${monto:.2f}."
        texto_url = urllib.parse.quote(mensaje)
        num_limpio = "".join(filter(str.isdigit, str(numero)))
        if not num_limpio.startswith("58"):
            if num_limpio.startswith("0"):
                num_limpio = "58" + num_limpio[1:]
            else:
                num_limpio = "58" + num_limpio
        
        url_final = f"https://api.whatsapp.com/send?phone={num_limpio}&text={texto_url}"
        page.launch_url(url_final)
        
        page.snack_bar = ft.SnackBar(ft.Text("Abriendo chat de WhatsApp..."))
        page.snack_bar.open = True
        page.update()

    # --- SEMÁFORO ---
    def calcular_semaforo(fecha_str):
        try:
            fecha_reg = datetime.strptime(fecha_str, "%d/%m/%Y")
            vencimiento = fecha_reg + timedelta(days=30)
            dias_restantes = (vencimiento - datetime.now()).days
            if dias_restantes < 0: return "#F8D7DA"
            if dias_restantes <= 5: return "#FFF3CD"
            return "#D4EDDA"
        except: return "#f0f2f5"

    def actualizar_lista():
        col_lista.controls.clear()
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, cliente, total_usd, cedula, telefono, fecha FROM prestamos ORDER BY id DESC")
        rows = cursor.fetchall()
        tasa = float(txt_tasa.value or 1.0)
        for r in rows:
            color_bg = calcular_semaforo(r[5])
            col_lista.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(r[1], weight="bold", size=18),
                        ft.Text(f"C.I: {r[3]} | Tel: {r[4]}", size=13),
                        ft.Text(f"Vence: {r[5]}", size=11, color="black54"),
                        ft.Row([
                            ft.Text(f"${r[2]:.2f} | {r[2]*tasa:,.2f} Bs.", color="blue", weight="bold", expand=True),
                            ft.TextButton("COBRAR", on_click=lambda e, n=r[1], t=r[4], m=r[2]: abrir_whatsapp(n, t, m), style=ft.ButtonStyle(color="green")),
                            ft.TextButton("BORRAR", on_click=lambda e, i=r[0]: borrar_pago(i), style=ft.ButtonStyle(color="red")),
                        ])
                    ]),
                    bgcolor=color_bg, padding=15, border_radius=12
                )
            )
        conn.close()
        page.update()

    def registrar_pago(e):
        if txt_nombre.value and txt_monto.value:
            monto_final = float(txt_monto.value) * 1.30
            hoy = datetime.now().strftime("%d/%m/%Y")
            conn = sqlite3.connect("inversiones_gl.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO prestamos (cliente, cedula, telefono, capital, total_usd, fecha) VALUES (?,?,?,?,?,?)",
                           (txt_nombre.value, txt_cedula.value, txt_telefono.value, float(txt_monto.value), monto_final, hoy))
            conn.commit()
            conn.close()
            txt_nombre.value = ""; txt_cedula.value = ""; txt_telefono.value = ""; txt_monto.value = ""
            mostrar_cobros(None)

    def borrar_pago(idx):
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM prestamos WHERE id = ?", (idx,))
        conn.commit()
        conn.close()
        actualizar_lista()
        calcular_totales()

    def calcular_totales():
        conn = sqlite3.connect("inversiones_gl.db")
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_usd) FROM prestamos")
        res = cursor.fetchone()[0]
        total = float(res) if res else 0.0
        conn.close()
        tasa = float(txt_tasa.value or 1.0)
        lbl_total_usd.value = f"$ {total:.2f}"
        lbl_total_bs.value = f"{total * tasa:,.2f} Bs."
        page.update()

    # --- VISTAS ---
    container_principal = ft.Column(expand=True, horizontal_alignment="center")

    def mostrar_registro(e):
        container_principal.controls.clear()
        container_principal.controls.append(ft.TextButton("< VOLVER AL MENÚ", on_click=ir_menu_principal))
        container_principal.controls.append(ft.Text("REGISTRO (+30%)", size=22, weight="bold"))
        container_principal.controls.append(txt_nombre)
        container_principal.controls.append(txt_cedula)
        container_principal.controls.append(txt_telefono)
        container_principal.controls.append(txt_monto)
        container_principal.controls.append(txt_tasa)
        container_principal.controls.append(ft.ElevatedButton("GUARDAR", on_click=registrar_pago, width=300, height=50))
        page.update()

    def mostrar_cobros(e):
        container_principal.controls.clear()
        container_principal.controls.append(ft.TextButton("< VOLVER AL MENÚ", on_click=ir_menu_principal))
        container_principal.controls.append(
            ft.Container(
                content=ft.Column([lbl_total_usd, lbl_total_bs], horizontal_alignment="center"),
                bgcolor="#e3f2fd", padding=15, border_radius=15
            )
        )
        container_principal.controls.append(ft.Divider(height=10))
        container_principal.controls.append(col_lista)
        actualizar_lista()
        calcular_totales()

    # --- PANTALLA DE LOGIN (CORREGIDA) ---
    def validar_pin(e):
        if txt_pin.value == PIN_CORRECTO:
            ir_menu_principal(None)
        else:
            txt_pin.error_text = "PIN Incorrecto"
            page.update()

    txt_pin = ft.TextField(label="PIN de Seguridad", password=True, text_align="center", keyboard_type="number", width=250)
    
    login_screen = ft.Column([
        ft.Container(height=40),
        # CORRECCIÓN AQUÍ: Usamos fit como texto directo para evitar el error de atributo
        ft.Image(
            src=r"C:\Users\Garcia\Pictures\imagen.png", 
            width=220,
            height=220,
            fit="contain", 
        ),
        ft.Text("INVERSIONES G.L.", size=30, weight="bold", color="blue"),
        ft.Text("Bienvenido", size=16, color="grey"),
        ft.Container(height=10),
        txt_pin,
        ft.ElevatedButton("ENTRAR", on_click=validar_pin, width=250, height=55)
    ], horizontal_alignment="center")

    page.add(login_screen)

ft.app(target=main)