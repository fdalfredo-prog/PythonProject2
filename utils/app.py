from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
import xlsxwriter
from datetime import datetime


app = Flask(__name__)
app.secret_key = "clave-secreta"
login_manager = LoginManager(app)
DB = "datos.db"

# Modelo de usuario
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM usuarios WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return User(*row)
    return None

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Tabla de registros
    c.execute("""CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT,
                    albaran TEXT,
                    factura_villena TEXT,
                    proveedor TEXT,
                    cantidad REAL
                )""")
    # Tabla de usuarios
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT
                )""")
    # Tabla de historial
    c.execute("""CREATE TABLE IF NOT EXISTS historial (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT,
                    accion TEXT,
                    registro_id INTEGER,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
    conn.commit()
    # Crear usuarios por defecto
    try:
        c.execute("INSERT INTO usuarios (username,password,role) VALUES (?,?,?)",
                  ("admin", generate_password_hash("666"), "admin"))
        c.execute("INSERT INTO usuarios (username,password,role) VALUES (?,?,?)",
                  ("colaborador", generate_password_hash("colab123"), "colaborador"))
        conn.commit()
    except:
        pass
    conn.close()

def log_accion(usuario, accion, registro_id):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO historial (usuario,accion,registro_id) VALUES (?,?,?)",
                 (usuario, accion, registro_id))
    conn.commit()
    conn.close()

# 🔑 Filtro Jinja para mostrar fechas en dd/mm/yyyy
@app.template_filter("datetimeformat")
def datetimeformat(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return value


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT id, username, password, role FROM usuarios WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()
        if row and check_password_hash(row[2], password):
            user = User(row[0], row[1], row[3])
            login_user(user)
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    conn = sqlite3.connect(DB)
    registros = conn.execute("SELECT * FROM registros").fetchall()
    conn.close()
    return render_template("index.html", registros=registros, role=current_user.role)

@app.route("/nuevo", methods=["POST"])
@login_required
def nuevo():
    fecha = request.form["fecha"]
    albaran = request.form["albaran"]
    factura_villena = request.form["factura_villena"]
    proveedor = request.form["proveedor"]
    cantidad = request.form["cantidad"]

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO registros (fecha, albaran, factura_villena, proveedor, cantidad) VALUES (?,?,?,?,?)",
              (fecha, albaran, factura_villena, proveedor, cantidad))
    registro_id = c.lastrowid
    conn.commit()
    conn.close()
    log_accion(current_user.username, "crear", registro_id)
    return redirect(url_for("index"))

@app.route("/editar/<int:id>", methods=["GET","POST"])
@login_required
def editar(id):
    if current_user.role != "admin":
        return "No autorizado", 403

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    if request.method == "POST":
        fecha = request.form.get("fecha")
        albaran = request.form.get("albaran")
        factura_villena = request.form.get("factura_villena")
        proveedor = request.form.get("proveedor")
        cantidad = request.form.get("cantidad")

        c.execute("UPDATE registros SET fecha=?, albaran=?, factura_villena=?, proveedor=?, cantidad=? WHERE id=?",
                  (fecha, albaran, factura_villena, proveedor, cantidad, id))
        conn.commit()
        conn.close()
        log_accion(current_user.username, "editar", id)
        return redirect(url_for("index"))
    else:
        registro = c.execute("SELECT * FROM registros WHERE id=?", (id,)).fetchone()
        conn.close()
        return render_template("editar.html", registro=registro)

@app.route("/borrar/<int:id>")
@login_required
def borrar(id):
    if current_user.role != "admin":
        return "No autorizado", 403
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM registros WHERE id=?", (id,))
    conn.commit()
    conn.close()
    log_accion(current_user.username, "borrar", id)
    return redirect(url_for("index"))

@app.route("/historial")
@login_required
def ver_historial():
    conn = sqlite3.connect(DB)
    historial = conn.execute("SELECT * FROM historial ORDER BY fecha DESC").fetchall()
    conn.close()
    return render_template("historial.html", historial=historial)

@app.route("/exportar")
@login_required
def exportar():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM registros", conn)
    conn.close()

    # Convertir fecha a datetime
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    # Crear Excel con XlsxWriter
    workbook = xlsxwriter.Workbook("datos.xlsx")
    worksheet = workbook.add_worksheet("Registros")

    # Formatos
    formato_fecha = workbook.add_format({"num_format": "dd/mm/yyyy", "align": "center"})
    formato_textoC = workbook.add_format({"align": "center"})
    formato_textoL = workbook.add_format({"align": "left"})
    formato_numero = workbook.add_format({"num_format": "#,##0.00", "align": "right"})
    formato_header = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "align": "center"})

    # Cabeceras
    headers = list(df.columns)
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, formato_header)

    # Filas con formato celda por celda
    for row_num, row in enumerate(df.itertuples(index=False), start=1):
        worksheet.write(row_num, 0, row.id, formato_textoC)
        worksheet.write_datetime(row_num, 1, row.fecha.to_pydatetime(), formato_fecha)
        worksheet.write(row_num, 2, row.albaran, formato_textoC)
        worksheet.write(row_num, 3, row.factura_villena, formato_textoC)
        worksheet.write(row_num, 4, row.proveedor, formato_textoC)
        worksheet.write(row_num, 5, row.cantidad, formato_numero)

    # Ajustar anchos
    worksheet.set_column(0, 0, 4)      # id
    worksheet.set_column(1, 1, 15, formato_fecha)      # fecha
    worksheet.set_column(2, 2, 15, formato_textoC)      # albaran
    worksheet.set_column(3, 3, 17, formato_textoC)      # factura_villena
    worksheet.set_column(4, 4, 50, formato_textoC)      # proveedor
    worksheet.set_column(5, 5, 10, formato_textoL)     # cantidad

    # Añadir tabla estructurada
    (max_row, max_col) = df.shape
    column_settings = [{"header": col} for col in df.columns]
    worksheet.add_table(0, 0, max_row, max_col-1,
                        {"columns": column_settings,
                         "style": "Table Style Medium 9"})

    workbook.close()
    return "Archivo Excel creado con formato de tabla y fecha dd/mm/yyyy"

if __name__ == "__main__":
    init_db()
    app.run(debug=True)