const startForm = document.querySelector('#simulation-start-form');
const startSection = document.querySelector('#start-section');
const tradingPanel = document.querySelector('#trading-panel');
const startMessage = document.querySelector('#start-message');
const actionMessage = document.querySelector('#action-message');
const newSimulationButton = document.querySelector('#new-simulation-button');
const actionButtons = document.querySelectorAll('[data-action]');
const tradeSharesInput = document.querySelector('#trade-shares');
let priceChart = null;

function csrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

async function postJson(url, payload) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Wystapil blad.');
    }
    return data;
}

function formPayload(form) {
    const data = new FormData(form);
    return Object.fromEntries(data.entries());
}

function setText(selector, value) {
    document.querySelector(selector).textContent = value;
}

function money(value) {
    return `${Number(value).toFixed(2)} USD`;
}

function renderState(state) {
    const day = state.current_day;
    const portfolio = state.portfolio;
    const prediction = state.prediction;

    setText('#panel-title', `${state.ticker} - krok ${state.current_step + 1}`);
    setText('#current-date', day.date);
    setText('#current-close', money(day.close));
    setText('#cash', money(portfolio.cash));
    setText('#shares', portfolio.shares);
    setText('#portfolio-value', money(portfolio.portfolio_value));
    setText('#profit-loss', money(portfolio.profit_loss));
    setText('#day-open', money(day.open));
    setText('#day-high', money(day.high));
    setText('#day-low', money(day.low));
    setText('#day-close', money(day.close));
    setText('#day-volume', Number(day.volume).toLocaleString('pl-PL'));
    setText('#prediction', `${prediction.direction} / ${money(prediction.predicted_close)}`);
    setText('#prediction-details', `${prediction.model}, confidence ${prediction.confidence}`);

    const profitLoss = document.querySelector('#profit-loss');
    profitLoss.classList.toggle('is-positive', Number(portfolio.profit_loss) > 0);
    profitLoss.classList.toggle('is-negative', Number(portfolio.profit_loss) < 0);

    renderHistory(state.history);
    renderChart(state.portfolio_history);
    setActionsDisabled(state.finished);

    if (state.finished) {
        actionMessage.textContent = 'Symulacja zakonczona. Mozesz uruchomic nowa.';
    }
}

function renderHistory(history) {
    const body = document.querySelector('#history-body');
    if (!history.length) {
        body.innerHTML = '<tr><td colspan="6">Brak decyzji.</td></tr>';
        return;
    }

    body.innerHTML = history.map((item) => `
        <tr>
            <td>${item.date}</td>
            <td>${item.action}</td>
            <td>${item.shares}</td>
            <td>${money(item.price)}</td>
            <td>${money(item.cash_after)}</td>
            <td>${money(item.portfolio_value_after)}</td>
        </tr>
    `).join('');
}

function renderChart(portfolioHistory) {
    const labels = portfolioHistory.map((item) => item.date);
    const closePrices = portfolioHistory.map((item) => Number(item.stock_price));
    const ctx = document.querySelector('#price-chart');

    if (!priceChart) {
        priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Close',
                    data: closePrices,
                    borderColor: '#126c59',
                    backgroundColor: 'rgba(18, 108, 89, 0.12)',
                    fill: true,
                    tension: 0.25,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false,
                    },
                },
            },
        });
        return;
    }

    priceChart.data.labels = labels;
    priceChart.data.datasets[0].data = closePrices;
    priceChart.update();
}

function setActionsDisabled(disabled) {
    actionButtons.forEach((button) => {
        button.disabled = disabled;
    });
    tradeSharesInput.disabled = disabled;
}

startForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    startMessage.textContent = 'Pobieram dane i startuje symulacje...';

    try {
        const state = await postJson(startForm.action, formPayload(startForm));
        startSection.classList.add('is-hidden');
        tradingPanel.classList.remove('is-hidden');
        actionMessage.textContent = '';
        renderState(state);
    } catch (error) {
        startMessage.textContent = error.message;
    }
});

actionButtons.forEach((button) => {
    button.addEventListener('click', async () => {
        actionMessage.textContent = 'Aktualizuje portfel...';
        const action = button.dataset.action;
        const shares = action === 'HOLD' ? 0 : tradeSharesInput.value;

        try {
            const state = await postJson('/api/action/', { action, shares });
            actionMessage.textContent = '';
            renderState(state);
        } catch (error) {
            actionMessage.textContent = error.message;
        }
    });
});

newSimulationButton.addEventListener('click', () => {
    tradingPanel.classList.add('is-hidden');
    startSection.classList.remove('is-hidden');
    startMessage.textContent = 'Pobieranie danych moze potrwac kilka sekund.';
    actionMessage.textContent = '';
    setActionsDisabled(false);
});
