# Almoxpert Empresarial

Versão empresarial do Almoxpert em Python com Flask.

## O que esta versão faz

- formulário público sem login
- protocolo automático para cada requisição
- consulta de status por protocolo
- painel administrativo com login
- aprovação, recusa ou retorno para pendente
- parecer administrativo em cada solicitação
- dashboard com indicadores
- cadastro de setores
- cadastro e edição de itens
- alerta de itens abaixo do estoque mínimo
- exportação em CSV e XLSX
- banco SQLite criado automaticamente
- logo do Almoxpert integrado

## Login inicial

- usuário: `admin`
- senha: `123456`

## Como rodar

```bash
pip install -r requirements.txt
python app.py
```

Depois abra no navegador:

```text
http://127.0.0.1:5000
```

## Estrutura do projeto

```text
almoxpert_empresarial/
├── app.py
├── requirements.txt
├── README.md
├── static/
│   ├── logo.png
│   └── css/
│       └── style.css
└── templates/
    ├── base.html
    ├── index.html
    ├── nova_requisicao.html
    ├── acompanhar_busca.html
    ├── acompanhar.html
    ├── admin_login.html
    ├── admin_dashboard.html
    ├── admin_requisicao.html
    ├── admin_setores.html
    └── admin_itens.html
```

## Observações

- Na primeira execução o sistema cria automaticamente:
  - banco de dados
  - usuário administrador
  - setores de exemplo
  - itens de exemplo
- Para publicar na internet, você pode subir esse projeto em Render, Railway ou PythonAnywhere.
- Antes de colocar em produção, altere a senha do admin no banco ou no código.
