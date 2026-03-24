from __future__ import annotations

import csv
import io
import os
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from openpyxl import Workbook
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "almoxpert_empresarial.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "almoxpert-chave-empresarial-altere-isto")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

STATUS_PENDENTE = "Pendente"
STATUS_APROVADA = "Aprovada"
STATUS_RECUSADA = "Recusada"
STATUS_VALIDOS = {STATUS_PENDENTE, STATUS_APROVADA, STATUS_RECUSADA}


class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nome_exibicao = db.Column(db.String(120), nullable=False, default="Administrador")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Setor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    unidade = db.Column(db.String(30), default="UN")
    estoque_atual = db.Column(db.Float, default=0)
    estoque_minimo = db.Column(db.Float, default=0)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Requisicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    protocolo = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nome_solicitante = db.Column(db.String(120), nullable=False)
    setor = db.Column(db.String(120), nullable=False)
    item_solicitado = db.Column(db.String(200), nullable=False)
    codigo_item = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.String(50), nullable=False)
    finalidade = db.Column(db.String(255), nullable=False)
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(30), default=STATUS_PENDENTE, nullable=False)
    parecer_admin = db.Column(db.Text)
    processado_por = db.Column(db.String(120))
    processado_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@app.context_processor
def inject_now():
    return {"agora": datetime.now(), "status_pendente": STATUS_PENDENTE, "status_aprovada": STATUS_APROVADA, "status_recusada": STATUS_RECUSADA}


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Faça login para acessar o painel administrativo.", "warning")
            return redirect(url_for("admin_login"))
        return view_func(*args, **kwargs)

    return wrapper


def gerar_protocolo() -> str:
    while True:
        protocolo = f"AXP-{datetime.now().strftime('%y%m')}-{secrets.randbelow(9999):04d}"
        if not Requisicao.query.filter_by(protocolo=protocolo).first():
            return protocolo


def to_float(valor: str | None) -> float:
    if not valor:
        return 0.0
    valor = valor.replace(".", "").replace(",", ".") if "," in valor else valor
    try:
        return float(valor)
    except ValueError:
        return 0.0


def resumo_status() -> dict[str, int]:
    return {
        "total": Requisicao.query.count(),
        "pendentes": Requisicao.query.filter_by(status=STATUS_PENDENTE).count(),
        "aprovadas": Requisicao.query.filter_by(status=STATUS_APROVADA).count(),
        "recusadas": Requisicao.query.filter_by(status=STATUS_RECUSADA).count(),
    }


def dados_grafico() -> list[dict[str, str | int]]:
    stats = resumo_status()
    itens = [
        {"label": "Pendentes", "value": stats["pendentes"], "class": "bar-pending"},
        {"label": "Aprovadas", "value": stats["aprovadas"], "class": "bar-approved"},
        {"label": "Recusadas", "value": stats["recusadas"], "class": "bar-rejected"},
    ]
    maior = max([1] + [int(x["value"]) for x in itens])
    for item in itens:
        item["height"] = max(12, round((int(item["value"]) / maior) * 180)) if int(item["value"]) > 0 else 12
    return itens


@app.route("/")
def index():
    setores = Setor.query.filter_by(ativo=True).order_by(Setor.nome.asc()).all()
    itens = Item.query.filter_by(ativo=True).order_by(Item.nome.asc()).all()
    ultimas = Requisicao.query.order_by(Requisicao.criado_em.desc()).limit(5).all()
    return render_template("index.html", setores=setores, itens=itens, ultimas=ultimas)


@app.route("/nova-requisicao", methods=["GET", "POST"])
def nova_requisicao():
    setores = Setor.query.filter_by(ativo=True).order_by(Setor.nome.asc()).all()
    itens = Item.query.filter_by(ativo=True).order_by(Item.nome.asc()).all()

    if request.method == "POST":
        nome_solicitante = request.form.get("nome_solicitante", "").strip()
        setor = request.form.get("setor", "").strip()
        item_solicitado = request.form.get("item_solicitado", "").strip()
        codigo_item = request.form.get("codigo_item", "").strip()
        quantidade = request.form.get("quantidade", "").strip()
        finalidade = request.form.get("finalidade", "").strip()
        observacoes = request.form.get("observacoes", "").strip()

        if not all([nome_solicitante, setor, item_solicitado, codigo_item, quantidade, finalidade]):
            flash("Preencha todos os campos obrigatórios.", "danger")
            return render_template("nova_requisicao.html", setores=setores, itens=itens)

        req = Requisicao(
            protocolo=gerar_protocolo(),
            nome_solicitante=nome_solicitante,
            setor=setor,
            item_solicitado=item_solicitado,
            codigo_item=codigo_item,
            quantidade=quantidade,
            finalidade=finalidade,
            observacoes=observacoes,
        )
        db.session.add(req)
        db.session.commit()
        flash(f"Requisição enviada com sucesso. Protocolo: {req.protocolo}", "success")
        return redirect(url_for("acompanhar_requisicao", protocolo=req.protocolo))

    return render_template("nova_requisicao.html", setores=setores, itens=itens)


