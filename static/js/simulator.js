const startForm = document.querySelector('#simulation-start-form');
const startSection = document.querySelector('#start-section');
const tradingPanel = document.querySelector('#trading-panel');
const startMessage = document.querySelector('#start-message');
const actionMessage = document.querySelector('#action-message');
const newSimulationButton = document.querySelector('#new-simulation-button');
const actionButtons = document.querySelectorAll('[data-action]');
const tradeSharesInput = document.querySelector('#trade-shares');
const startDateInput = startForm.querySelector('[name="start_date"]');
const endDateInput = startForm.querySelector('[name="end_date"]');
const resetZoomButton = document.querySelector('#reset-zoom-button');
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
    syncDateRange();
    const data = new FormData(form);
    return Object.fromEntries(data.entries());
}

function nextDate(value) {
    const [year, month, day] = value.split('-').map(Number);
    const date = new Date(Date.UTC(year, month - 1, day));
    date.setUTCDate(date.getUTCDate() + 1);
    return date.toISOString().slice(0, 10);
}

function syncDateRange() {
    if (!startDateInput.value) {
        return;
    }

    const minimumEndDate = nextDate(startDateInput.value);
    endDateInput.min = minimumEndDate;

    if (!endDateInput.value || endDateInput.value <= startDateInput.value) {
        endDateInput.value = minimumEndDate;
    }
}

function scheduleDateRangeSync() {
    window.setTimeout(syncDateRange, 0);
}

function setText(selector, value) {
    document.querySelector(selector).textContent = value;
}

function money(value) {
    return `${Number(value).toFixed(2)} USD`;
}

function percent(value) {
    return `${Number(value).toFixed(2)}%`;
}

function signedMoney(value) {
    const numberValue = Number(value);
    return `${numberValue >= 0 ? '+' : ''}${money(numberValue)}`;
}

function signedPercent(value) {
    const numberValue = Number(value);
    return `${numberValue >= 0 ? '+' : ''}${percent(numberValue)}`;
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
    renderPrediction(prediction);
    renderModelMetrics(state.model_metrics);
    renderModelParams(state.model_params);
    renderDataStats(state.data_stats);

    const profitLoss = document.querySelector('#profit-loss');
    profitLoss.classList.toggle('is-positive', Number(portfolio.profit_loss) > 0);
    profitLoss.classList.toggle('is-negative', Number(portfolio.profit_loss) < 0);

    renderHistory(state.history);
    renderPredictionEvaluations(state.prediction_evaluation_history || []);
    renderChart(state.portfolio_history);
    renderSummary(state.summary);
    setActionsDisabled(state.finished);

    if (state.finished) {
        actionMessage.textContent = 'Symulacja zakonczona. Mozesz uruchomic nowa.';
    }
}

function renderSummary(summary) {
    const summarySection = document.querySelector('#summary-section');
    if (!summary) {
        summarySection.classList.add('is-hidden');
        return;
    }

    summarySection.classList.remove('is-hidden');
    setText('#summary-final-date', summary.final_date);
    setText('#summary-final-value', money(summary.final_portfolio_value));
    setText('#summary-profit-loss', money(summary.total_profit_loss));
    setText('#summary-transaction-count', summary.transaction_count);
    setText('#summary-buy-hold', money(summary.buy_and_hold_value));
    setText('#summary-difference', money(summary.difference_vs_buy_and_hold));
    setText(
        '#summary-actions',
        `Kupno: ${summary.action_counts.BUY}, sprzedaz: ${summary.action_counts.SELL}, czekanie: ${summary.action_counts.HOLD}`,
    );
}

