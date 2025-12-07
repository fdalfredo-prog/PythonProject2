from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "clave-secreta"
login_manager = LoginManager(app)
DB = "datos.db"

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
    c.execute("""CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clave TEXT UNIQUE,
                    nombre TEXT,
                    estado TEXT
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT
                )""")
    conn.commit()
    try:
        c.execute("INSERT INTO usuarios (username,password,role) VALUES (?,?,?)",
                  ("admin", generate_password_hash("admin123"), "admin"))
        c.execute("INSERT INTO usuarios (username,password,role) VALUES (?,?,?)",
                  ("colaborador", generate_password_hash("colab123"), "colaborador"))
        conn.commit()
    except:
        pass
    conn.close()

def log_accion(usuario, accion, registro_id):
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS historial (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        usuario TEXT,
                        accion TEXT,
                        registro_id INTEGER,
                        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
    conn.execute("INSERT INTO historial (usuario,accion,registro_id) VALUES (?,?,?)",
                 (usuario, accion, registro_id))
    conn.commit()
    conn.close()

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
    clave = request.form["clave"]
    nombre = request.form["nombre"]
    estado = request.form["estado"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO registros (clave,nombre,estado) VALUES (?,?,?)",
              (clave, nombre, estado))
    registro_id = c.lastrowid
    conn.commit()
    conn.close()
    log_accion(current_user.username, "crear", registro_id)
    return redirect(url_for("index"))

@app.route("/editar/<int:id>", methods=["POST"])
@login_required
def editar(id):
    if current_user.role != "admin":
        return "No autorizado", 403
    nombre = request.form["nombre"]
    estado = request.form["estado"]
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE registros SET nombre=?, estado=? WHERE id=?",
                 (nombre, estado, id))
    conn.commit()
    conn.close()
    log_accion(current_user.username, "editar", id)
    return redirect(url_for("index"))

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
    df.to_excel("datos.xlsx", index=False)
    return "Archivo Excel actualizado"

if __name__ == "__main__":
    init_db()
    app.run(debug=True)