@app.route("/acompanhar", methods=["GET", "POST"])
def acompanhar_busca():
    if request.method == "POST":
        protocolo = request.form.get("protocolo", "").strip().upper()
        if protocolo:
            return redirect(url_for("acompanhar_requisicao", protocolo=protocolo))
        flash("Digite o protocolo para consultar a requisição.", "warning")
    return render_template("acompanhar_busca.html")


@app.route("/acompanhar/<protocolo>")
def acompanhar_requisicao(protocolo: str):
    requisicao = Requisicao.query.filter_by(protocolo=protocolo).first_or_404()
    return render_template("acompanhar.html", requisicao=requisicao)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session["admin_id"] = admin.id
            session["admin_username"] = admin.username
            session["admin_nome"] = admin.nome_exibicao
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    termo = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    setor = request.args.get("setor", "").strip()

    query = Requisicao.query
    if termo:
        like = f"%{termo}%"
        query = query.filter(
            db.or_(
                Requisicao.protocolo.ilike(like),
                Requisicao.nome_solicitante.ilike(like),
                Requisicao.setor.ilike(like),
                Requisicao.item_solicitado.ilike(like),
                Requisicao.codigo_item.ilike(like),
                Requisicao.finalidade.ilike(like),
            )
        )
    if status in STATUS_VALIDOS:
        query = query.filter_by(status=status)
    if setor:
        query = query.filter(Requisicao.setor == setor)

    requisicoes = query.order_by(Requisicao.criado_em.desc()).all()
    setores = [s.nome for s in Setor.query.order_by(Setor.nome.asc()).all()]
    itens_abaixo_minimo = Item.query.filter(Item.estoque_atual < Item.estoque_minimo).order_by(Item.nome.asc()).all()

    return render_template(
        "admin_dashboard.html",
        requisicoes=requisicoes,
        termo=termo,
        status=status,
        setor=setor,
        setores=setores,
        stats=resumo_status(),
        barras=dados_grafico(),
        itens_abaixo_minimo=itens_abaixo_minimo,
    )


@app.route("/admin/requisicao/<int:req_id>")
@admin_required
def admin_requisicao(req_id: int):
    requisicao = Requisicao.query.get_or_404(req_id)
    return render_template("admin_requisicao.html", requisicao=requisicao)


@app.post("/admin/requisicao/<int:req_id>/status")
@admin_required
def atualizar_status(req_id: int):
    requisicao = Requisicao.query.get_or_404(req_id)
    novo_status = request.form.get("status", "").strip()
    parecer_admin = request.form.get("parecer_admin", "").strip()

    if novo_status not in STATUS_VALIDOS:
        flash("Status inválido.", "danger")
        return redirect(url_for("admin_requisicao", req_id=req_id))

    requisicao.status = novo_status
    requisicao.parecer_admin = parecer_admin
    requisicao.processado_por = session.get("admin_nome") or session.get("admin_username")
    requisicao.processado_em = datetime.utcnow()
    db.session.commit()
    flash(f"Requisição {requisicao.protocolo} atualizada para {novo_status}.", "success")
    return redirect(url_for("admin_requisicao", req_id=req_id))


@app.post("/admin/requisicao/<int:req_id>/excluir")
@admin_required
def excluir_requisicao(req_id: int):
    requisicao = Requisicao.query.get_or_404(req_id)
    db.session.delete(requisicao)
    db.session.commit()
    flash("Requisição excluída com sucesso.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/setores", methods=["GET", "POST"])
@admin_required
def admin_setores():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if not nome:
            flash("Informe o nome do setor.", "danger")
            return redirect(url_for("admin_setores"))
        if Setor.query.filter(db.func.lower(Setor.nome) == nome.lower()).first():
            flash("Este setor já existe.", "warning")
            return redirect(url_for("admin_setores"))
        db.session.add(Setor(nome=nome, ativo=True))
        db.session.commit()
        flash("Setor cadastrado com sucesso.", "success")
        return redirect(url_for("admin_setores"))

    setores = Setor.query.order_by(Setor.nome.asc()).all()
    return render_template("admin_setores.html", setores=setores)


@app.post("/admin/setores/<int:setor_id>/toggle")
@admin_required
def toggle_setor(setor_id: int):
    setor = Setor.query.get_or_404(setor_id)
    setor.ativo = not setor.ativo
    db.session.commit()
    flash("Status do setor atualizado.", "info")
    return redirect(url_for("admin_setores"))