function renderPrediction(prediction) {
    const predictionBox = document.querySelector('#prediction-box');
    const direction = prediction.direction || 'FLAT';
    const change = Number(prediction.change || 0);
    const arrow = direction === 'UP' ? '^' : direction === 'DOWN' ? 'v' : '=';
    const label = direction === 'UP' ? 'wzrost' : direction === 'DOWN' ? 'spadek' : 'bez zmian';
    const signedChange = `${change >= 0 ? '+' : ''}${money(change)}`;
    const signedPercent = `${Number(prediction.change_percent || 0) >= 0 ? '+' : ''}${percent(prediction.change_percent || 0)}`;
    const targetDate = prediction.target_date ? ` dla dnia ${prediction.target_date}` : '';
    const probabilityUp = percent(Number(prediction.probability_up || 0) * 100);
    const probabilityDown = percent(Number(prediction.probability_down || (1 - Number(prediction.probability_up || 0))) * 100);

    predictionBox.classList.toggle('prediction-up', direction === 'UP');
    predictionBox.classList.toggle('prediction-down', direction === 'DOWN');
    predictionBox.classList.toggle('prediction-flat', direction === 'FLAT');

    setText('#prediction', `${arrow} ${label}: ${money(prediction.predicted_close)}`);
    setText('#prediction-change', `${signedChange} (${signedPercent}) wzgledem dzisiejszego zamkniecia${targetDate}`);
    setText(
        '#prediction-details',
        `${prediction.model}, pewnosc ${percent(Number(prediction.confidence || 0) * 100)}, P(up) ${probabilityUp}, P(down) ${probabilityDown}`,
    );
}

function renderModelMetrics(modelMetrics) {
    if (!modelMetrics) {
        return;
    }

    const metrics = modelMetrics.metrics;
    setText('#model-name', modelMetrics.model_name || '-');
    setText('#model-warning', modelMetrics.warning || '');

    if (!metrics) {
        ['#metric-mae', '#metric-rmse', '#metric-r2', '#metric-accuracy', '#metric-f1'].forEach((selector) => {
            setText(selector, '-');
        });
        return;
    }

    setText('#metric-mae', formatMetric(metrics.regression.mae));
    setText('#metric-rmse', formatMetric(metrics.regression.rmse));
    setText('#metric-r2', formatMetric(metrics.regression.r2));
    setText('#metric-accuracy', formatMetric(metrics.classification.accuracy));
    setText('#metric-f1', formatMetric(metrics.classification.f1));
}

function renderModelParams(modelParams) {
    if (!modelParams) {
        return;
    }

    setText('#model-training-window', `${modelParams.training_window_days} dni`);
    setText('#model-lookback', `${modelParams.lookback_days} dni`);
}

function renderDataStats(stats) {
    if (!stats) {
        return;
    }

    setText('#stats-visible-days', stats.visible_days);
    setText('#stats-min-close', money(stats.min_close));
    setText('#stats-max-close', money(stats.max_close));
    setText('#stats-avg-close', money(stats.avg_close));
    setText('#stats-avg-volume', Number(stats.avg_volume).toLocaleString('pl-PL'));
    setText('#stats-return', percent(stats.period_return_percent));
    setText('#stats-range', `Zakres widocznych danych: ${stats.first_date} - ${stats.last_date}`);
}

function formatMetric(value) {
    return value === null || value === undefined ? '-' : Number(value).toFixed(3);
}

function renderHistory(history) {
    const body = document.querySelector('#history-body');
    if (!history.length) {
        body.innerHTML = '<tr><td colspan="8">Brak decyzji.</td></tr>';
        return;
    }

    body.innerHTML = history.map((item) => `
        <tr>
            <td>${item.date}</td>
            <td>${actionLabel(item.action)}</td>
            <td>${item.shares}</td>
            <td>${money(item.price)}</td>
            <td class="${movementClass(item.price_direction)}">${movementLabel(item.price_direction)} ${signedMoney(item.price_change || 0)}</td>
            <td class="${movementClass(item.price_direction)}">${signedPercent(item.price_change_percent || 0)}</td>
            <td>${money(item.cash_after)}</td>
            <td>${money(item.portfolio_value_after)}</td>
        </tr>
    `).join('');
}

