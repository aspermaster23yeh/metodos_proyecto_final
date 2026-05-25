"""Modelos numéricos alineados al reporte: logístico, spline y Newton-Raphson."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.interpolate import UnivariateSpline
from scipy.optimize import curve_fit, newton

from report_data import K_RATE, K_SEED, L_MAX, T0_INFL, T0_SEED


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


def linear_predict(t_min: np.ndarray, coef: np.ndarray) -> np.ndarray:
    return np.polyval(coef, t_min)


def _fit_spline_on_samples(t_min: np.ndarray, levels: np.ndarray) -> UnivariateSpline:
    t_h = t_min / 60.0
    n = t_min.size
    k = int(min(3, max(1, n - 1)))
    s = max(0.0, (n * float(np.var(levels))) * 0.05) if n >= 4 else 0.0
    return UnivariateSpline(t_h, levels, k=k, s=s)


@dataclass
class ModelComparison:
    r2_linear: float
    r2_logistic: float
    r2_spline: float
    t_grid: np.ndarray
    y_linear: np.ndarray
    y_logistic: np.ndarray
    y_spline: np.ndarray
    linear_coef: np.ndarray
    t_cv_min: float | None


def compare_models(df: pd.DataFrame, threshold_cv: float = 80.0) -> ModelComparison:
    t = df["t_min"].to_numpy(dtype=float)
    y = df["level"].to_numpy(dtype=float)
    coef = np.polyfit(t, y, 1)
    y_lin_obs = linear_predict(t, coef)
    y_log_obs = logistic_c(t)
    sp = _fit_spline_on_samples(t, y)
    y_sp_obs = sp(t / 60.0)

    t_grid = np.linspace(float(t.min()), max(float(t.max()), 1.0), 200)
    y_linear = linear_predict(t_grid, coef)
    y_logistic = logistic_c(t_grid)
    y_spline = sp(t_grid / 60.0)

    return ModelComparison(
        r2_linear=r2_score(y, y_lin_obs),
        r2_logistic=r2_score(y, y_log_obs),
        r2_spline=r2_score(y, y_sp_obs),
        t_grid=t_grid,
        y_linear=y_linear,
        y_logistic=y_logistic,
        y_spline=y_spline,
        linear_coef=coef,
        t_cv_min=estimate_cv_start_min(df, threshold_cv),
    )


def estimate_cv_start_min(df: pd.DataFrame, threshold: float = 80.0) -> float | None:
    """Primer instante (min) en que la carga alcanza el umbral — interpolación lineal."""
    d = df.sort_values("t_min")
    t = d["t_min"].to_numpy(dtype=float)
    y = d["level"].to_numpy(dtype=float)
    for i in range(1, len(y)):
        if y[i - 1] < threshold <= y[i]:
            if y[i] == y[i - 1]:
                return float(t[i])
            frac = (threshold - y[i - 1]) / (y[i] - y[i - 1])
            return float(t[i - 1] + frac * (t[i] - t[i - 1]))
    if len(y) and y[-1] >= threshold:
        return float(t[-1])
    return None


def comparison_verdict_es(cmp: ModelComparison) -> str:
    scores = {
        "Lineal": cmp.r2_linear,
        "Logístico": cmp.r2_logistic,
        "Spline": cmp.r2_spline,
    }
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    best_r2 = scores[best]
    second = sorted(scores.values(), reverse=True)[1]
    delta = best_r2 - second

    if best == "Logístico":
        why = (
            "La curva logística captura la **saturación hacia 100%** y el cambio de ritmo "
            "entre la fase **CC** (subida más rápida) y la **CV** (tramo final más lento), "
            "algo que una recta no puede representar."
        )
    elif best == "Spline":
        why = (
            "El spline se adapta punto a punto con gran flexibilidad; es útil para visualizar "
            "la serie medida, aunque tiene menos interpretación física que la sigmoide."
        )
    else:
        why = (
            "En este tramo la recta parece competir con la sigmoide, pero extrapolar "
            "más allá del experimento sobreestimaría la velocidad de carga."
        )

    return (
        f"El modelo con mayor **R²** es **{best}** ({best_r2:.4f}), "
        f"por encima del siguiente en ≈{delta:.4f}. {why}"
    )


def device_summary(df: pd.DataFrame) -> dict[str, float | int | None]:
    stats = report_fit_stats(df)
    d0 = df[df["t_min"] == 0]
    d5 = df[df["t_min"] == 5]
    slope = None
    if not d0.empty and not d5.empty:
        slope = (float(d5["level"].iloc[0]) - float(d0["level"].iloc[0])) / 5.0
    return {
        **stats,
        "initial_slope_pct_per_min": slope,
        "t_100_min": float(df["t_min"].max()),
        "final_level": float(df["level"].iloc[-1]),
    }


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


def format_newton_steps(steps: list[dict]) -> pd.DataFrame:
    if not steps:
        return pd.DataFrame()
    return pd.DataFrame(steps).rename(
        columns={
            "n": "Iteración",
            "t": "t (min)",
            "f": "f(t)",
            "fp": "f'(t)",
            "t_new": "t nuevo",
            "delta": "Error",
        }
    )


def _minutes_to_mmss(t_min: float) -> str:
    mm = int(t_min)
    ss = int(round((t_min - mm) * 60))
    return f"{mm}:{ss:02d}"


def newton_batch_table(targets: list[int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for pct in targets:
        t_star, msg, steps = newton_time_for_target(float(pct))
        rows.append(
            {
                "% objetivo": pct,
                "t* (min)": round(t_star, 4) if t_star is not None else None,
                "Tiempo": _minutes_to_mmss(t_star) if t_star is not None else "—",
                "Iteraciones": len(steps),
                "Estado": msg,
                "Convergió": "Sí" if t_star is not None and steps and steps[-1]["delta"] < 1e-6 else "Parcial",
            }
        )
    return pd.DataFrame(rows)


def multivar_fit_note() -> str:
    return (
        "En el reporte, al resolver simultáneamente **k** y **t₀** con Newton-Raphson multivariable "
        "(sistema no lineal + Jacobiano), el resultado fue **k = NaN** y **t₀ = NaN**. "
        "Causas probables:\n\n"
        "- **Condición inicial** lejana del mínimo (semilla logit k≈0.1139, t₀≈21.71 min vs ajuste final k≈0.1185, t₀≈23.85).\n"
        "- Puntos en **0% y 100%** que fijan la curva y sensibilizan el Jacobiano.\n"
        "- El método **no es global**: pequeñas perturbaciones divergen.\n\n"
        "El problema **escalar** (dado k y t₀ fijos, buscar *t* para un %) sí converge — p. ej. 80% en ~35.55 min."
    )


def _logistic_fit_func(t: np.ndarray, L: float, k: float, t0: float) -> np.ndarray:
    return L / (1.0 + np.exp(-k * (t - t0)))


def try_logistic_curve_fit(df: pd.DataFrame) -> dict[str, Any]:
    """Intento de ajuste conjunto (Levenberg-Marquardt vía curve_fit)."""
    t = df["t_min"].to_numpy(dtype=float)
    y = df["level"].to_numpy(dtype=float)
    try:
        popt, _ = curve_fit(
            _logistic_fit_func,
            t,
            y,
            p0=[L_MAX, K_SEED, T0_SEED],
            bounds=([50.0, 0.01, 5.0], [100.0, 0.5, 60.0]),
            maxfev=8000,
        )
        L, k, t0 = map(float, popt)
        y_hat = _logistic_fit_func(t, L, k, t0)
        return {
            "ok": True,
            "L": L,
            "k": k,
            "t0": t0,
            "r2": r2_score(y, y_hat),
            "message": f"Ajuste convergió: k={k:.5f}, t₀={t0:.2f} min, R²={r2_score(y, y_hat):.4f}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "message": f"No convergió o matriz singular: {exc}",
        }


def report_fit_stats(df: pd.DataFrame) -> dict[str, float]:
    cmp = compare_models(df)
    return {
        "r2_logistic": cmp.r2_logistic,
        "r2_linear": cmp.r2_linear,
        "r2_spline": cmp.r2_spline,
        "n_samples": len(df),
        "t_max_min": float(df["t_min"].max()),
    }