@app.route("/admin/itens", methods=["GET", "POST"])
@admin_required
def admin_itens():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip().upper()
        nome = request.form.get("nome", "").strip()
        unidade = request.form.get("unidade", "UN").strip().upper() or "UN"
        estoque_atual = to_float(request.form.get("estoque_atual", "0"))
        estoque_minimo = to_float(request.form.get("estoque_minimo", "0"))

        if not codigo or not nome:
            flash("Código e nome do item são obrigatórios.", "danger")
            return redirect(url_for("admin_itens"))
        if Item.query.filter_by(codigo=codigo).first():
            flash("Já existe um item com esse código.", "warning")
            return redirect(url_for("admin_itens"))

        item = Item(
            codigo=codigo,
            nome=nome,
            unidade=unidade,
            estoque_atual=estoque_atual,
            estoque_minimo=estoque_minimo,
            ativo=True,
        )
        db.session.add(item)
        db.session.commit()
        flash("Item cadastrado com sucesso.", "success")
        return redirect(url_for("admin_itens"))

    itens = Item.query.order_by(Item.nome.asc()).all()
    return render_template("admin_itens.html", itens=itens)


@app.post("/admin/itens/<int:item_id>/atualizar")
@admin_required
def atualizar_item(item_id: int):
    item = Item.query.get_or_404(item_id)
    item.nome = request.form.get("nome", item.nome).strip() or item.nome
    item.unidade = request.form.get("unidade", item.unidade).strip().upper() or item.unidade
    item.estoque_atual = to_float(request.form.get("estoque_atual", str(item.estoque_atual)))
    item.estoque_minimo = to_float(request.form.get("estoque_minimo", str(item.estoque_minimo)))
    item.ativo = request.form.get("ativo") == "on"
    db.session.commit()
    flash("Item atualizado com sucesso.", "success")
    return redirect(url_for("admin_itens"))


@app.route("/admin/exportar/csv")
@admin_required
def exportar_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID",
        "Protocolo",
        "Data",
        "Solicitante",
        "Setor",
        "Item",
        "Código",
        "Quantidade",
        "Finalidade",
        "Observações",
        "Status",
        "Parecer do Admin",
        "Processado por",
        "Processado em",
    ])

    for r in Requisicao.query.order_by(Requisicao.criado_em.desc()).all():
        writer.writerow([
            r.id,
            r.protocolo,
            r.criado_em.strftime("%d/%m/%Y %H:%M"),
            r.nome_solicitante,
            r.setor,
            r.item_solicitado,
            r.codigo_item,
            r.quantidade,
            r.finalidade,
            r.observacoes or "",
            r.status,
            r.parecer_admin or "",
            r.processado_por or "",
            r.processado_em.strftime("%d/%m/%Y %H:%M") if r.processado_em else "",
        ])

    mem = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    mem.seek(0)
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="almoxpert_requisicoes.csv")


@app.route("/admin/exportar/xlsx")
@admin_required
def exportar_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "Requisições"
    ws.append([
        "ID", "Protocolo", "Data", "Solicitante", "Setor", "Item", "Código", "Quantidade",
        "Finalidade", "Observações", "Status", "Parecer do Admin", "Processado por", "Processado em"
    ])

    for r in Requisicao.query.order_by(Requisicao.criado_em.desc()).all():
        ws.append([
            r.id,
            r.protocolo,
            r.criado_em.strftime("%d/%m/%Y %H:%M"),
            r.nome_solicitante,
            r.setor,
            r.item_solicitado,
            r.codigo_item,
            r.quantidade,
            r.finalidade,
            r.observacoes or "",
            r.status,
            r.parecer_admin or "",
            r.processado_por or "",
            r.processado_em.strftime("%d/%m/%Y %H:%M") if r.processado_em else "",
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    mem = io.BytesIO()
    wb.save(mem)
    mem.seek(0)
    return send_file(
        mem,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="almoxpert_requisicoes.xlsx",
    )


@app.cli.command("init-db")
def init_db_command():
    inicializar_banco()
    print("Banco de dados inicializado.")



def popular_dados_iniciais() -> None:
    if not Setor.query.first():
        for nome in ["Produção", "Manutenção", "Compras", "Qualidade", "Expedição"]:
            db.session.add(Setor(nome=nome, ativo=True))

    if not Item.query.first():
        exemplos = [
            ("ALM-0001", "Luva de proteção", "PAR", 120, 40),
            ("ALM-0002", "Abraçadeira nylon", "UN", 600, 150),
            ("ALM-0003", "Fita isolante", "UN", 80, 20),
            ("ALM-0004", "Parafuso sextavado", "UN", 1000, 300),
        ]
        for codigo, nome, unidade, atual, minimo in exemplos:
            db.session.add(Item(codigo=codigo, nome=nome, unidade=unidade, estoque_atual=atual, estoque_minimo=minimo, ativo=True))

    if not Admin.query.filter_by(username="admin").first():
        db.session.add(
            Admin(
                username="admin",
                nome_exibicao="Administrador Almoxpert",
                password_hash=generate_password_hash("123456"),
            )
        )
    db.session.commit()



def inicializar_banco() -> None:
    db.create_all()
    popular_dados_iniciais()


with app.app_context():
    inicializar_banco()


if __name__ == "__main__":
    app.run(debug=True)
