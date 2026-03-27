from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from functools import wraps
from typing import Any

from flask import Flask, Response, flash, g, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'almoxpert-chave-2026')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['DATABASE'] = os.path.join(BASE_DIR, 'almoxpert_empresarial.db')


def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop('db', None)
    if db is not None:
        db.close()


def now_str() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def init_db() -> None:
    db = sqlite3.connect(app.config['DATABASE'])
    with closing(db.cursor()) as cur:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS requester_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                sector TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                must_change_password INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS sectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                item_code TEXT UNIQUE,
                unit TEXT DEFAULT 'UN',
                keywords TEXT,
                image_url TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_number TEXT UNIQUE NOT NULL,
                requester_name TEXT NOT NULL,
                sector TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_code TEXT,
                quantity INTEGER NOT NULL,
                purpose TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDENTE',
                admin_note TEXT,
                approved_by TEXT,
                approved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        cur.execute("SELECT id FROM admins WHERE username='Joan'")
        if not cur.fetchone():
            cur.execute('INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)', ('Joan', generate_password_hash('Maeve0306@'), now_str()))
        for sector in ['Produção', 'Manutenção', 'Oficina', 'Almoxarifado', 'Administrativo']:
            cur.execute('INSERT OR IGNORE INTO sectors (name, created_at) VALUES (?, ?)', (sector, now_str()))
        defaults = [
            ('Disco flap', 'MV02558', 'UN', 'disco flap disco lixa acabamento metal', 'https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80'),
            ('Lâmpada industrial', 'LA001', 'UN', 'lampada luz industrial galpao', 'https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&w=600&q=80'),
            ('Luva de proteção', 'EPI100', 'PAR', 'luva epi proteção segurança', 'https://images.unsplash.com/photo-1584634731339-252c581abfc5?auto=format&fit=crop&w=600&q=80')
        ]
        for item in defaults:
            cur.execute('INSERT OR IGNORE INTO items (item_name, item_code, unit, keywords, image_url, created_at) VALUES (?, ?, ?, ?, ?, ?)', (*item, now_str()))
    db.commit(); db.close()


def generate_request_number() -> str:
    db = get_db()
    today = datetime.now().strftime('%Y%m%d')
    count = db.execute("SELECT COUNT(*) AS total FROM requests WHERE substr(created_at,1,10)=?", (datetime.now().strftime('%Y-%m-%d'),)).fetchone()['total']
    return f'REQ-{today}-{str(count+1).zfill(3)}'


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('admin_id'):
            flash('Faça login como administrador.', 'warning')
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapped


def requester_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('requester_user_id'):
            flash('Faça login para acessar a solicitação.', 'warning')
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapped


BASE_HTML = '''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} - Almoxpert</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
:root{--accent:#1f7aec;--bg:#eef3f8;--card:#fff;--text:#152536;--muted:#6d7a88;--border:#dbe5ef}
body{background:var(--bg);color:var(--text)} .navbar-brand{font-weight:900;font-size:1.35rem}
.card{border:0;border-radius:22px;box-shadow:0 12px 32px rgba(15,76,129,.08);background:var(--card)}
.section-title{font-weight:800}.small-muted{color:var(--muted);font-size:.94rem}
.btn{border-radius:14px;min-height:46px;font-weight:700}.btn-primary{background:var(--accent);border-color:var(--accent)}
.form-control,.form-select{border-radius:14px;min-height:48px;border:1px solid var(--border)} textarea.form-control{min-height:120px}
.menu-chip{border-radius:999px;padding:.5rem .85rem;background:#f1f6fb;color:#092b49;text-decoration:none;font-weight:600}
.menu-chip:hover{background:#e2edf8}.catalog-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
.catalog-card{border:1px solid var(--border);border-radius:18px;overflow:hidden;background:#fff;cursor:pointer;transition:.18s ease}.catalog-card:hover{transform:translateY(-2px);box-shadow:0 10px 22px rgba(15,76,129,.10)}
.catalog-card.active{border:2px solid var(--accent);box-shadow:0 0 0 4px rgba(31,122,236,.12)}.catalog-thumb{width:100%;height:150px;object-fit:cover;background:#eaf1f8}
.catalog-body{padding:14px}.catalog-code{font-size:.88rem;color:var(--muted)}.catalog-keywords{font-size:.82rem;color:#4d6073}.logo-top{max-height:110px;width:auto;display:block;margin:0 auto 18px auto}
.thumb-mini{width:54px;height:54px;object-fit:cover;border-radius:12px;background:#edf3f9}.helper-box{background:#f7fbff;border:1px solid #d8eaff;border-radius:18px;padding:18px}
.stat-card .value{font-size:2rem;font-weight:800;line-height:1}.stat-card .label{color:var(--muted);font-size:.92rem}
</style></head><body>
<nav class="navbar navbar-expand-lg bg-white border-bottom sticky-top"><div class="container py-2"><a class="navbar-brand" href="{{ url_for('login') }}">Almoxpert</a><div class="ms-auto d-flex flex-wrap gap-2 align-items-center">{% if session.get('requester_user_id') %}<a class="menu-chip" href="{{ url_for('request_portal') }}">Solicitação</a><a class="btn btn-outline-danger btn-sm" href="{{ url_for('logout') }}">Sair</a>{% elif session.get('admin_id') %}<a class="menu-chip" href="{{ url_for('dashboard') }}">Dashboard</a><a class="menu-chip" href="{{ url_for('cadastros_page') }}">Cadastros</a><a class="menu-chip" href="{{ url_for('reports_page') }}">Relatórios</a><a class="btn btn-outline-danger btn-sm" href="{{ url_for('logout') }}">Sair</a>{% endif %}</div></div></nav>
<div class="container py-4">{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">{{ message }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>{% endfor %}{% endif %}{% endwith %}{{ content|safe }}</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script></body></html>'''


