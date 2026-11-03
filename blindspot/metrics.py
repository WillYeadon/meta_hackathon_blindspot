"""Rejection is detection for errors and a false positive for controls."""
import math


def wilson(rejections, n):
    if not n:
        return None
    z = 1.959963984540054
    p, denominator = rejections/n, 1 + z*z/n
    midpoint = (p + z*z/(2*n)) / denominator
    radius = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator
    return [max(0, midpoint-radius), min(1, midpoint+radius)]


def aggregate(cell_result, is_control):
    trials = cell_result.get("trials", [])
    parsed = [t for t in trials if t.get("status") == "ok" and type(t.get("valid")) is bool]
    rejections = sum(not t["valid"] for t in parsed)
    observed = rejections/len(parsed) if parsed else None
    prediction = cell_result.get("prediction")
    predicted = prediction["probability_percent"]/100 if prediction and prediction.get("status") == "ok" else None
    gap = predicted - observed if predicted is not None and observed is not None else None
    return dict(metric="false_positive_rate" if is_control else "detection_probability",
                predicted=predicted, observed=observed, calibration_gap=gap,
                absolute_calibration_error=abs(gap) if gap is not None else None,
                valid_trials=len(parsed), rejected_trials=rejections,
                failed_trials=len(trials)-len(parsed), wilson_95=wilson(rejections, len(parsed)))
