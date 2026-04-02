document.addEventListener('DOMContentLoaded', () => {
    carregarSolicitacoes();
});

function carregarSolicitacoes() {
    fetch('/minhas-solicitacoes')
        .then(res => res.json())
        .then(data => {
            const tabela = document.getElementById('myRequests');

            if (!data.length) {
                tabela.innerHTML = `<tr><td colspan="5">Nenhuma solicitação</td></tr>`;
                return;
            }

            tabela.innerHTML = data.map(item => `
                <tr>
                    <td>#${item.id}</td>
                    <td>${item.item}</td>
                    <td>${item.quantidade}</td>
                    <td>${traduzirStatus(item.status)}</td>
                    <td>${item.retorno}</td>
                </tr>
            `).join('');
        });
}

function traduzirStatus(status) {
    const map = {
        EM_ANALISE: "Em análise",
        FAVOR_RETIRAR: "Favor retirar",
        EM_FASE_COMPRA: "Em fase de compra",
        NEGADO: "Negado",
        CONCLUIDO: "Concluído"
    };
    return map[status] || status;
}