def render_page(title: str, content: str) -> str:
    return render_template_string(BASE_HTML, title=title, content=content)


def logo_html() -> str:
    return f'<div style="text-align:center; margin-bottom:18px;"><img src="{url_for("static", filename="logo_almoxpert.png")}" alt="Almoxpert" style="max-height:110px; width:auto; display:inline-block;"></div>'


@app.route('/', methods=['GET', 'POST'])
def login() -> str:
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        access_type = request.form.get('access_type', 'requester')
        db = get_db()
        if access_type == 'admin':
            admin = db.execute('SELECT * FROM admins WHERE username = ?', (username,)).fetchone()
            if admin and check_password_hash(admin['password_hash'], password):
                session.clear(); session['admin_id'] = admin['id']; session['admin_username'] = admin['username']
                flash('Login administrativo realizado com sucesso.', 'success')
                return redirect(url_for('dashboard'))
        else:
            requester = db.execute('SELECT * FROM requester_users WHERE username = ? AND is_active = 1', (username,)).fetchone()
            if requester and check_password_hash(requester['password_hash'], password):
                session.clear(); session['requester_user_id'] = requester['id']; session['requester_username'] = requester['username']; session['requester_full_name'] = requester['full_name']; session['requester_sector'] = requester['sector'] or ''; session['must_change_password'] = requester['must_change_password']
                if requester['must_change_password'] == 1:
                    flash('Por segurança, altere sua senha no primeiro acesso.', 'warning')
                    return redirect(url_for('change_own_password'))
                flash('Login realizado com sucesso.', 'success')
                return redirect(url_for('request_portal'))
        flash('Usuário ou senha inválidos.', 'danger')
    content = f'''<div class="row justify-content-center"><div class="col-lg-5 col-md-7">{logo_html()}<div class="card p-4"><h3 class="section-title mb-3 text-center">Login</h3><form method="post" class="row g-3"><div class="col-12"><label class="form-label">Tipo de acesso</label><select name="access_type" class="form-select"><option value="requester" selected>Solicitante</option><option value="admin">Administrador</option></select></div><div class="col-12"><label class="form-label">Usuário</label><input type="text" name="username" class="form-control" required></div><div class="col-12"><label class="form-label">Senha</label><input type="password" name="password" class="form-control" required></div><div class="col-12 d-grid"><button type="submit" class="btn btn-primary">Entrar</button></div></form></div></div></div>'''
    return render_page('Login', content)


@app.route('/logout')
def logout() -> Response:
    session.clear(); flash('Sessão encerrada.', 'info'); return redirect(url_for('login'))


