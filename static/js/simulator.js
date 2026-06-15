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
let chartPointCount = 0;

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
    renderPrediction(prediction, state.prediction_evaluation_history || []);
    renderModelMetrics(state.model_metrics);
    renderModelParams(state.model_params);
    renderDataStats(state.data_stats);

    const profitLoss = document.querySelector('#profit-loss');
    profitLoss.classList.toggle('is-positive', Number(portfolio.profit_loss) > 0);
    profitLoss.classList.toggle('is-negative', Number(portfolio.profit_loss) < 0);

    renderHistory(state.history);
    renderPredictionEvaluations(state.prediction_evaluation_history || []);
    renderChart(state.portfolio_history, prediction, state.prediction_evaluation_history || []);
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

function renderPrediction(prediction, evaluations = []) {
    const predictionBox = document.querySelector('#prediction-box');
    const predictionResult = document.querySelector('#prediction-result');
    const direction = prediction.direction || 'FLAT';
    const change = Number(prediction.change || 0);
    const arrow = direction === 'UP' ? '\u2191' : direction === 'DOWN' ? '\u2193' : '\u2192';
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
        `${prediction.model}, pewnosc ${percent(Number(prediction.confidence || 0) * 100)}, P(up) = szansa wzrostu ${probabilityUp}, P(down) = szansa spadku ${probabilityDown}`,
    );

    const latestEvaluation = evaluations[evaluations.length - 1];
    if (!latestEvaluation) {
        predictionResult.classList.add('is-hidden');
        predictionResult.textContent = '';
        predictionResult.classList.remove('is-positive', 'is-negative');
        return;
    }

    predictionResult.classList.remove('is-hidden');
    predictionResult.classList.toggle('is-positive', Boolean(latestEvaluation.direction_match));
    predictionResult.classList.toggle('is-negative', !latestEvaluation.direction_match);
    predictionResult.textContent = predictionEvaluationSummary(latestEvaluation);
}

function renderModelMetrics(modelMetrics) {
    if (!modelMetrics) {
        return;
    }

    const metrics = modelMetrics.metrics;
    setText('#model-name', modelMetrics.model_name || '-');
    setText('#model-warning', modelMetrics.warning || '');
    setText('#model-train-rows', modelMetrics.train_rows === null || modelMetrics.train_rows === undefined ? '-' : `${modelMetrics.train_rows}`);

    if (!metrics) {
        ['#metric-mae', '#metric-rmse', '#metric-r2', '#metric-accuracy', '#metric-f1', '#metric-precision'].forEach((selector) => {
            setText(selector, '-');
        });
        return;
    }

    setText('#metric-mae', formatMetric(metrics.regression.mae));
    setText('#metric-rmse', formatMetric(metrics.regression.rmse));
    setText('#metric-r2', formatMetric(metrics.regression.r2));
    setText('#metric-accuracy', formatMetricPercent(metrics.classification.accuracy));
    setText('#metric-precision', formatMetricPercent(metrics.classification.precision));
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

function formatMetricPercent(value) {
    return value === null || value === undefined ? '-' : percent(Number(value) * 100);
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
        body.innerHTML = '<tr><td colspan="9">Brak porownan.</td></tr>';
        return;
    }

    body.innerHTML = evaluations.map((item) => `
        <tr>
            <td>${item.based_on_date}</td>
            <td>${item.target_date}</td>
            <td>${money(item.predicted_close)}</td>
            <td>${money(item.actual_close)}</td>
            <td class="${predictionErrorClass(item.error)}">${predictionErrorLabel(item.error)}</td>
            <td>${directionArrowLabel(item.predicted_direction)}</td>
            <td>${directionArrowLabel(item.actual_direction)}</td>
            <td>${probabilityPair(item)}</td>
            <td class="${item.direction_match ? 'evaluation-match' : 'evaluation-miss'}">${item.direction_match ? 'Trafiony kierunek' : 'Pomylka kierunku'}</td>
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

function directionArrowLabel(direction) {
    const arrows = {
        UP: '\u2191',
        DOWN: '\u2193',
        FLAT: '\u2192',
    };
    return `${arrows[direction] || ''} ${directionLabel(direction)}`.trim();
}

function predictionErrorLabel(error) {
    const value = Number(error || 0);
    if (value > 0) {
        return `Model zanizyl o ${money(Math.abs(value))}`;
    }
    if (value < 0) {
        return `Model zawyzyl o ${money(Math.abs(value))}`;
    }
    return 'Trafiona cena';
}

function predictionErrorClass(error) {
    return Number(error || 0) === 0 ? 'is-positive' : 'is-negative';
}

function probabilityPair(item) {
    const probabilityUp = item.probability_up === null || item.probability_up === undefined ? '-' : percent(Number(item.probability_up) * 100);
    const probabilityDown = item.probability_down === null || item.probability_down === undefined ? '-' : percent(Number(item.probability_down) * 100);
    return `${probabilityUp} / ${probabilityDown}`;
}

function predictionEvaluationSummary(item) {
    const result = item.direction_match ? 'model trafil kierunek' : 'model pomylil kierunek';
    return `Ostatnia sprawdzona predykcja: ${result}, ${predictionErrorLabel(item.error).toLowerCase()}.`;
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

function renderChart(portfolioHistory, prediction, evaluations = []) {
    const observedLabels = portfolioHistory.map((item) => item.date);
    const labels = [...observedLabels];
    if (prediction && prediction.target_date && !labels.includes(prediction.target_date)) {
        labels.push(prediction.target_date);
    }

    const historyByDate = new Map(portfolioHistory.map((item) => [item.date, item]));
    const closePrices = labels.map((date) => historyByDate.has(date) ? Number(historyByDate.get(date).stock_price) : null);
    const openPrices = labels.map((date) => historyByDate.has(date) ? Number(historyByDate.get(date).open) : null);
    const highPrices = labels.map((date) => historyByDate.has(date) ? Number(historyByDate.get(date).high) : null);
    const lowPrices = labels.map((date) => historyByDate.has(date) ? Number(historyByDate.get(date).low) : null);
    const volumes = labels.map((date) => historyByDate.has(date) ? Number(historyByDate.get(date).volume) : null);
    const evaluatedPredictionByDate = new Map(evaluations.map((item) => [item.target_date, Number(item.predicted_close)]));
    const evaluatedPredictionPrices = labels.map((date) => evaluatedPredictionByDate.get(date) || null);
    const currentPredictionPrices = labels.map((date) => prediction && date === prediction.target_date ? Number(prediction.predicted_close) : null);
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
        {
            type: 'line',
            label: 'Predykcje sprawdzone',
            data: evaluatedPredictionPrices,
            borderColor: '#d18b00',
            backgroundColor: '#d18b00',
            pointBackgroundColor: '#d18b00',
            pointBorderColor: '#ffffff',
            pointRadius: 5,
            pointHoverRadius: 7,
            showLine: false,
            yAxisID: 'price',
        },
        {
            type: 'line',
            label: 'Aktualna predykcja',
            data: currentPredictionPrices,
            borderColor: '#7c3aed',
            backgroundColor: '#7c3aed',
            pointBackgroundColor: '#7c3aed',
            pointBorderColor: '#ffffff',
            pointRadius: 6,
            pointHoverRadius: 8,
            showLine: false,
            yAxisID: 'price',
        },
    ];

    if (!priceChart) {
        chartPointCount = labels.length;
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
    if (labels.length !== chartPointCount) {
        chartPointCount = labels.length;
        if (typeof priceChart.resetZoom === 'function') {
            priceChart.resetZoom('none');
        }
    }
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
