from __future__ import annotations

from math import sqrt
from typing import Any

from main.services.preprocessing import (
    DEFAULT_LOOKBACK_DAYS,
    FEATURE_COLUMNS,
    build_feature_columns,
    build_feature_frame,
)


MIN_FEATURE_ROWS = 10
DEFAULT_TRAINING_WINDOW_DAYS = 60


class ModelTrainingError(ValueError):
    pass


def build_prediction_artifacts(
    prices: list[dict[str, Any]],
    current_step: int | None = None,
    training_window_days: int = DEFAULT_TRAINING_WINDOW_DAYS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    train_ratio: float = 0.75,
    n_estimators: int = 80,
) -> dict[str, Any]:
    if not prices:
        raise ModelTrainingError('Brak danych do treningu modelu ML.')

    current_step = len(prices) - 1 if current_step is None else int(current_step)
    if current_step < 0 or current_step >= len(prices):
        raise ModelTrainingError('Niepoprawny krok symulacji dla modelu ML.')

    if lookback_days < 2:
        raise ModelTrainingError('Parametr lookback_days musi byc nie mniejszy niz 2.')

    if training_window_days < MIN_FEATURE_ROWS:
        raise ModelTrainingError(
            f'Parametr training_window_days musi byc nie mniejszy niz {MIN_FEATURE_ROWS}.'
        )

    observed_prices = prices[: current_step + 1]
    feature_columns = build_feature_columns(lookback_days)
    prediction_row = build_feature_frame(observed_prices, lookback_days=lookback_days, include_target=False)
    if prediction_row.empty:
        raise ModelTrainingError('Za malo odslonietych danych do wyliczenia cech modelu ML.')

    training_frame = build_feature_frame(observed_prices, lookback_days=lookback_days, include_target=True)
    if len(training_frame) < MIN_FEATURE_ROWS:
        raise ModelTrainingError('Za malo odslonietych danych do treningu modelu ML.')

    training_frame = training_frame.tail(training_window_days).reset_index(drop=True)
    if len(training_frame) < MIN_FEATURE_ROWS:
        raise ModelTrainingError('Za malo danych po zastosowaniu okna treningowego modelu ML.')

    split_index = _split_index(len(training_frame), train_ratio)
    train_frame = training_frame.iloc[:split_index]
    test_frame = training_frame.iloc[split_index:]

    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.metrics import accuracy_score, mean_absolute_error, mean_squared_error, precision_recall_fscore_support, r2_score

    regressor = RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=42,
        min_samples_leaf=2,
    )
    classifier = RandomForestClassifier(
        n_estimators=n_estimators,
        random_state=42,
        min_samples_leaf=2,
        class_weight='balanced',
    )

    x_train = train_frame[feature_columns]
    x_test = test_frame[feature_columns]
    y_price_train = train_frame['target_close']
    y_price_test = test_frame['target_close']
    y_direction_train = train_frame['target_direction']
    y_direction_test = test_frame['target_direction']

    regressor.fit(x_train, y_price_train)
    regression_predictions = regressor.predict(x_test)

    classifier_metrics = _empty_classifier_metrics()
    classifier_ready = y_direction_train.nunique() > 1
    if classifier_ready:
        classifier.fit(x_train, y_direction_train)
        direction_predictions = classifier.predict(x_test)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_direction_test,
            direction_predictions,
            average='binary',
            zero_division=0,
        )
        classifier_metrics = {
            'accuracy': _round_metric(accuracy_score(y_direction_test, direction_predictions)),
            'precision': _round_metric(precision),
            'recall': _round_metric(recall),
            'f1': _round_metric(f1),
        }

    latest_row = prediction_row.iloc[[-1]]
    predicted_close = float(regressor.predict(latest_row[feature_columns])[0])
    current_close = float(latest_row['close'].iloc[0])
    change = predicted_close - current_close
    change_percent = (change / current_close) * 100 if current_close else 0
    probability_up = _probability_up(classifier, latest_row[feature_columns]) if classifier_ready else 0.5
    confidence = max(probability_up, 1 - probability_up)
    direction = 'UP' if change > 0 else 'DOWN' if change < 0 else 'FLAT'

    return {
        'model_name': 'Random Forest',
        'train_rows': int(len(train_frame)),
        'test_rows': int(len(test_frame)),
        'feature_columns': feature_columns,
        'metrics': {
            'regression': {
                'mae': _round_metric(mean_absolute_error(y_price_test, regression_predictions)),
                'rmse': _round_metric(sqrt(mean_squared_error(y_price_test, regression_predictions))),
                'r2': _round_metric(r2_score(y_price_test, regression_predictions)),
            },
            'classification': classifier_metrics,
        },
        'model_params': {
            'training_window_days': int(training_window_days),
            'lookback_days': int(lookback_days),
            'train_ratio': float(train_ratio),
            'n_estimators': int(n_estimators),
        },
        'current_prediction': {
            'model': 'Random Forest',
            'predicted_close': f'{predicted_close:.2f}',
            'direction': direction,
            'confidence': _round_metric(confidence),
            'probability_up': _round_metric(probability_up),
            'probability_down': _round_metric(1 - probability_up),
            'change': f'{change:.2f}',
            'change_percent': _round_metric(change_percent),
            'based_on_date': str(latest_row['date'].iloc[0]),
            'target_date': _target_date(prices, current_step),
        },
    }


def _split_index(row_count: int, train_ratio: float) -> int:
    split_index = int(row_count * train_ratio)
    split_index = max(8, split_index)
    split_index = min(row_count - 2, split_index)
    if split_index <= 0 or split_index >= row_count:
        raise ModelTrainingError('Nie mozna podzielic danych na trening i test.')
    return split_index


def _probability_up(classifier, feature_row) -> float:
    class_labels = list(classifier.classes_)
    probability_index = class_labels.index(1) if 1 in class_labels else None
    if probability_index is None:
        return 0.5
    return float(classifier.predict_proba(feature_row)[:, probability_index][0])


def _target_date(prices: list[dict[str, Any]], current_step: int) -> str | None:
    if current_step + 1 >= len(prices):
        return None
    return prices[current_step + 1]['date']


def _empty_classifier_metrics() -> dict[str, None]:
    return {
        'accuracy': None,
        'precision': None,
        'recall': None,
        'f1': None,
    }


def _round_metric(value: float) -> float:
    return round(float(value), 4)