@app.route('/alterar-minha-senha', methods=['GET', 'POST'])
@requester_required
def change_own_password() -> str:
    db = get_db(); user = db.execute('SELECT * FROM requester_users WHERE id = ?', (session['requester_user_id'],)).fetchone()
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if len(new_password) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.', 'danger')
        elif new_password != confirm_password:
            flash('A confirmação da senha não confere.', 'danger')
        else:
            db.execute('UPDATE requester_users SET password_hash = ?, must_change_password = 0 WHERE id = ?', (generate_password_hash(new_password), session['requester_user_id']))
            db.commit(); session['must_change_password'] = 0; flash('Senha alterada com sucesso.', 'success'); return redirect(url_for('request_portal'))
    content = f'''<div class="row justify-content-center"><div class="col-lg-5">{logo_html()}<div class="card p-4"><h3 class="section-title mb-3 text-center">Alterar senha</h3><p class="small-muted text-center">Olá, {user['full_name']}. Defina sua nova senha.</p><form method="post" class="row g-3"><div class="col-12"><label class="form-label">Nova senha</label><input type="password" name="new_password" class="form-control" required></div><div class="col-12"><label class="form-label">Confirmar nova senha</label><input type="password" name="confirm_password" class="form-control" required></div><div class="col-12 d-grid"><button class="btn btn-primary">Salvar nova senha</button></div></form></div></div></div>'''
    return render_page('Alterar Senha', content)


@app.route('/solicitacao', methods=['GET', 'POST'])
@requester_required
def request_portal() -> str:
    if session.get('must_change_password') == 1:
        return redirect(url_for('change_own_password'))
    db = get_db(); sectors = get_sectors(); items = get_items(); requester_name_default = session.get('requester_full_name', ''); requester_sector_default = session.get('requester_sector', '')
    if request.method == 'POST':
        sector = request.form.get('sector', '').strip() or requester_sector_default
        item_name = request.form.get('item_name', '').strip(); item_code = request.form.get('item_code', '').strip(); quantity_str = request.form.get('quantity', '1').strip(); purpose = request.form.get('purpose', '').strip(); priority = request.form.get('priority', 'NORMAL').strip().upper()
        errors = []
        if not sector: errors.append('Informe o setor.')
        if not item_name: errors.append('Selecione um item do catálogo.')
        if not purpose: errors.append('Informe a finalidade.')
        try:
            quantity = int(quantity_str)
            if quantity <= 0: errors.append('A quantidade deve ser maior que zero.')
        except ValueError:
            quantity = 0; errors.append('Quantidade inválida.')
        if errors:
            for err in errors: flash(err, 'danger')
        else:
            ts = now_str(); req = generate_request_number()
            db.execute("INSERT INTO requests (request_number, requester_name, sector, item_name, item_code, quantity, purpose, priority, status, admin_note, approved_by, approved_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', '', '', '', ?, ?)", (req, requester_name_default, sector, item_name, item_code, quantity, purpose, priority, ts, ts))
            db.commit(); flash(f'Solicitação enviada com sucesso. Número: {req}', 'success'); return redirect(url_for('request_portal'))
    sector_options = ''.join([f'<option value="{row["name"]}">{row["name"]}</option>' for row in sectors])
    catalog_cards = []
    for row in items:
        image_url = row['image_url'] or 'https://via.placeholder.com/500x300.png?text=Sem+Imagem'; keywords = row['keywords'] or ''
        catalog_cards.append(f'''<div class="catalog-card" data-name="{row['item_name']}" data-code="{row['item_code'] or ''}" data-img="{image_url}" data-keywords="{keywords}"><img class="catalog-thumb" src="{image_url}" alt="{row['item_name']}"><div class="catalog-body"><div class="fw-bold">{row['item_name']}</div><div class="catalog-code">Código: {row['item_code'] or '-'}</div><div class="catalog-keywords mt-2">{keywords or 'Sem palavras-chave cadastradas'}</div></div></div>''')
    content = f'''<div class="text-center mb-4">{logo_html()}</div><div class="card p-4"><div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2"><h3 class="section-title mb-0">Nova solicitação</h3><span class="small-muted">Solicitante: {requester_name_default}</span></div><form method="post" class="row g-3"><div class="col-md-6"><label class="form-label">Solicitante</label><input type="text" value="{requester_name_default}" class="form-control" readonly></div><div class="col-md-6"><label class="form-label">Setor</label><input list="sector-list" name="sector" class="form-control" value="{requester_sector_default}" required><datalist id="sector-list">{sector_options}</datalist></div><div class="col-12"><label class="form-label">Buscar item no catálogo</label><input type="text" id="catalogSearch" class="form-control" placeholder="Ex.: disco flap, luva, lâmpada..."></div><div class="col-12"><div id="selectedPreview" class="helper-box d-none"><div class="row align-items-center g-3"><div class="col-auto"><img id="selectedPreviewImg" src="" class="thumb-mini" alt="Prévia do item"></div><div class="col"><div class="fw-bold" id="selectedPreviewName"></div><div class="small-muted" id="selectedPreviewCode"></div></div></div></div></div><div class="col-12"><div class="catalog-grid" id="catalogGrid">{''.join(catalog_cards)}</div></div><div class="col-md-6"><label class="form-label">Item selecionado</label><input type="text" id="item_name" name="item_name" class="form-control" readonly required></div><div class="col-md-6"><label class="form-label">Código do item</label><input type="text" id="item_code" name="item_code" class="form-control" readonly></div><div class="col-md-4"><label class="form-label">Quantidade</label><input type="number" name="quantity" min="1" value="1" class="form-control" required></div><div class="col-md-4"><label class="form-label">Prioridade</label><select name="priority" class="form-select"><option>BAIXA</option><option selected>NORMAL</option><option>ALTA</option><option>URGENTE</option></select></div><div class="col-md-12"><label class="form-label">Finalidade / Utilização</label><textarea name="purpose" class="form-control" rows="4" required></textarea></div><div class="col-12 d-grid"><button type="submit" class="btn btn-primary btn-lg">Enviar solicitação</button></div></form></div><script>const searchInput=document.getElementById('catalogSearch');const catalogCards=Array.from(document.querySelectorAll('.catalog-card'));const itemNameInput=document.getElementById('item_name');const itemCodeInput=document.getElementById('item_code');const selectedPreview=document.getElementById('selectedPreview');const selectedPreviewImg=document.getElementById('selectedPreviewImg');const selectedPreviewName=document.getElementById('selectedPreviewName');const selectedPreviewCode=document.getElementById('selectedPreviewCode');function selectCard(card){{catalogCards.forEach(c=>c.classList.remove('active'));card.classList.add('active');itemNameInput.value=card.dataset.name||'';itemCodeInput.value=card.dataset.code||'';selectedPreview.classList.remove('d-none');selectedPreviewImg.src=card.dataset.img||'';selectedPreviewName.textContent=card.dataset.name||'';selectedPreviewCode.textContent='Código: '+(card.dataset.code||'-');}}catalogCards.forEach(card=>{{card.addEventListener('click',()=>selectCard(card));}});searchInput?.addEventListener('input',function(){{const value=this.value.toLowerCase().trim();catalogCards.forEach(card=>{{const text=(card.dataset.name+' '+(card.dataset.code||'')+' '+(card.dataset.keywords||'')).toLowerCase();card.style.display=text.includes(value)?'':'none';}});}});</script>'''
    return render_page('Solicitação', content)


