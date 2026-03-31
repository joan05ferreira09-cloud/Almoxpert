import os
import sqlite3
from datetime import datetime
from functools import wraps
from uuid import uuid4
from werkzeug.utils import secure_filename
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "almal_expert.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PRODUCT_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "products")
REQUEST_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "requests")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "Maeve0306@_almal_expert_chave_interna_2026"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["PRODUCT_UPLOAD_DIR"] = PRODUCT_UPLOAD_DIR
app.config["REQUEST_UPLOAD_DIR"] = REQUEST_UPLOAD_DIR


os.makedirs(PRODUCT_UPLOAD_DIR, exist_ok=True)
os.makedirs(REQUEST_UPLOAD_DIR, exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
            ativo INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
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

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin_exists = cur.execute("SELECT id FROM admin_users WHERE usuario = ?", ("Joan",)).fetchone()
    if not admin_exists:
        cur.execute(
            """
            INSERT INTO admin_users (nome, usuario, senha, ativo, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            ("Joan", "Joan", "Maeve0306@", now, now),
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


def now_br():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def now_db():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@app.route("/")
def home():
    conn = get_conn()
    products = conn.execute(
        """
        SELECT * FROM products
        WHERE ativo = 1
        ORDER BY nome COLLATE NOCASE ASC
        """
    ).fetchall()
    conn.close()
    return render_template("index.html", products=products)


@app.route("/catalog-search")
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
                "imagem_url": url_for("uploaded_file", folder="products", filename=p["imagem"]) if p["imagem"] else url_for("static", filename="img/placeholder-product.svg"),
            }
        )

    return jsonify(result)


@app.route("/solicitar-catalogo", methods=["POST"])
def solicitar_catalogo():
    solicitante_nome = request.form.get("solicitante_nome", "").strip()
    solicitante_setor = request.form.get("solicitante_setor", "").strip()
    solicitante_matricula = request.form.get("solicitante_matricula", "").strip()
    solicitante_telefone = request.form.get("solicitante_telefone", "").strip()
    item_nome = request.form.get("item_nome", "").strip()
    item_codigo = request.form.get("item_codigo", "").strip()
    quantidade = request.form.get("quantidade", "").strip()
    onde_sera_usado = request.form.get("onde_sera_usado", "").strip()
    prioridade = request.form.get("prioridade", "Normal").strip() or "Normal"
    observacao = request.form.get("observacao", "").strip()
    product_id = request.form.get("product_id", "").strip() or None

    if not solicitante_nome or not solicitante_setor or not item_nome or not onde_sera_usado:
        flash("Preencha todos os campos obrigatórios da solicitação por catálogo.", "erro")
        return redirect(url_for("home"))

    try:
        quantidade_int = int(quantidade)
        if quantidade_int <= 0:
            raise ValueError
    except ValueError:
        flash("A quantidade deve ser um número maior que zero.", "erro")
        return redirect(url_for("home"))

    conn = get_conn()
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
            solicitante_nome,
            solicitante_setor,
            solicitante_matricula,
            solicitante_telefone,
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

    flash("Solicitação por catálogo enviada com sucesso.", "sucesso")
    return redirect(url_for("home"))


@app.route("/solicitar-novo", methods=["POST"])
def solicitar_novo():
    solicitante_nome = request.form.get("solicitante_nome", "").strip()
    solicitante_setor = request.form.get("solicitante_setor", "").strip()
    solicitante_matricula = request.form.get("solicitante_matricula", "").strip()
    solicitante_telefone = request.form.get("solicitante_telefone", "").strip()
    item_nome = request.form.get("item_nome", "").strip()
    quantidade = request.form.get("quantidade", "").strip()
    onde_sera_usado = request.form.get("onde_sera_usado", "").strip()
    prioridade = request.form.get("prioridade", "Normal").strip() or "Normal"
    observacao = request.form.get("observacao", "").strip()
    foto = request.files.get("foto_referencia")

    if not solicitante_nome or not solicitante_setor or not item_nome or not onde_sera_usado:
        flash("Preencha todos os campos obrigatórios da nova solicitação.", "erro")
        return redirect(url_for("home"))

    try:
        quantidade_int = int(quantidade)
        if quantidade_int <= 0:
            raise ValueError
    except ValueError:
        flash("A quantidade deve ser um número maior que zero.", "erro")
        return redirect(url_for("home"))

    foto_filename = None
    if foto and foto.filename:
        foto_filename = save_uploaded_file(foto, app.config["REQUEST_UPLOAD_DIR"])
        if not foto_filename:
            flash("A foto precisa ser PNG, JPG, JPEG, WEBP ou GIF.", "erro")
            return redirect(url_for("home"))

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO requests (
            tipo, solicitante_nome, solicitante_setor, solicitante_matricula, solicitante_telefone,
            item_nome, item_codigo, quantidade, onde_sera_usado, prioridade, observacao,
            foto_referencia, product_id, status, data_criacao, data_atualizacao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', ?, ?)
        """,
        (
            "NOVO_ITEM",
            solicitante_nome,
            solicitante_setor,
            solicitante_matricula,
            solicitante_telefone,
            item_nome,
            None,
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

    flash("Nova solicitação enviada com sucesso.", "sucesso")
    return redirect(url_for("home"))


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
        conn.close()

        if admin:
            session["admin_logged_in"] = True
            session["admin_user_id"] = admin["id"]
            session["admin_nome"] = admin["nome"]
            flash("Login realizado com sucesso.", "sucesso")
            return redirect(url_for("admin_dashboard"))

        flash("Usuário ou senha inválidos.", "erro")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sessão encerrada.", "sucesso")
    return redirect(url_for("login"))


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

    latest_requests = conn.execute(
        """
        SELECT * FROM requests
        ORDER BY id DESC
        LIMIT 8
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
        latest_requests=latest_requests,
    )


@app.route("/admin/solicitacoes")
@admin_required
def admin_requests():
    status = request.args.get("status", "").strip().upper()
    search = request.args.get("search", "").strip()

    query = """
        SELECT * FROM requests
        WHERE 1=1
    """
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

    return render_template("admin_requests.html", requests_data=requests_data, current_status=status, current_search=search)


@app.route("/admin/solicitacoes/<int:request_id>/status/<string:new_status>")
@admin_required
def update_request_status(request_id, new_status):
    new_status = new_status.upper()
    if new_status not in {"PENDENTE", "APROVADO", "RECUSADO"}:
        flash("Status inválido.", "erro")
        return redirect(url_for("admin_requests"))

    conn = get_conn()
    conn.execute(
        "UPDATE requests SET status = ?, data_atualizacao = ? WHERE id = ?",
        (new_status, now_br(), request_id),
    )
    conn.commit()
    conn.close()

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

    return render_template("admin_products.html", products=products, current_search=search, low_stock=only_low)


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
        query += " AND (nome LIKE ? OR COALESCE(setor, '') LIKE ? OR COALESCE(matricula, '') LIKE ? OR COALESCE(telefone, '') LIKE ?)"
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

        if not nome:
            flash("O nome do usuário é obrigatório.", "erro")
            return redirect(url_for("admin_user_new"))

        conn = get_conn()
        conn.execute(
            """
            INSERT INTO requester_users (nome, setor, matricula, telefone, ativo, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (nome, setor, matricula, telefone, now_db(), now_db()),
        )
        conn.commit()
        conn.close()

        flash("Usuário cadastrado com sucesso.", "sucesso")
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

        if not nome:
            conn.close()
            flash("O nome do usuário é obrigatório.", "erro")
            return redirect(url_for("admin_user_edit", user_id=user_id))

        conn.execute(
            """
            UPDATE requester_users
            SET nome = ?, setor = ?, matricula = ?, telefone = ?, updated_at = ?
            WHERE id = ?
            """,
            (nome, setor, matricula, telefone, now_db(), user_id),
        )
        conn.commit()
        conn.close()

        flash("Usuário atualizado com sucesso.", "sucesso")
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

    flash("Usuário excluído com sucesso.", "sucesso")
    return redirect(url_for("admin_users"))


@app.route("/uploads/<folder>/<filename>")
def uploaded_file(folder, filename):
    from flask import send_from_directory

    if folder == "products":
        return send_from_directory(app.config["PRODUCT_UPLOAD_DIR"], filename)
    if folder == "requests":
        return send_from_directory(app.config["REQUEST_UPLOAD_DIR"], filename)
    return "Arquivo não encontrado", 404


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
else:
    init_db()
