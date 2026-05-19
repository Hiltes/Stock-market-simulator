from __future__ import annotations

from math import sqrt
from typing import Any

from main.services.preprocessing import FEATURE_COLUMNS, build_feature_frame


MIN_FEATURE_ROWS = 20


class ModelTrainingError(ValueError):
    pass


def build_prediction_artifacts(
    prices: list[dict[str, Any]],
    train_ratio: float = 0.75,
    n_estimators: int = 80,
) -> dict[str, Any]:
    feature_frame = build_feature_frame(prices)
    if len(feature_frame) < MIN_FEATURE_ROWS:
        raise ModelTrainingError('Za mało danych do treningu modelu ML.')

    split_index = _split_index(len(feature_frame), train_ratio)
    train_frame = feature_frame.iloc[:split_index]
    test_frame = feature_frame.iloc[split_index:]

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

    x_train = train_frame[FEATURE_COLUMNS]
    x_test = test_frame[FEATURE_COLUMNS]
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

    return {
        'model_name': 'Random Forest',
        'train_rows': int(len(train_frame)),
        'test_rows': int(len(test_frame)),
        'feature_columns': FEATURE_COLUMNS,
        'metrics': {
            'regression': {
                'mae': _round_metric(mean_absolute_error(y_price_test, regression_predictions)),
                'rmse': _round_metric(sqrt(mean_squared_error(y_price_test, regression_predictions))),
                'r2': _round_metric(r2_score(y_price_test, regression_predictions)),
            },
            'classification': classifier_metrics,
        },
        'predictions_by_date': _predictions_by_date(feature_frame, regressor, classifier if classifier_ready else None),
    }


def _split_index(row_count: int, train_ratio: float) -> int:
    split_index = int(row_count * train_ratio)
    split_index = max(10, split_index)
    split_index = min(row_count - 2, split_index)
    if split_index <= 0 or split_index >= row_count:
        raise ModelTrainingError('Nie można podzielić danych na trening i test.')
    return split_index


def _predictions_by_date(feature_frame, regressor, classifier) -> dict[str, dict[str, Any]]:
    predictions = {}
    predicted_prices = regressor.predict(feature_frame[FEATURE_COLUMNS])

    probabilities_up = None
    if classifier is not None:
        class_labels = list(classifier.classes_)
        probability_index = class_labels.index(1) if 1 in class_labels else None
        if probability_index is not None:
            probabilities_up = classifier.predict_proba(feature_frame[FEATURE_COLUMNS])[:, probability_index]

    for index, row in feature_frame.reset_index(drop=True).iterrows():
        current_close = float(row['close'])
        predicted_close = float(predicted_prices[index])
        change = predicted_close - current_close
        change_percent = (change / current_close) * 100 if current_close else 0
        direction = 'UP' if change > 0 else 'DOWN' if change < 0 else 'FLAT'
        probability_up = float(probabilities_up[index]) if probabilities_up is not None else 0.5
        confidence = max(probability_up, 1 - probability_up)

        predictions[str(row['date'])] = {
            'model': 'Random Forest',
            'predicted_close': f'{predicted_close:.2f}',
            'direction': direction,
            'confidence': _round_metric(confidence),
            'probability_up': _round_metric(probability_up),
            'change': f'{change:.2f}',
            'change_percent': _round_metric(change_percent),
        }

    return predictions


def _empty_classifier_metrics() -> dict[str, None]:
    return {
        'accuracy': None,
        'precision': None,
        'recall': None,
        'f1': None,
    }


def _round_metric(value: float) -> float:
    return round(float(value), 4)