@app.route('/admin/dashboard')
@admin_required
def dashboard() -> str:
    db = get_db(); rows = db.execute('SELECT * FROM requests ORDER BY id DESC').fetchall()
    total = db.execute("SELECT COUNT(*) AS total FROM requests").fetchone()['total']
    pending = db.execute("SELECT COUNT(*) AS total FROM requests WHERE status='PENDENTE'").fetchone()['total']
    approved = db.execute("SELECT COUNT(*) AS total FROM requests WHERE status='APROVADA'").fetchone()['total']
    concluded = db.execute("SELECT COUNT(*) AS total FROM requests WHERE status='CONCLUIDA'").fetchone()['total']
    body = ''.join([f"<tr><td>{r['request_number']}</td><td>{r['requester_name']}</td><td>{r['sector']}</td><td>{r['item_name']}</td><td>{r['quantity']}</td><td>{r['status']}</td><td><a class='btn btn-sm btn-outline-primary' href='{url_for('request_detail', request_id=r['id'])}'>Abrir</a></td></tr>" for r in rows]) or "<tr><td colspan='7' class='text-center py-4'>Nenhuma solicitação encontrada.</td></tr>"
    content = f'''<div class="text-center mb-4">{logo_html()}</div><div class="row g-3 mb-4"><div class="col-md-3"><div class="card stat-card p-3"><div class="label">Total</div><div class="value">{total}</div></div></div><div class="col-md-3"><div class="card stat-card p-3"><div class="label">Pendentes</div><div class="value text-warning">{pending}</div></div></div><div class="col-md-3"><div class="card stat-card p-3"><div class="label">Aprovadas</div><div class="value text-success">{approved}</div></div></div><div class="col-md-3"><div class="card stat-card p-3"><div class="label">Concluídas</div><div class="value text-primary">{concluded}</div></div></div></div><div class="card p-4"><div class="d-flex justify-content-between align-items-center mb-3"><div><h3 class="section-title mb-0">Painel Administrativo</h3><div class="small-muted">Gerencie todas as solicitações</div></div><div class="d-flex gap-2"><a href="{url_for('cadastros_page')}" class="btn btn-outline-primary">Cadastros</a><a href="{url_for('export_csv')}" class="btn btn-success">Exportar CSV</a></div></div><div class="table-responsive"><table class="table table-hover align-middle"><thead class="table-light"><tr><th>Nº Solicitação</th><th>Solicitante</th><th>Setor</th><th>Item</th><th>Qtd</th><th>Status</th><th>Ações</th></tr></thead><tbody>{body}</tbody></table></div></div>'''
    return render_page('Dashboard', content)


