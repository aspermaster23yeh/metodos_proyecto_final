"""Modelos numéricos alineados al reporte: logístico, spline y Newton-Raphson."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import newton

from report_data import K_RATE, L_MAX, SAMPLES_MAIN, T0_INFL


def logistic_c(t_min: float | np.ndarray, k: float = K_RATE, t0: float = T0_INFL, L: float = L_MAX) -> np.ndarray:
    t = np.asarray(t_min, dtype=float)
    return L / (1.0 + np.exp(-k * (t - t0)))


def logistic_c_prime(t_min: float, k: float = K_RATE, t0: float = T0_INFL, L: float = L_MAX) -> float:
    e = np.exp(-k * (t_min - t0))
    return float(L * k * e / (1.0 + e) ** 2)


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=float)
    yh = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y - yh) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0


def newton_time_for_target(
    target_pct: float,
    t_init_min: float = 26.0,
    tol: float = 1e-8,
    maxiter: int = 50,
) -> tuple[float | None, str, list[dict]]:
    """Newton-Raphson escalar: C(t) - target = 0 (t en minutos)."""

    def f(t: float) -> float:
        return float(logistic_c(t) - target_pct)

    def fp(t: float) -> float:
        return logistic_c_prime(t)

    steps: list[dict] = []
    t = float(t_init_min)
    for n in range(maxiter):
        ft = f(t)
        fpt = fp(t)
        if abs(fpt) < 1e-14:
            return None, "Derivada casi cero — detenido", steps
        t_new = t - ft / fpt
        delta = abs(t_new - t)
        steps.append({"n": n, "t": t, "f": ft, "fp": fpt, "t_new": t_new, "delta": delta})
        t = t_new
        if delta < tol:
            return float(t), f"Convergió en {n + 1} iteraciones", steps
    return float(t), "Máximo de iteraciones alcanzado", steps


def report_fit_stats(df: pd.DataFrame) -> dict[str, float]:
    t = df["t_min"].to_numpy()
    y = df["level"].to_numpy()
    y_log = logistic_c(t)
    y_lin = np.polyval(np.polyfit(t, y, 1), t)
    return {
        "r2_logistic": r2_score(y, y_log),
        "r2_linear": r2_score(y, y_lin),
        "n_samples": len(y),
        "t_max_min": float(t.max()),
    }
