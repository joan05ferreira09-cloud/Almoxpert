import os
import sqlite3
from datetime import datetime
from functools import wraps
from uuid import uuid4

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_from_directory,
)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "almoxpert.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PRODUCT_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "products")
REQUEST_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "requests")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "Maeve0306@_almoxpert_chave_interna_2026"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["PRODUCT_UPLOAD_DIR"] = PRODUCT_UPLOAD_DIR
app.config["REQUEST_UPLOAD_DIR"] = REQUEST_UPLOAD_DIR

os.makedirs(PRODUCT_UPLOAD_DIR, exist_ok=True)
os.makedirs(REQUEST_UPLOAD_DIR, exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_br() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def now_db() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str):
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file_storage, folder_path: str):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    original_name = secure_filename(file_storage.filename)
    ext = original_name.rsplit(".", 1)[1].lower()
    filename = f"{uuid4().hex}.{ext}"
    final_path = os.path.join(folder_path, filename)
    file_storage.save(final_path)
    return filename


def create_default_username(nome: str, matricula: str | None, user_id: int) -> str:
    base = (matricula or nome.split()[0] or f"user{user_id}").strip().lower().replace(" ", "")
    cleaned = "".join(ch for ch in base if ch.isalnum()) or f"user{user_id}"
    return cleaned[:18]


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo TEXT NOT NULL UNIQUE,
            categoria TEXT,
            unidade TEXT,
            estoque_atual INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 0,
            localizacao TEXT,
            descricao TEXT,
            imagem TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS requester_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            setor TEXT,
            matricula TEXT,
            telefone TEXT,
            usuario TEXT,
            senha TEXT,
            force_password_change INTEGER NOT NULL DEFAULT 1,
            ativo INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    ensure_column(conn, "requester_users", "usuario", "usuario TEXT")
    ensure_column(conn, "requester_users", "senha", "senha TEXT")
    ensure_column(
        conn,
        "requester_users",
        "force_password_change",
        "force_password_change INTEGER NOT NULL DEFAULT 1",
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            solicitante_nome TEXT NOT NULL,
            solicitante_setor TEXT NOT NULL,
            solicitante_matricula TEXT,
            solicitante_telefone TEXT,
            item_nome TEXT NOT NULL,
            item_codigo TEXT,
            quantidade INTEGER,
            onde_sera_usado TEXT NOT NULL,
            prioridade TEXT NOT NULL,
            observacao TEXT,
            foto_referencia TEXT,
            product_id INTEGER,
            status TEXT NOT NULL DEFAULT 'PENDENTE',
            data_criacao TEXT NOT NULL,
            data_atualizacao TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        """
    )

    now = now_db()
    admin_exists = cur.execute("SELECT id FROM admin_users WHERE usuario = ?", ("Joan",)).fetchone()
    if not admin_exists:
        cur.execute(
            """
            INSERT INTO admin_users (nome, usuario, senha, ativo, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            ("Joan", "Joan", "Maeve0306@", now, now),
        )

    users_without_login = cur.execute(
        "SELECT id, nome, matricula FROM requester_users WHERE COALESCE(usuario, '') = ''"
    ).fetchall()

    for user in users_without_login:
        base_username = create_default_username(user["nome"], user["matricula"], user["id"])
        username = base_username
        suffix = 1

        while cur.execute(
            "SELECT id FROM requester_users WHERE usuario = ? AND id != ?",
            (username, user["id"]),
        ).fetchone():
            suffix += 1
            username = f"{base_username[:14]}{suffix}"

        cur.execute(
            """
            UPDATE requester_users
            SET usuario = ?, senha = COALESCE(NULLIF(senha, ''), ?), force_password_change = 1, updated_at = ?
            WHERE id = ?
            """,
            (username, f"{username}@123", now, user["id"]),
        )

    conn.commit()
    conn.close()


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Faça login para acessar o painel administrativo.", "erro")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def requester_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("requester_logged_in"):
            flash("Faça login para acessar o Almoxpert.", "erro")
            return redirect(url_for("login"))
        if session.get("force_password_change") and request.endpoint != "change_requester_password":
            flash("No primeiro acesso, troque sua senha para continuar.", "erro")
            return redirect(url_for("change_requester_password"))
        return view_func(*args, **kwargs)

    return wrapped


@app.route("/")
def home():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    if session.get("requester_logged_in"):
        if session.get("force_password_change"):
            return redirect(url_for("change_requester_password"))
        return redirect(url_for("requester_home"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()

        conn = get_conn()

        admin = conn.execute(
            "SELECT * FROM admin_users WHERE usuario = ? AND senha = ? AND ativo = 1",
            (usuario, senha),
        ).fetchone()

        if admin:
            conn.close()
            session.clear()
            session["admin_logged_in"] = True
            session["admin_user_id"] = admin["id"]
            session["admin_nome"] = admin["nome"]
            flash("Login administrativo realizado com sucesso.", "sucesso")
            return redirect(url_for("admin_dashboard"))

        requester = conn.execute(
            "SELECT * FROM requester_users WHERE usuario = ? AND senha = ? AND ativo = 1",
            (usuario, senha),
        ).fetchone()
        conn.close()

        if requester:
            session.clear()
            session["requester_logged_in"] = True
            session["requester_user_id"] = requester["id"]
            session["requester_nome"] = requester["nome"]
            session["requester_setor"] = requester["setor"] or "Não informado"
            session["requester_matricula"] = requester["matricula"] or ""
            session["requester_telefone"] = requester["telefone"] or ""
            session["force_password_change"] = bool(requester["force_password_change"])

            if requester["force_password_change"]:
                flash("Primeiro acesso detectado. Defina sua nova senha.", "sucesso")
                return redirect(url_for("change_requester_password"))

            flash("Login realizado com sucesso.", "sucesso")
            return redirect(url_for("requester_home"))

        flash("Usuário ou senha inválidos.", "erro")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/trocar-senha", methods=["GET", "POST"])
@requester_required
def change_requester_password():
    if request.method == "POST":
        nova_senha = request.form.get("nova_senha", "").strip()
        confirmar_senha = request.form.get("confirmar_senha", "").strip()

        if len(nova_senha) < 6:
            flash("A nova senha precisa ter pelo menos 6 caracteres.", "erro")
            return redirect(url_for("change_requester_password"))

        if nova_senha != confirmar_senha:
            flash("As senhas não conferem.", "erro")
            return redirect(url_for("change_requester_password"))

        conn = get_conn()
        conn.execute(
            "UPDATE requester_users SET senha = ?, force_password_change = 0, updated_at = ? WHERE id = ?",
            (nova_senha, now_db(), session["requester_user_id"]),
        )
        conn.commit()
        conn.close()

        session["force_password_change"] = False
        flash("Senha alterada com sucesso.", "sucesso")
        return redirect(url_for("requester_home"))

    return render_template("change_password.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sessão encerrada.", "sucesso")
    return redirect(url_for("login"))


@app.route("/solicitante")
@requester_required
def requester_home():
    return render_template("index.html")


@app.route("/catalog-search")
@requester_required
def catalog_search():
    query = request.args.get("q", "").strip()
    conn = get_conn()

    if query:
        like = f"%{query}%"
        products = conn.execute(
            """
            SELECT id, nome, codigo, categoria, unidade, estoque_atual, estoque_minimo, localizacao, descricao, imagem
            FROM products
            WHERE ativo = 1
              AND (nome LIKE ? OR codigo LIKE ? OR categoria LIKE ?)
            ORDER BY nome COLLATE NOCASE ASC
            LIMIT 12
            """,
            (like, like, like),
        ).fetchall()
    else:
        products = []

    conn.close()

    result = []
    for p in products:
        result.append(
            {
                "id": p["id"],
                "nome": p["nome"],
                "codigo": p["codigo"],
                "categoria": p["categoria"] or "Sem categoria",
                "unidade": p["unidade"] or "UN",
                "estoque_atual": p["estoque_atual"],
                "estoque_minimo": p["estoque_minimo"],
                "localizacao": p["localizacao"] or "Não informada",
                "descricao": p["descricao"] or "",
                "imagem_url": (
                    url_for("uploaded_file", folder="products", filename=p["imagem"])
                    if p["imagem"]
                    else url_for("static", filename="img/placeholder-product.svg")
                ),
            }
        )
    return jsonify(result)


@app.route("/solicitar-catalogo", methods=["POST"])
@requester_required
def solicitar_catalogo():
    item_nome = request.form.get("item_nome", "").strip()
    item_codigo = request.form.get("item_codigo", "").strip()
    quantidade = request.form.get("quantidade", "").strip()
    onde_sera_usado = request.form.get("onde_sera_usado", "").strip()
    prioridade = request.form.get("prioridade", "Normal").strip() or "Normal"
    observacao = request.form.get("observacao", "").strip()
    product_id = request.form.get("product_id", "").strip() or None

    if not item_nome or not onde_sera_usado:
        flash("Selecione um item e informe onde ele será usado.", "erro")
        return redirect(url_for("requester_home"))

    try:
        quantidade_int = int(quantidade)
        if quantidade_int <= 0:
            raise ValueError
    except ValueError:
        flash("A quantidade deve ser um número maior que zero.", "erro")
        return redirect(url_for("requester_home"))

    conn = get_conn()
    requester = conn.execute(
        "SELECT * FROM requester_users WHERE id = ?",
        (session["requester_user_id"],),
    ).fetchone()

    conn.execute(
        """
        INSERT INTO requests (
            tipo, solicitante_nome, solicitante_setor, solicitante_matricula, solicitante_telefone,
            item_nome, item_codigo, quantidade, onde_sera_usado, prioridade, observacao,
            foto_referencia, product_id, status, data_criacao, data_atualizacao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', ?, ?)
        """,
        (
            "CATALOGO",
            requester["nome"],
            requester["setor"] or "Não informado",
            requester["matricula"] or "",
            requester["telefone"] or "",
            item_nome,
            item_codigo,
            quantidade_int,
            onde_sera_usado,
            prioridade,
            observacao,
            None,
            product_id,
            now_br(),
            now_br(),
        ),
    )
    conn.commit()
    conn.close()

    flash("Solicitação enviada com sucesso.", "sucesso")
    return redirect(url_for("requester_home"))


@app.route("/solicitar-item-novo", methods=["POST"])
@requester_required
def solicitar_item_novo():
    item_nome = request.form.get("item_nome_novo", "").strip()
    quantidade = request.form.get("quantidade_novo", "").strip()
    onde_sera_usado = request.form.get("onde_sera_usado_novo", "").strip()
    prioridade = request.form.get("prioridade_novo", "Normal").strip() or "Normal"
    observacao = request.form.get("observacao_novo", "").strip()
    foto = request.files.get("foto_item_novo")

    if not item_nome or not onde_sera_usado:
        flash("Informe o nome do item novo e onde ele será usado.", "erro")
        return redirect(url_for("requester_home"))

    try:
        quantidade_int = int(quantidade)
        if quantidade_int <= 0:
            raise ValueError
    except ValueError:
        flash("A quantidade do item novo deve ser um número maior que zero.", "erro")
        return redirect(url_for("requester_home"))

    foto_filename = None
    if foto and foto.filename:
        foto_filename = save_uploaded_file(foto, app.config["REQUEST_UPLOAD_DIR"])
        if not foto_filename:
            flash("Formato de imagem inválido. Use PNG, JPG, JPEG, WEBP ou GIF.", "erro")
            return redirect(url_for("requester_home"))

    conn = get_conn()
    requester = conn.execute(
        "SELECT * FROM requester_users WHERE id = ?",
        (session["requester_user_id"],),
    ).fetchone()

    conn.execute(
        """
        INSERT INTO requests (
            tipo, solicitante_nome, solicitante_setor, solicitante_matricula, solicitante_telefone,
            item_nome, item_codigo, quantidade, onde_sera_usado, prioridade, observacao,
            foto_referencia, product_id, status, data_criacao, data_atualizacao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', ?, ?)
        """,
        (
            "ITEM_NOVO",
            requester["nome"],
            requester["setor"] or "Não informado",
            requester["matricula"] or "",
            requester["telefone"] or "",
            item_nome,
            "NOVO",
            quantidade_int,
            onde_sera_usado,
            prioridade,
            observacao,
            foto_filename,
            None,
            now_br(),
            now_br(),
        ),
    )
    conn.commit()
    conn.close()

    flash("Solicitação de item novo enviada com sucesso.", "sucesso")
    return redirect(url_for("requester_home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_conn()

    total_requests = conn.execute("SELECT COUNT(*) AS total FROM requests").fetchone()["total"]
    total_pending = conn.execute("SELECT COUNT(*) AS total FROM requests WHERE status = 'PENDENTE'").fetchone()["total"]
    total_approved = conn.execute("SELECT COUNT(*) AS total FROM requests WHERE status = 'APROVADO'").fetchone()["total"]
    total_rejected = conn.execute("SELECT COUNT(*) AS total FROM requests WHERE status = 'RECUSADO'").fetchone()["total"]
    total_products = conn.execute("SELECT COUNT(*) AS total FROM products WHERE ativo = 1").fetchone()["total"]
    total_users = conn.execute("SELECT COUNT(*) AS total FROM requester_users WHERE ativo = 1").fetchone()["total"]
    low_stock = conn.execute(
        "SELECT COUNT(*) AS total FROM products WHERE ativo = 1 AND estoque_atual <= estoque_minimo"
    ).fetchone()["total"]
    urgent_open = conn.execute(
        "SELECT COUNT(*) AS total FROM requests WHERE status = 'PENDENTE' AND prioridade = 'Urgente'"
    ).fetchone()["total"]

    latest_requests = conn.execute("SELECT * FROM requests ORDER BY id DESC LIMIT 8").fetchall()

    sector_kpis = conn.execute(
        """
        SELECT
            COALESCE(solicitante_setor, 'Não informado') AS setor,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'PENDENTE' THEN 1 ELSE 0 END) AS pendentes,
            SUM(CASE WHEN status = 'APROVADO' THEN 1 ELSE 0 END) AS aprovadas,
            SUM(CASE WHEN status = 'RECUSADO' THEN 1 ELSE 0 END) AS recusadas,
            SUM(CASE WHEN prioridade = 'Urgente' THEN 1 ELSE 0 END) AS urgentes,
            ROUND((SUM(CASE WHEN status = 'APROVADO' THEN 1 ELSE 0 END) * 100.0) / COUNT(*), 1) AS taxa_aprovacao
        FROM requests
        GROUP BY COALESCE(solicitante_setor, 'Não informado')
        ORDER BY total DESC, setor ASC
        """
    ).fetchall()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_requests=total_requests,
        total_pending=total_pending,
        total_approved=total_approved,
        total_rejected=total_rejected,
        total_products=total_products,
        total_users=total_users,
        low_stock=low_stock,
        urgent_open=urgent_open,
        latest_requests=latest_requests,
        sector_kpis=sector_kpis,
    )


@app.route("/admin/solicitacoes")
@admin_required
def admin_requests():
    status = request.args.get("status", "").strip().upper()
    search = request.args.get("search", "").strip()

    query = "SELECT * FROM requests WHERE 1=1"
    params = []

    if status in {"PENDENTE", "APROVADO", "RECUSADO"}:
        query += " AND status = ?"
        params.append(status)

    if search:
        like = f"%{search}%"
        query += " AND (solicitante_nome LIKE ? OR item_nome LIKE ? OR COALESCE(item_codigo, '') LIKE ? OR COALESCE(onde_sera_usado, '') LIKE ?)"
        params.extend([like, like, like, like])

    query += " ORDER BY id DESC"

    conn = get_conn()
    requests_data = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "admin_requests.html",
        requests_data=requests_data,
        current_status=status,
        current_search=search,
    )


@app.route("/admin/solicitacoes/<int:request_id>/status/<string:new_status>")
@admin_required
def update_request_status(request_id, new_status):
    new_status = new_status.upper()

    if new_status not in {"PENDENTE", "APROVADO", "RECUSADO"}:
        flash("Status inválido.", "erro")
        return redirect(url_for("admin_requests"))

    conn = get_conn()

    solicitacao = conn.execute(
        "SELECT * FROM requests WHERE id = ?",
        (request_id,),
    ).fetchone()

    if not solicitacao:
        conn.close()
        flash("Solicitação não encontrada.", "erro")
        return redirect(url_for("admin_requests"))

    status_atual = (solicitacao["status"] or "").upper()
    tipo = (solicitacao["tipo"] or "").upper()
    product_id = solicitacao["product_id"]

    try:
        quantidade = int(solicitacao["quantidade"] or 0)
    except (TypeError, ValueError):
        quantidade = 0

    produto = None
    if product_id:
        produto = conn.execute(
            "SELECT * FROM products WHERE id = ? AND ativo = 1",
            (product_id,),
        ).fetchone()

    try:
        if status_atual == "APROVADO" and new_status in {"PENDENTE", "RECUSADO"}:
            if tipo == "CATALOGO" and produto and quantidade > 0:
                novo_estoque = int(produto["estoque_atual"] or 0) + quantidade
                conn.execute(
                    """
                    UPDATE products
                    SET estoque_atual = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (novo_estoque, now_db(), product_id),
                )

        if status_atual != "APROVADO" and new_status == "APROVADO":
            if tipo == "CATALOGO":
                if not produto:
                    conn.close()
                    flash("Produto vinculado não encontrado para baixar o estoque.", "erro")
                    return redirect(url_for("admin_requests"))

                estoque_atual = int(produto["estoque_atual"] or 0)

                if quantidade <= 0:
                    conn.close()
                    flash("Quantidade inválida na solicitação.", "erro")
                    return redirect(url_for("admin_requests"))

                if estoque_atual < quantidade:
                    conn.close()
                    flash(
                        f"Estoque insuficiente para aprovar. Disponível: {estoque_atual} | Solicitado: {quantidade}.",
                        "erro",
                    )
                    return redirect(url_for("admin_requests"))

                novo_estoque = estoque_atual - quantidade
                conn.execute(
                    """
                    UPDATE products
                    SET estoque_atual = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (novo_estoque, now_db(), product_id),
                )

        conn.execute(
            """
            UPDATE requests
            SET status = ?, data_atualizacao = ?
            WHERE id = ?
            """,
            (new_status, now_br(), request_id),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        conn.close()
        flash("Erro ao atualizar a solicitação.", "erro")
        return redirect(url_for("admin_requests"))

    conn.close()

    if status_atual != "APROVADO" and new_status == "APROVADO" and tipo == "CATALOGO":
        flash("Solicitação aprovada e estoque baixado automaticamente.", "sucesso")
    elif status_atual == "APROVADO" and new_status in {"PENDENTE", "RECUSADO"} and tipo == "CATALOGO":
        flash("Status alterado e estoque devolvido automaticamente.", "sucesso")
    else:
        flash(f"Solicitação atualizada para {new_status}.", "sucesso")

    return redirect(url_for("admin_requests"))


@app.route("/admin/produtos")
@admin_required
def admin_products():
    search = request.args.get("search", "").strip()
    only_low = request.args.get("low_stock", "").strip()

    query = "SELECT * FROM products WHERE ativo = 1"
    params = []

    if search:
        like = f"%{search}%"
        query += " AND (nome LIKE ? OR codigo LIKE ? OR COALESCE(categoria, '') LIKE ? OR COALESCE(localizacao, '') LIKE ?)"
        params.extend([like, like, like, like])

    if only_low == "1":
        query += " AND estoque_atual <= estoque_minimo"

    query += " ORDER BY nome COLLATE NOCASE ASC"

    conn = get_conn()
    products = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "admin_products.html",
        products=products,
        current_search=search,
        low_stock=only_low,
    )


@app.route("/admin/produtos/novo", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        codigo = request.form.get("codigo", "").strip()
        categoria = request.form.get("categoria", "").strip()
        unidade = request.form.get("unidade", "").strip()
        estoque_atual = request.form.get("estoque_atual", "0").strip()
        estoque_minimo = request.form.get("estoque_minimo", "0").strip()
        localizacao = request.form.get("localizacao", "").strip()
        descricao = request.form.get("descricao", "").strip()
        imagem = request.files.get("imagem")

        if not nome or not codigo:
            flash("Nome e código do produto são obrigatórios.", "erro")
            return redirect(url_for("admin_product_new"))

        try:
            estoque_atual_int = int(estoque_atual or 0)
            estoque_minimo_int = int(estoque_minimo or 0)
        except ValueError:
            flash("Estoque atual e estoque mínimo devem ser números inteiros.", "erro")
            return redirect(url_for("admin_product_new"))

        image_filename = None
        if imagem and imagem.filename:
            image_filename = save_uploaded_file(imagem, app.config["PRODUCT_UPLOAD_DIR"])
            if not image_filename:
                flash("A imagem do produto precisa ser PNG, JPG, JPEG, WEBP ou GIF.", "erro")
                return redirect(url_for("admin_product_new"))

        conn = get_conn()
        exists = conn.execute("SELECT id FROM products WHERE codigo = ?", (codigo,)).fetchone()
        if exists:
            conn.close()
            flash("Já existe um produto cadastrado com esse código.", "erro")
            return redirect(url_for("admin_product_new"))

        conn.execute(
            """
            INSERT INTO products (
                nome, codigo, categoria, unidade, estoque_atual, estoque_minimo,
                localizacao, descricao, imagem, ativo, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                nome,
                codigo,
                categoria,
                unidade,
                estoque_atual_int,
                estoque_minimo_int,
                localizacao,
                descricao,
                image_filename,
                now_db(),
                now_db(),
            ),
        )
        conn.commit()
        conn.close()

        flash("Produto cadastrado com sucesso.", "sucesso")
        return redirect(url_for("admin_products"))

    return render_template("admin_product_form.html", product=None)


@app.route("/admin/produtos/<int:product_id>/editar", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    conn = get_conn()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    if not product:
        conn.close()
        flash("Produto não encontrado.", "erro")
        return redirect(url_for("admin_products"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        codigo = request.form.get("codigo", "").strip()
        categoria = request.form.get("categoria", "").strip()
        unidade = request.form.get("unidade", "").strip()
        estoque_atual = request.form.get("estoque_atual", "0").strip()
        estoque_minimo = request.form.get("estoque_minimo", "0").strip()
        localizacao = request.form.get("localizacao", "").strip()
        descricao = request.form.get("descricao", "").strip()
        imagem = request.files.get("imagem")

        if not nome or not codigo:
            conn.close()
            flash("Nome e código do produto são obrigatórios.", "erro")
            return redirect(url_for("admin_product_edit", product_id=product_id))

        try:
            estoque_atual_int = int(estoque_atual or 0)
            estoque_minimo_int = int(estoque_minimo or 0)
        except ValueError:
            conn.close()
            flash("Estoque atual e estoque mínimo devem ser números inteiros.", "erro")
            return redirect(url_for("admin_product_edit", product_id=product_id))

        duplicate = conn.execute(
            "SELECT id FROM products WHERE codigo = ? AND id != ?",
            (codigo, product_id),
        ).fetchone()
        if duplicate:
            conn.close()
            flash("Já existe outro produto com esse código.", "erro")
            return redirect(url_for("admin_product_edit", product_id=product_id))

        image_filename = product["imagem"]
        if imagem and imagem.filename:
            new_filename = save_uploaded_file(imagem, app.config["PRODUCT_UPLOAD_DIR"])
            if not new_filename:
                conn.close()
                flash("A imagem do produto precisa ser PNG, JPG, JPEG, WEBP ou GIF.", "erro")
                return redirect(url_for("admin_product_edit", product_id=product_id))
            image_filename = new_filename

        conn.execute(
            """
            UPDATE products
            SET nome = ?, codigo = ?, categoria = ?, unidade = ?, estoque_atual = ?, estoque_minimo = ?,
                localizacao = ?, descricao = ?, imagem = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                nome,
                codigo,
                categoria,
                unidade,
                estoque_atual_int,
                estoque_minimo_int,
                localizacao,
                descricao,
                image_filename,
                now_db(),
                product_id,
            ),
        )
        conn.commit()
        conn.close()

        flash("Produto atualizado com sucesso.", "sucesso")
        return redirect(url_for("admin_products"))

    conn.close()
    return render_template("admin_product_form.html", product=product)


@app.route("/admin/produtos/<int:product_id>/excluir")
@admin_required
def admin_product_delete(product_id):
    conn = get_conn()
    conn.execute(
        "UPDATE products SET ativo = 0, updated_at = ? WHERE id = ?",
        (now_db(), product_id),
    )
    conn.commit()
    conn.close()

    flash("Produto excluído com sucesso.", "sucesso")
    return redirect(url_for("admin_products"))


@app.route("/admin/usuarios")
@admin_required
def admin_users():
    search = request.args.get("search", "").strip()

    query = "SELECT * FROM requester_users WHERE ativo = 1"
    params = []
    if search:
        like = f"%{search}%"
        query += " AND (nome LIKE ? OR COALESCE(setor, '') LIKE ? OR COALESCE(matricula, '') LIKE ? OR COALESCE(usuario, '') LIKE ?)"
        params.extend([like, like, like, like])

    query += " ORDER BY nome COLLATE NOCASE ASC"

    conn = get_conn()
    users = conn.execute(query, params).fetchall()
    conn.close()

    return render_template("admin_users.html", users=users, current_search=search)


@app.route("/admin/usuarios/novo", methods=["GET", "POST"])
@admin_required
def admin_user_new():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        setor = request.form.get("setor", "").strip()
        matricula = request.form.get("matricula", "").strip()
        telefone = request.form.get("telefone", "").strip()
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()

        if not nome or not usuario or not senha:
            flash("Nome, login e senha temporária são obrigatórios.", "erro")
            return redirect(url_for("admin_user_new"))

        conn = get_conn()
        duplicate = conn.execute("SELECT id FROM requester_users WHERE usuario = ?", (usuario,)).fetchone()
        if duplicate:
            conn.close()
            flash("Já existe um solicitante com esse login.", "erro")
            return redirect(url_for("admin_user_new"))

        conn.execute(
            """
            INSERT INTO requester_users (nome, setor, matricula, telefone, usuario, senha, force_password_change, ativo, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (nome, setor, matricula, telefone, usuario, senha, now_db(), now_db()),
        )
        conn.commit()
        conn.close()

        flash("Solicitante cadastrado com sucesso. No primeiro acesso ele terá que trocar a senha.", "sucesso")
        return redirect(url_for("admin_users"))

    return render_template("admin_user_form.html", user=None)


@app.route("/admin/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
@admin_required
def admin_user_edit(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM requester_users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        conn.close()
        flash("Usuário não encontrado.", "erro")
        return redirect(url_for("admin_users"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        setor = request.form.get("setor", "").strip()
        matricula = request.form.get("matricula", "").strip()
        telefone = request.form.get("telefone", "").strip()
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()
        force_password_change = 1 if request.form.get("force_password_change") == "1" else 0

        if not nome or not usuario:
            conn.close()
            flash("Nome e login são obrigatórios.", "erro")
            return redirect(url_for("admin_user_edit", user_id=user_id))

        duplicate = conn.execute(
            "SELECT id FROM requester_users WHERE usuario = ? AND id != ?",
            (usuario, user_id),
        ).fetchone()
        if duplicate:
            conn.close()
            flash("Já existe outro solicitante com esse login.", "erro")
            return redirect(url_for("admin_user_edit", user_id=user_id))

        final_password = senha if senha else user["senha"]

        conn.execute(
            """
            UPDATE requester_users
            SET nome = ?, setor = ?, matricula = ?, telefone = ?, usuario = ?, senha = ?, force_password_change = ?, updated_at = ?
            WHERE id = ?
            """,
            (nome, setor, matricula, telefone, usuario, final_password, force_password_change, now_db(), user_id),
        )
        conn.commit()
        conn.close()

        flash("Solicitante atualizado com sucesso.", "sucesso")
        return redirect(url_for("admin_users"))

    conn.close()
    return render_template("admin_user_form.html", user=user)


@app.route("/admin/usuarios/<int:user_id>/excluir")
@admin_required
def admin_user_delete(user_id):
    conn = get_conn()
    conn.execute(
        "UPDATE requester_users SET ativo = 0, updated_at = ? WHERE id = ?",
        (now_db(), user_id),
    )
    conn.commit()
    conn.close()

    flash("Solicitante excluído com sucesso.", "sucesso")
    return redirect(url_for("admin_users"))


@app.route("/uploads/<folder>/<filename>")
def uploaded_file(folder, filename):
    if folder == "products":
        return send_from_directory(app.config["PRODUCT_UPLOAD_DIR"], filename)
    if folder == "requests":
        return send_from_directory(app.config["REQUEST_UPLOAD_DIR"], filename)
    return "Arquivo não encontrado", 404


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
else:
    init_db()