@app.route('/admin/request/<int:request_id>', methods=['GET', 'POST'])
@admin_required
def request_detail(request_id: int) -> str:
    db = get_db(); record = db.execute('SELECT * FROM requests WHERE id = ?', (request_id,)).fetchone()
    if not record:
        flash('Solicitação não encontrada.', 'danger'); return redirect(url_for('dashboard'))
    if request.method == 'POST':
        action = request.form.get('action', '').strip().upper(); admin_note = request.form.get('admin_note', '').strip(); approved_by = session.get('admin_username', 'Joan'); new_status = None
        if action == 'APROVAR': new_status = 'APROVADA'
        elif action == 'RECUSAR': new_status = 'RECUSADA'
        elif action == 'CONCLUIR': new_status = 'CONCLUIDA'
        if new_status:
            db.execute('UPDATE requests SET status=?, admin_note=?, approved_by=?, approved_at=?, updated_at=? WHERE id=?', (new_status, admin_note, approved_by, now_str(), now_str(), request_id)); db.commit(); flash(f'Solicitação atualizada para {new_status}.', 'success'); return redirect(url_for('request_detail', request_id=request_id))
    content = f'''<div class="d-flex justify-content-between align-items-center mb-3"><div><h2 class="mb-1 section-title">Solicitação {record['request_number']}</h2><div class="small-muted">Criada em {record['created_at']} | Atualizada em {record['updated_at']}</div></div><a href="{url_for('dashboard')}" class="btn btn-outline-secondary">Voltar</a></div><div class="row g-4"><div class="col-lg-7"><div class="card p-4 h-100"><div class="row g-3"><div class="col-md-6"><strong>Solicitante:</strong><br>{record['requester_name']}</div><div class="col-md-6"><strong>Setor:</strong><br>{record['sector']}</div><div class="col-md-6"><strong>Item:</strong><br>{record['item_name']}</div><div class="col-md-6"><strong>Código:</strong><br>{record['item_code'] or '-'}</div><div class="col-md-4"><strong>Quantidade:</strong><br>{record['quantity']}</div><div class="col-md-4"><strong>Prioridade:</strong><br>{record['priority']}</div><div class="col-md-4"><strong>Status:</strong><br>{record['status']}</div><div class="col-md-12"><strong>Finalidade:</strong><br>{record['purpose']}</div></div></div></div><div class="col-lg-5"><div class="card p-4"><h4 class="section-title mb-3">Ação do administrador</h4><form method="post"><div class="mb-3"><label class="form-label">Observação do admin</label><textarea name="admin_note" class="form-control" rows="6">{record['admin_note'] or ''}</textarea></div><div class="d-grid gap-2"><button name="action" value="APROVAR" class="btn btn-success">Aprovar</button><button name="action" value="RECUSAR" class="btn btn-danger">Recusar</button><button name="action" value="CONCLUIR" class="btn btn-primary">Concluir</button></div></form></div></div></div>'''
    return render_page('Detalhe', content)