function renderPredictionEvaluations(evaluations) {
    const body = document.querySelector('#prediction-evaluation-body');
    if (!evaluations.length) {
        body.innerHTML = '<tr><td colspan="8">Brak porownan.</td></tr>';
        return;
    }

    body.innerHTML = evaluations.map((item) => `
        <tr>
            <td>${item.based_on_date}</td>
            <td>${item.target_date}</td>
            <td>${money(item.predicted_close)}</td>
            <td>${money(item.actual_close)}</td>
            <td>${money(item.error)}</td>
            <td>${directionLabel(item.predicted_direction)}</td>
            <td>${directionLabel(item.actual_direction)}</td>
            <td>${item.direction_match ? 'Tak' : 'Nie'}</td>
        </tr>
    `).join('');
}

function actionLabel(action) {
    const labels = {
        BUY: 'Kupno',
        SELL: 'Sprzedaz',
        HOLD: 'Czekanie',
    };
    return labels[action] || action;
}

function directionLabel(direction) {
    const labels = {
        UP: 'Wzrost',
        DOWN: 'Spadek',
        FLAT: 'Bez zmian',
    };
    return labels[direction] || direction;
}

function movementLabel(direction) {
    return directionLabel(direction) || 'Bez zmian';
}

function movementClass(direction) {
    if (direction === 'UP') {
        return 'is-positive';
    }
    if (direction === 'DOWN') {
        return 'is-negative';
    }
    return 'is-neutral';
}

function renderChart(portfolioHistory) {
    const labels = portfolioHistory.map((item) => item.date);
    const closePrices = portfolioHistory.map((item) => Number(item.stock_price));
    const openPrices = portfolioHistory.map((item) => Number(item.open));
    const highPrices = portfolioHistory.map((item) => Number(item.high));
    const lowPrices = portfolioHistory.map((item) => Number(item.low));
    const volumes = portfolioHistory.map((item) => Number(item.volume));
    const ctx = document.querySelector('#price-chart');
    const datasets = [
        {
            label: 'Zamkniecie',
            data: closePrices,
            borderColor: '#126c59',
            backgroundColor: 'rgba(18, 108, 89, 0.12)',
            fill: false,
            tension: 0.25,
            yAxisID: 'price',
        },
        {
            label: 'Otwarcie',
            data: openPrices,
            borderColor: '#4b7bec',
            backgroundColor: 'rgba(75, 123, 236, 0.08)',
            fill: false,
            tension: 0.2,
            yAxisID: 'price',
        },
        {
            label: 'Maksimum',
            data: highPrices,
            borderColor: '#d18b00',
            backgroundColor: 'rgba(209, 139, 0, 0.08)',
            fill: false,
            tension: 0.2,
            yAxisID: 'price',
        },
        {
            label: 'Minimum',
            data: lowPrices,
            borderColor: '#a13535',
            backgroundColor: 'rgba(161, 53, 53, 0.08)',
            fill: false,
            tension: 0.2,
            yAxisID: 'price',
        },
        {
            type: 'bar',
            label: 'Wolumen',
            data: volumes,
            borderColor: 'rgba(101, 115, 111, 0.35)',
            backgroundColor: 'rgba(101, 115, 111, 0.18)',
            yAxisID: 'volume',
        },
    ];

    if (!priceChart) {
        priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: 'x',
                        },
                        zoom: {
                            wheel: {
                                enabled: true,
                            },
                            pinch: {
                                enabled: true,
                            },
                            mode: 'x',
                        },
                    },
                },
                scales: {
                    price: {
                        type: 'linear',
                        position: 'left',
                        beginAtZero: false,
                    },
                    volume: {
                        type: 'linear',
                        position: 'right',
                        grid: {
                            drawOnChartArea: false,
                        },
                    },
                },
            },
        });
        return;
    }

    priceChart.data.labels = labels;
    priceChart.data.datasets = datasets;
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
    syncDateRange();
    startMessage.textContent = 'Pobieram dane i uruchamiam symulacje...';

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
            const state = await postJson('/api/decision', { action, shares });
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

resetZoomButton.addEventListener('click', () => {
    if (priceChart && typeof priceChart.resetZoom === 'function') {
        priceChart.resetZoom();
    }
});

['change', 'input', 'blur', 'keyup'].forEach((eventName) => {
    startDateInput.addEventListener(eventName, scheduleDateRangeSync);
    endDateInput.addEventListener(eventName, scheduleDateRangeSync);
});

syncDateRange();
