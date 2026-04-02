document.addEventListener('DOMContentLoaded', () => {
    carregarSolicitacoes();
});

function carregarSolicitacoes() {
    fetch('/minhas-solicitacoes')
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('myRequests');

            if (!data.length) {
                tbody.innerHTML = `<tr><td colspan="5">Nenhuma solicitação</td></tr>`;
                return;
            }

            tbody.innerHTML = data.map(r => `
                <tr>
                    <td>#${r.id}</td>
                    <td>${r.item}</td>
                    <td>${r.quantidade}</td>
                    <td>${traduzirStatus(r.status)}</td>
                    <td>${r.retorno}</td>
                </tr>
            `).join('');
        });
}

function traduzirStatus(status) {
    const mapa = {
        EM_ANALISE: "Em análise",
        FAVOR_RETIRAR: "Favor retirar no almoxarifado",
        EM_FASE_COMPRA: "Em fase de compra",
        NEGADO: "Negado",
        CONCLUIDO: "Concluído"
    };
    return mapa[status] || status;
}