@app.route('/admin/requester/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_requester_user(user_id: int) -> str:
    db = get_db(); user = db.execute('SELECT * FROM requester_users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('Usuário solicitante não encontrado.', 'danger'); return redirect(url_for('cadastros_page', tab='usuarios'))
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip(); username = request.form.get('username', '').strip(); sector = request.form.get('sector', '').strip(); new_password = request.form.get('new_password', ''); is_active = 1 if request.form.get('is_active') == '1' else 0; must_change_password = 1 if request.form.get('must_change_password') == '1' else 0
        try:
            if new_password:
                db.execute('UPDATE requester_users SET full_name=?, username=?, password_hash=?, sector=?, is_active=?, must_change_password=? WHERE id=?', (full_name, username, generate_password_hash(new_password), sector, is_active, must_change_password, user_id))
            else:
                db.execute('UPDATE requester_users SET full_name=?, username=?, sector=?, is_active=?, must_change_password=? WHERE id=?', (full_name, username, sector, is_active, must_change_password, user_id))
            db.commit(); flash('Usuário atualizado com sucesso.', 'success'); return redirect(url_for('cadastros_page', tab='usuarios'))
        except sqlite3.IntegrityError:
            flash('Esse usuário já existe. Use outro login.', 'danger')
    sectors = get_sectors(); sector_options = ''.join([f'<option value="{r["name"]}" {"selected" if r["name"] == (user["sector"] or "") else ""}>{r["name"]}</option>' for r in sectors])
    content = f'''<div class="row justify-content-center"><div class="col-lg-7"><div class="card p-4"><div class="d-flex justify-content-between align-items-center mb-3"><div><h2 class="section-title mb-1">Editar usuário</h2><div class="small-muted">Atualize os dados e controle o acesso.</div></div><a href="{url_for('cadastros_page', tab='usuarios')}" class="btn btn-outline-secondary">Voltar</a></div><form method="post" class="row g-3"><div class="col-md-8"><label class="form-label">Nome completo</label><input type="text" name="full_name" value="{user['full_name']}" class="form-control" required></div><div class="col-md-4"><label class="form-label">Usuário</label><input type="text" name="username" value="{user['username']}" class="form-control" required></div><div class="col-md-6"><label class="form-label">Setor</label><select name="sector" class="form-select"><option value="">Selecione</option>{sector_options}</select></div><div class="col-md-6"><label class="form-label">Nova senha</label><input type="password" name="new_password" class="form-control" placeholder="Deixe em branco para manter"></div><div class="col-md-6"><label class="form-label">Status</label><select name="is_active" class="form-select"><option value="1" {"selected" if user['is_active'] == 1 else ""}>Ativo</option><option value="0" {"selected" if user['is_active'] == 0 else ""}>Inativo</option></select></div><div class="col-md-6"><label class="form-label">Exigir troca de senha</label><select name="must_change_password" class="form-select"><option value="1" {"selected" if user['must_change_password'] == 1 else ""}>Sim</option><option value="0" {"selected" if user['must_change_password'] == 0 else ""}>Não</option></select></div><div class="col-12 d-grid gap-2 d-md-flex justify-content-md-end"><a href="{url_for('cadastros_page', tab='usuarios')}" class="btn btn-outline-secondary">Cancelar</a><button class="btn btn-primary">Salvar alterações</button></div></form></div></div></div>'''
    return render_page('Editar Usuário', content)


@app.route('/admin/cadastros', methods=['GET', 'POST'])
@admin_required
def cadastros_page() -> str:
    db = get_db(); tab = request.args.get('tab', 'usuarios')
    if request.method == 'POST':
        form_type = request.form.get('form_type', '')
        if form_type == 'requester_user':
            full_name = request.form.get('full_name', '').strip(); username = request.form.get('username', '').strip(); password = request.form.get('password', ''); sector = request.form.get('sector', '').strip()
            try:
                db.execute('INSERT INTO requester_users (full_name, username, password_hash, sector, is_active, must_change_password, created_at) VALUES (?, ?, ?, ?, 1, 1, ?)', (full_name, username, generate_password_hash(password), sector, now_str())); db.commit(); flash('Usuário cadastrado com sucesso.', 'success'); return redirect(url_for('cadastros_page', tab='usuarios'))
            except sqlite3.IntegrityError:
                flash('Usuário já existe. Use outro login.', 'danger')
        elif form_type == 'sector':
            name = request.form.get('name', '').strip(); db.execute('INSERT OR IGNORE INTO sectors (name, created_at) VALUES (?, ?)', (name, now_str())); db.commit(); flash('Setor salvo com sucesso.', 'success'); return redirect(url_for('cadastros_page', tab='setores'))
        elif form_type == 'item':
            item_name = request.form.get('item_name', '').strip(); item_code = request.form.get('item_code', '').strip(); unit = request.form.get('unit', 'UN').strip().upper() or 'UN'; keywords = request.form.get('keywords', '').strip(); image_url = request.form.get('image_url', '').strip()
            try:
                db.execute('INSERT INTO items (item_name, item_code, unit, keywords, image_url, created_at) VALUES (?, ?, ?, ?, ?, ?)', (item_name, item_code or None, unit, keywords, image_url or None, now_str())); db.commit(); flash('Item cadastrado com sucesso.', 'success'); return redirect(url_for('cadastros_page', tab='itens'))
            except sqlite3.IntegrityError:
                flash('Código do item já existe. Use outro código.', 'danger')
    items = db.execute('SELECT * FROM items ORDER BY item_name ASC').fetchall(); sectors = db.execute('SELECT * FROM sectors ORDER BY name ASC').fetchall(); users = db.execute('SELECT * FROM requester_users ORDER BY full_name ASC').fetchall()
    sector_options_admin = ''.join([f'<option value="{r["name"]}">{r["name"]}</option>' for r in sectors])
    requester_rows = ''.join([f"<tr><td>{r['full_name']}</td><td>{r['username']}</td><td>{r['sector'] or '-'}</td><td>{'Ativo' if r['is_active'] else 'Inativo'}</td><td>{'Sim' if r['must_change_password'] else 'Não'}</td><td>{r['created_at']}</td><td><a href='{url_for('edit_requester_user', user_id=r['id'])}' class='btn btn-sm btn-outline-primary'>Editar</a></td></tr>" for r in users]) or "<tr><td colspan='7'>Nenhum usuário cadastrado.</td></tr>"
    sector_rows = ''.join([f"<tr><td>{r['name']}</td><td>{r['created_at']}</td></tr>" for r in sectors]) or "<tr><td colspan='2'>Nenhum setor cadastrado.</td></tr>"
    item_rows = ''.join([f"<tr><td>{r['item_name']}</td><td>{r['item_code'] or '-'}</td><td>{r['unit']}</td><td>{r['keywords'] or '-'}</td></tr>" for r in items]) or "<tr><td colspan='4'>Nenhum item cadastrado.</td></tr>"
    if tab == 'usuarios':
        left_panel = f'''<h3 class="section-title">Cadastro de usuários</h3><form method="post" class="row g-3 mt-1"><input type="hidden" name="form_type" value="requester_user"><div class="col-12"><label class="form-label">Nome completo</label><input type="text" name="full_name" class="form-control" required></div><div class="col-12"><label class="form-label">Usuário</label><input type="text" name="username" class="form-control" required></div><div class="col-12"><label class="form-label">Senha inicial</label><input type="password" name="password" class="form-control" required></div><div class="col-12"><label class="form-label">Setor</label><input list="sector-list-admin" name="sector" class="form-control"></div><datalist id="sector-list-admin">{sector_options_admin}</datalist><div class="col-12 d-grid"><button class="btn btn-primary">Salvar usuário</button></div></form>'''
        right_panel = f'''<h3 class="section-title">Usuários cadastrados</h3><div class="table-responsive mt-3"><table class="table table-hover align-middle"><thead class="table-light"><tr><th>Nome</th><th>Usuário</th><th>Setor</th><th>Status</th><th>Troca senha</th><th>Criado em</th><th>Ações</th></tr></thead><tbody>{requester_rows}</tbody></table></div>'''
    elif tab == 'setores':
        left_panel = '''<h3 class="section-title">Cadastro de setores</h3><form method="post" class="row g-3 mt-1"><input type="hidden" name="form_type" value="sector"><div class="col-12"><label class="form-label">Nome do setor</label><input type="text" name="name" class="form-control" required></div><div class="col-12 d-grid"><button class="btn btn-primary">Salvar setor</button></div></form>'''
        right_panel = f'''<h3 class="section-title">Setores cadastrados</h3><div class="table-responsive mt-3"><table class="table table-hover align-middle"><thead class="table-light"><tr><th>Setor</th><th>Criado em</th></tr></thead><tbody>{sector_rows}</tbody></table></div>'''
    else:
        left_panel = '''<h3 class="section-title">Cadastro de itens</h3><form method="post" class="row g-3 mt-1"><input type="hidden" name="form_type" value="item"><div class="col-12"><label class="form-label">Nome do item</label><input type="text" name="item_name" class="form-control" required></div><div class="col-12"><label class="form-label">Código</label><input type="text" name="item_code" class="form-control"></div><div class="col-12"><label class="form-label">Unidade</label><input type="text" name="unit" class="form-control" value="UN"></div><div class="col-12"><label class="form-label">Palavras-chave</label><input type="text" name="keywords" class="form-control"></div><div class="col-12"><label class="form-label">Imagem por URL</label><input type="text" name="image_url" class="form-control"></div><div class="col-12 d-grid"><button class="btn btn-primary">Salvar item</button></div></form>'''
        right_panel = f'''<h3 class="section-title">Itens cadastrados</h3><div class="table-responsive mt-3"><table class="table table-hover align-middle"><thead class="table-light"><tr><th>Item</th><th>Código</th><th>Unidade</th><th>Palavras-chave</th></tr></thead><tbody>{item_rows}</tbody></table></div>'''
    content = f'''<div class="text-center mb-4">{logo_html()}</div><div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2"><div><h2 class="section-title mb-1">Fazer cadastros</h2><div class="small-muted">Apenas o administrador cria usuários, setores e itens.</div></div><a href="{url_for('dashboard')}" class="btn btn-outline-secondary">Voltar ao dashboard</a></div><div class="card p-4"><ul class="nav nav-tabs mb-4"><li class="nav-item"><a class="nav-link {'active' if tab == 'usuarios' else ''}" href="{url_for('cadastros_page', tab='usuarios')}">Usuários</a></li><li class="nav-item"><a class="nav-link {'active' if tab == 'setores' else ''}" href="{url_for('cadastros_page', tab='setores')}">Setores</a></li><li class="nav-item"><a class="nav-link {'active' if tab == 'itens' else ''}" href="{url_for('cadastros_page', tab='itens')}">Itens</a></li></ul><div class="row g-4"><div class="col-lg-4"><div class="card p-4">{left_panel}</div></div><div class="col-lg-8"><div class="card p-4">{right_panel}</div></div></div></div>'''
    return render_page('Cadastros', content)


@app.route('/admin/reports')
@admin_required
def reports_page() -> str:
    db = get_db(); by_sector = db.execute("SELECT sector, COUNT(*) AS total FROM requests GROUP BY sector ORDER BY total DESC, sector ASC").fetchall(); by_item = db.execute("SELECT item_name, COUNT(*) AS total FROM requests GROUP BY item_name ORDER BY total DESC, item_name ASC LIMIT 10").fetchall()
    sector_rows = ''.join([f"<tr><td>{r['sector']}</td><td>{r['total']}</td></tr>" for r in by_sector]) or "<tr><td colspan='2'>Sem dados</td></tr>"
    item_rows = ''.join([f"<tr><td>{r['item_name']}</td><td>{r['total']}</td></tr>" for r in by_item]) or "<tr><td colspan='2'>Sem dados</td></tr>"
    content = f'''<div class="text-center mb-4">{logo_html()}</div><div class="row g-4"><div class="col-lg-6"><div class="card p-4 h-100"><h3 class="section-title">Solicitações por setor</h3><div class="table-responsive mt-3"><table class="table table-hover align-middle"><thead class="table-light"><tr><th>Setor</th><th>Total</th></tr></thead><tbody>{sector_rows}</tbody></table></div></div></div><div class="col-lg-6"><div class="card p-4 h-100"><h3 class="section-title">Itens mais solicitados</h3><div class="table-responsive mt-3"><table class="table table-hover align-middle"><thead class="table-light"><tr><th>Item</th><th>Total</th></tr></thead><tbody>{item_rows}</tbody></table></div></div></div></div>'''
    return render_page('Relatórios', content)


@app.route('/admin/export/csv')
@admin_required
def export_csv() -> Response:
    db = get_db(); rows = db.execute("SELECT request_number, requester_name, sector, item_name, item_code, quantity, purpose, priority, status, admin_note, approved_by, approved_at, created_at, updated_at FROM requests ORDER BY id DESC").fetchall()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['Numero Solicitação', 'Solicitante', 'Setor', 'Item', 'Codigo do Item', 'Quantidade', 'Finalidade', 'Prioridade', 'Status', 'Observacao Admin', 'Tratado por', 'Data da ação', 'Criado em', 'Atualizado em'])
    for row in rows:
        writer.writerow([row['request_number'], row['requester_name'], row['sector'], row['item_name'], row['item_code'], row['quantity'], row['purpose'], row['priority'], row['status'], row['admin_note'], row['approved_by'], row['approved_at'], row['created_at'], row['updated_at']])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=almoxpert_solicitacoes.csv'})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
