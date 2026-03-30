from flask import Flask, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = "database.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_name TEXT,
        item_name TEXT,
        quantity INTEGER,
        request_mode TEXT,
        created_at TEXT
    )
    """)

    cur.execute("SELECT * FROM admins WHERE username = ?", ("admin",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO admins (username, password, created_at) VALUES (?, ?, ?)",
            ("admin", "123", datetime.now().isoformat())
        )

    conn.commit()
    conn.close()

@app.route("/")
def home():
    return "<h1>Almoxpert 🚀</h1><a href='/solicitar'>Nova Solicitação</a><br><a href='/admin'>Admin</a>"

@app.route("/solicitar", methods=["GET", "POST"])
def solicitar():
    if request.method == "POST":
        nome = request.form.get("nome")
        item = request.form.get("item")
        quantidade = request.form.get("quantidade")

        conn = get_db()
        conn.execute(
            "INSERT INTO requests (requester_name, item_name, quantity, request_mode, created_at) VALUES (?, ?, ?, ?, ?)",
            (nome, item, quantidade, "CATALOGO", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return "Solicitação enviada!"

    return '''
    <h2>Nova Solicitação</h2>
    <form method="post">
        Nome:<br><input name="nome"><br>
        Item:<br><input name="item"><br>
        Quantidade:<br><input name="quantidade"><br><br>
        <button type="submit">Enviar</button>
    </form>
    '''

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        user = request.form.get("user")
        pwd = request.form.get("pwd")

        conn = get_db()
        admin = conn.execute(
            "SELECT * FROM admins WHERE username=? AND password=?",
            (user, pwd)
        ).fetchone()
        conn.close()

        if admin:
            return redirect("/dashboard")
        return "Login inválido"

    return '''
    <h2>Login Admin</h2>
    <form method="post">
        Usuário:<br><input name="user"><br>
        Senha:<br><input name="pwd"><br><br>
        <button type="submit">Entrar</button>
    </form>
    '''

@app.route("/dashboard")
def dashboard():
    conn = get_db()
    requests = conn.execute("SELECT * FROM requests").fetchall()
    conn.close()

    html = "<h2>Solicitações</h2><ul>"
    for r in requests:
        html += f"<li>{r['requester_name']} pediu {r['item_name']} ({r['quantity']})</li>"
    html += "</ul>"
    return html

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
