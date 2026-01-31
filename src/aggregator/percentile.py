# src/aggregator/percentile.py


def calculate_percentile(value: float, history: list[float]) -> float:
    if not history:
        return 50.0
    count_below = sum(1 for h in history if h < abs(value))
    return count_below / len(history) * 100


def get_level_emoji(percentile: float) -> str:
    if percentile < 75:
        return "🟢"
    elif percentile < 90:
        return "🟡"
    else:
        return "🔴"
