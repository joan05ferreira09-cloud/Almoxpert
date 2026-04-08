document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initCatalogSearch();
});

function initTabs() {
    const buttons = document.querySelectorAll('.tab-button');
    const contents = document.querySelectorAll('.tab-content');

    if (!buttons.length) return;

    buttons.forEach((button) => {
        button.addEventListener('click', () => {
            buttons.forEach((btn) => btn.classList.remove('active'));
            contents.forEach((content) => content.classList.remove('active'));
            button.classList.add('active');
            const target = document.getElementById(button.dataset.tabTarget);
            if (target) target.classList.add('active');
        });
    });
}

function initCatalogSearch() {
    const input = document.getElementById('catalogSearchInput');
    const resultsContainer = document.getElementById('catalogResults');
    const selectedProductBox = document.getElementById('selectedProductBox');
    const productIdField = document.getElementById('selectedProductId');
    const productNameField = document.getElementById('selectedProductName');
    const productCodeField = document.getElementById('selectedProductCode');

    if (!input || !resultsContainer) return;

    const form = input.closest('form');
    if (form) {
        form.addEventListener('submit', (event) => {
            if (!productNameField.value.trim()) {
                event.preventDefault();
                alert('Selecione um item do catálogo antes de enviar a solicitação.');
                input.focus();
            }
        });
    }

    let timeoutId = null;

    input.addEventListener('input', () => {
        const query = input.value.trim();

        productIdField.value = '';
        productNameField.value = '';
        productCodeField.value = '';
        selectedProductBox.innerHTML = '<div class="selected-product-placeholder">Nenhum item selecionado ainda.</div>';

        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            if (query.length < 2) {
                resultsContainer.className = 'catalog-results-grid empty-state-grid';
                resultsContainer.innerHTML = '<div class="empty-state">Digite pelo menos 2 letras para pesquisar no catálogo.</div>';
                return;
            }

            fetch(`/catalog-search?q=${encodeURIComponent(query)}`)
                .then((response) => response.json())
                .then((items) => {
                    if (!items.length) {
                        resultsContainer.className = 'catalog-results-grid empty-state-grid';
                        resultsContainer.innerHTML = '<div class="empty-state">Nenhum item encontrado com esse termo.</div>';
                        return;
                    }

                    resultsContainer.className = 'catalog-results-grid';
                    resultsContainer.innerHTML = items.map((item) => `
                        <article class="catalog-item" data-product='${JSON.stringify(item).replace(/'/g, '&#39;')}'>
                            <img src="${item.imagem_url}" alt="${escapeHtml(item.nome)}">
                            <div class="catalog-item-body">
                                <h4>${escapeHtml(item.nome)}</h4>
                                <p><strong>Código:</strong> ${escapeHtml(item.codigo)}</p>
                                <p><strong>Categoria:</strong> ${escapeHtml(item.categoria)}</p>
                                <p><strong>Local:</strong> ${escapeHtml(item.localizacao)}</p>
                                <p><strong>Estoque:</strong> ${item.estoque_atual} | <strong>Mínimo:</strong> ${item.estoque_minimo}</p>
                                <button type="button" class="catalog-select">Selecionar item</button>
                            </div>
                        </article>
                    `).join('');

                    resultsContainer.querySelectorAll('.catalog-item').forEach((card) => {
                        card.addEventListener('click', () => {
                            const data = JSON.parse(card.dataset.product.replace(/&#39;/g, "'"));
                            productIdField.value = data.id;
                            productNameField.value = data.nome;
                            productCodeField.value = data.codigo;
                            input.value = data.nome;
                            selectedProductBox.innerHTML = `
                                <div class="selected-product-card">
                                    <img src="${data.imagem_url}" alt="${escapeHtml(data.nome)}">
                                    <div>
                                        <h4>${escapeHtml(data.nome)}</h4>
                                        <p><strong>Código:</strong> ${escapeHtml(data.codigo)}</p>
                                        <p><strong>Categoria:</strong> ${escapeHtml(data.categoria)}</p>
                                        <p><strong>Local:</strong> ${escapeHtml(data.localizacao)}</p>
                                        <p><strong>Unidade:</strong> ${escapeHtml(data.unidade)}</p>
                                        <p><strong>Estoque atual:</strong> ${data.estoque_atual}</p>
                                    </div>
                                </div>
                            `;
                        });
                    });
                })
                .catch(() => {
                    resultsContainer.className = 'catalog-results-grid empty-state-grid';
                    resultsContainer.innerHTML = '<div class="empty-state">Não foi possível carregar o catálogo agora.</div>';
                });
        }, 250);
    });
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
