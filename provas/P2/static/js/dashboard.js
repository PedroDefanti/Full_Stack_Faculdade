(function () {
    'use strict';

    function ler(id) {
        const el = document.getElementById(id);
        return el ? JSON.parse(el.textContent) : null;
    }

    function desenhar(canvasId, tipo, labels, valores, rotulo) {
        const el = document.getElementById(canvasId);
        if (!el || !labels || !valores) { return; }
        const circular = tipo === 'doughnut';
        new Chart(el, {
            type: tipo,
            data: {
                labels: labels,
                datasets: [{
                    label: rotulo,
                    data: valores,
                    backgroundColor: circular
                        ? ['#10b981', '#f59e0b', '#ef4444']
                        : (tipo === 'line' ? 'rgba(79,70,229,.15)' : '#4f46e5'),
                    borderColor: '#4f46e5',
                    borderWidth: tipo === 'line' ? 2 : 0,
                    fill: tipo === 'line',
                    tension: 0.3,
                    borderRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: circular } },
                scales: circular ? {} : { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    }

    // série mensal no formato do slide: [{mes: "08/2026", total: 22}]
    const meses = ler('dados-mes') || [];
    if (meses.length) {
        desenhar('gMeses', 'bar', meses.map(d => d.mes), meses.map(d => d.total), 'Empréstimos');
    }

    const G = ler('graficos') || {};
    const mapa = [
        ['gStatus', 'doughnut', G.status, 'Exemplares'],
        ['gLogins', 'line', G.logins, 'Logins'],
        ['gLoginsOrgs', 'bar', G.logins_orgs, 'Logins'],
        ['gNovasOrgs', 'bar', G.novas_orgs, 'Organizações'],
    ];
    mapa.forEach(function (g) {
        if (g[2]) { desenhar(g[0], g[1], g[2].labels, g[2].valores, g[3]); }
    });
})();