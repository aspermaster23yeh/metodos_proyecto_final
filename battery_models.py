"""Modelos numéricos alineados al reporte: logístico, spline y Newton-Raphson."""
# Docstring del módulo: implementa los métodos matemáticos del proyecto (regresión, ajuste y raíces).

from __future__ import annotations
# Habilita anotaciones de tipo modernas para versiones anteriores de Python.

from dataclasses import dataclass
# Importa el decorador @dataclass para crear clases ligeras (estructuras de datos).
from typing import Any
# Tipo genérico utilizado en diccionarios con valores heterogéneos.

import numpy as np
# NumPy: librería para cálculo numérico con arrays (operaciones vectorizadas).
import pandas as pd
# Pandas: librería para manejo de DataFrames (tablas) y series.
from scipy.interpolate import UnivariateSpline
# Función para construir splines (curvas suaves) que interpolan los datos medidos.
from scipy.optimize import curve_fit, newton
# `curve_fit`: ajuste no lineal (Levenberg-Marquardt). `newton`: método de Newton-Raphson.

from report_data import K_RATE, K_SEED, L_MAX, T0_INFL, T0_SEED
# Importa los parámetros del modelo (k, t₀, L) y las semillas iniciales para los ajustes.


def logistic_c(t_min: float | np.ndarray, k: float = K_RATE, t0: float = T0_INFL, L: float = L_MAX) -> np.ndarray:
    # Calcula el % de carga C(t) en función del tiempo usando la curva logística (sigmoide).
    t = np.asarray(t_min, dtype=float)
    # Asegura que `t` sea un array NumPy de tipo float (acepta escalares y listas).
    return L / (1.0 + np.exp(-k * (t - t0)))
    # Fórmula sigmoide: C(t) = L / (1 + e^{-k(t-t₀)}). Devuelve el % de carga predicho.


def logistic_c_prime(t_min: float, k: float = K_RATE, t0: float = T0_INFL, L: float = L_MAX) -> float:
    # Calcula la derivada C'(t) del modelo logístico — necesaria para Newton-Raphson.
    e = np.exp(-k * (t_min - t0))
    # Pre-calcula e^{-k(t-t₀)} para evitar calcularlo dos veces.
    return float(L * k * e / (1.0 + e) ** 2)
    # Derivada analítica de la sigmoide: L*k*e / (1+e)^2.


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    # Calcula el coeficiente de determinación R² (qué tan bien el modelo explica los datos).
    y = np.asarray(y_true, dtype=float)
    # Valores reales medidos.
    yh = np.asarray(y_pred, dtype=float)
    # Valores predichos por el modelo.
    ss_res = float(np.sum((y - yh) ** 2))
    # Suma de cuadrados de los residuos (errores del modelo).
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    # Suma total de cuadrados (varianza de los datos respecto a su media).
    return 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
    # R² = 1 - (SS_res/SS_tot). Si SS_tot es 0 (todos los datos iguales), devuelve 1.


def linear_predict(t_min: np.ndarray, coef: np.ndarray) -> np.ndarray:
    # Evalúa un polinomio (en este caso recta) con los coeficientes dados.
    return np.polyval(coef, t_min)
    # `np.polyval` aplica los coeficientes; con coef=[m, b] calcula y = m*t + b.


def _fit_spline_on_samples(t_min: np.ndarray, levels: np.ndarray) -> UnivariateSpline:
    # Función privada: ajusta un spline a las muestras (tiempo, %).
    t_h = t_min / 60.0
    # Convierte el tiempo a horas (mejor escala para el ajuste numérico).
    n = t_min.size
    # Número de muestras.
    k = int(min(3, max(1, n - 1)))
    # Grado del spline: máximo 3 (cúbico), mínimo 1 (lineal), limitado por # de muestras.
    s = max(0.0, (n * float(np.var(levels))) * 0.05) if n >= 4 else 0.0
    # Parámetro de suavizado: depende de la varianza; 0 si hay pocas muestras (interpolación exacta).
    return UnivariateSpline(t_h, levels, k=k, s=s)
    # Devuelve el spline ajustado, listo para evaluar en cualquier t.


@dataclass
class ModelComparison:
    # Estructura que agrupa los resultados de comparar 3 modelos sobre los mismos datos.
    r2_linear: float
    # R² del ajuste lineal.
    r2_logistic: float
    # R² del modelo logístico (sigmoide).
    r2_spline: float
    # R² del spline.
    t_grid: np.ndarray
    # Vector de tiempos densos para dibujar las curvas continuas.
    y_linear: np.ndarray
    # Valores de la recta evaluada en `t_grid`.
    y_logistic: np.ndarray
    # Valores de la sigmoide evaluada en `t_grid`.
    y_spline: np.ndarray
    # Valores del spline evaluado en `t_grid`.
    linear_coef: np.ndarray
    # Coeficientes [m, b] de la recta ajustada.
    t_cv_min: float | None
    # Tiempo en que se cruza el 80% (inicio aproximado de fase CV); None si no se alcanza.


def compare_models(df: pd.DataFrame, threshold_cv: float = 80.0) -> ModelComparison:
    # Ajusta y compara los 3 modelos (lineal, logístico, spline) sobre las muestras.
    t = df["t_min"].to_numpy(dtype=float)
    # Tiempos (en minutos) como array NumPy.
    y = df["level"].to_numpy(dtype=float)
    # Porcentajes de carga como array NumPy.
    coef = np.polyfit(t, y, 1)
    # Ajuste lineal de grado 1: devuelve [pendiente, intersección].
    y_lin_obs = linear_predict(t, coef)
    # Predicciones del modelo lineal en los puntos observados.
    y_log_obs = logistic_c(t)
    # Predicciones del modelo logístico (parámetros fijos del reporte) en los puntos observados.
    sp = _fit_spline_on_samples(t, y)
    # Ajusta el spline a las muestras.
    y_sp_obs = sp(t / 60.0)
    # Predicciones del spline (ojo: en horas, no en minutos).

    t_grid = np.linspace(float(t.min()), max(float(t.max()), 1.0), 200)
    # Vector denso de 200 tiempos entre el mínimo y máximo observados (para curvas suaves).
    y_linear = linear_predict(t_grid, coef)
    # Recta evaluada en el grid denso.
    y_logistic = logistic_c(t_grid)
    # Sigmoide evaluada en el grid denso.
    y_spline = sp(t_grid / 60.0)
    # Spline evaluado en el grid denso.

    return ModelComparison(
        # Devuelve la estructura con todos los resultados de la comparación.
        r2_linear=r2_score(y, y_lin_obs),
        # R² del modelo lineal.
        r2_logistic=r2_score(y, y_log_obs),
        # R² del modelo logístico.
        r2_spline=r2_score(y, y_sp_obs),
        # R² del spline.
        t_grid=t_grid,
        y_linear=y_linear,
        y_logistic=y_logistic,
        y_spline=y_spline,
        linear_coef=coef,
        t_cv_min=estimate_cv_start_min(df, threshold_cv),
        # Calcula también el inicio de la fase CV (cruce del 80%).
    )


def estimate_cv_start_min(df: pd.DataFrame, threshold: float = 80.0) -> float | None:
    """Primer instante (min) en que la carga alcanza el umbral — interpolación lineal."""
    # Docstring: explica que se busca dónde se cruza un % objetivo.
    d = df.sort_values("t_min")
    # Ordena las muestras por tiempo ascendente (por seguridad).
    t = d["t_min"].to_numpy(dtype=float)
    # Tiempos ordenados.
    y = d["level"].to_numpy(dtype=float)
    # Porcentajes ordenados.
    for i in range(1, len(y)):
        # Recorre las muestras buscando el primer cruce del umbral.
        if y[i - 1] < threshold <= y[i]:
            # Si el valor anterior está por debajo y el actual por encima/igual al umbral...
            if y[i] == y[i - 1]:
                return float(t[i])
                # Caso degenerado (no debería pasar): devuelve el tiempo actual.
            frac = (threshold - y[i - 1]) / (y[i] - y[i - 1])
            # Calcula la fracción de interpolación lineal entre los dos puntos.
            return float(t[i - 1] + frac * (t[i] - t[i - 1]))
            # Devuelve el tiempo interpolado donde se cruza el umbral.
    if len(y) and y[-1] >= threshold:
        # Si el cruce no se detectó pero el último punto ya superó el umbral...
        return float(t[-1])
        # ...devuelve el último tiempo.
    return None
    # Si nunca se alcanza el umbral, devuelve None.


def comparison_verdict_es(cmp: ModelComparison) -> str:
    # Construye un texto explicativo en español sobre qué modelo encajó mejor.
    scores = {
        # Diccionario nombre→R² para comparar los modelos.
        "Lineal": cmp.r2_linear,
        "Logístico": cmp.r2_logistic,
        "Spline": cmp.r2_spline,
    }
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    # Modelo con el R² más alto.
    best_r2 = scores[best]
    # R² del mejor modelo.
    second = sorted(scores.values(), reverse=True)[1]
    # Segundo R² más alto (para medir la ventaja).
    delta = best_r2 - second
    # Diferencia de R² entre el mejor y el segundo (cuán claro es el ganador).

    if best == "Logístico":
        # Explicación específica si gana la sigmoide.
        why = (
            "La curva logística captura la **saturación hacia 100%** y el cambio de ritmo "
            "entre la fase **CC** (subida más rápida) y la **CV** (tramo final más lento), "
            "algo que una recta no puede representar."
        )
    elif best == "Spline":
        # Explicación específica si gana el spline.
        why = (
            "El spline se adapta punto a punto con gran flexibilidad; es útil para visualizar "
            "la serie medida, aunque tiene menos interpretación física que la sigmoide."
        )
    else:
        # Caso restante: gana el modelo lineal.
        why = (
            "En este tramo la recta parece competir con la sigmoide, pero extrapolar "
            "más allá del experimento sobreestimaría la velocidad de carga."
        )

    return (
        # Devuelve el veredicto formateado en Markdown con el mejor modelo y la explicación.
        f"El modelo con mayor **R²** es **{best}** ({best_r2:.4f}), "
        f"por encima del siguiente en ≈{delta:.4f}. {why}"
    )


def device_summary(df: pd.DataFrame) -> dict[str, float | int | None]:
    # Devuelve un resumen estadístico de un dispositivo (R², pendiente inicial, tiempo total).
    stats = report_fit_stats(df)
    # Reusa la función de estadísticas para los R² y la duración.
    d0 = df[df["t_min"] == 0]
    # Fila correspondiente al tiempo 0 (si existe).
    d5 = df[df["t_min"] == 5]
    # Fila correspondiente al tiempo 5 min.
    slope = None
    # Inicializa la pendiente como None por si no se puede calcular.
    if not d0.empty and not d5.empty:
        # Solo calcula la pendiente si existen ambos puntos.
        slope = (float(d5["level"].iloc[0]) - float(d0["level"].iloc[0])) / 5.0
        # Pendiente inicial = (nivel_5min - nivel_0min) / 5 → %/min.
    return {
        # Combina las estadísticas base con los nuevos campos.
        **stats,
        "initial_slope_pct_per_min": slope,
        # Pendiente inicial (qué tan rápido carga al principio).
        "t_100_min": float(df["t_min"].max()),
        # Tiempo en que termina el experimento (último valor de t_min).
        "final_level": float(df["level"].iloc[-1]),
        # Carga final alcanzada.
    }


def newton_time_for_target(
    # Calcula el tiempo en que la carga alcanza un porcentaje objetivo, usando Newton-Raphson.
    target_pct: float,
    # Porcentaje objetivo (p. ej. 80%).
    t_init_min: float = 26.0,
    # Tiempo inicial (semilla) en minutos — se elige cerca del punto de inflexión.
    tol: float = 1e-8,
    # Tolerancia: si |Δt| < tol, se considera convergido.
    maxiter: int = 50,
    # Número máximo de iteraciones para evitar bucles infinitos.
) -> tuple[float | None, str, list[dict]]:
    """Newton-Raphson escalar: C(t) - target = 0 (t en minutos)."""
    # Docstring: explica que resolvemos C(t) = target despejando t.

    def f(t: float) -> float:
        # Función f(t) = C(t) - target cuya raíz queremos encontrar.
        return float(logistic_c(t) - target_pct)

    def fp(t: float) -> float:
        # Derivada f'(t) = C'(t) (la del modelo logístico).
        return logistic_c_prime(t)

    steps: list[dict] = []
    # Lista donde guardamos el detalle de cada iteración (para mostrar en tabla).
    t = float(t_init_min)
    # Inicia con la semilla.
    for n in range(maxiter):
        # Bucle de Newton-Raphson hasta `maxiter`.
        ft = f(t)
        # Valor actual de f(t).
        fpt = fp(t)
        # Valor actual de la derivada f'(t).
        if abs(fpt) < 1e-14:
            # Si la derivada es prácticamente cero, no podemos dividir → detenemos.
            return None, "Derivada casi cero — detenido", steps
        t_new = t - ft / fpt
        # Fórmula iterativa de Newton: t_{n+1} = t_n - f(t_n)/f'(t_n).
        delta = abs(t_new - t)
        # Cambio entre iteraciones (criterio de convergencia).
        steps.append({"n": n, "t": t, "f": ft, "fp": fpt, "t_new": t_new, "delta": delta})
        # Guarda la iteración n con sus valores intermedios.
        t = t_new
        # Actualiza t para la siguiente iteración.
        if delta < tol:
            # Si el cambio es menor a la tolerancia, hemos convergido.
            return float(t), f"Convergió en {n + 1} iteraciones", steps
    return float(t), "Máximo de iteraciones alcanzado", steps
    # Si salimos del bucle sin converger, devolvemos el último valor y un mensaje de aviso.


def format_newton_steps(steps: list[dict]) -> pd.DataFrame:
    # Convierte las iteraciones de Newton en un DataFrame con columnas en español.
    if not steps:
        return pd.DataFrame()
        # Si no hay pasos, devuelve un DataFrame vacío.
    return pd.DataFrame(steps).rename(
        # Renombra las columnas internas a etiquetas legibles para el usuario.
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
    # Convierte minutos decimales (p. ej. 35.55) a formato "mm:ss" (p. ej. "35:33").
    mm = int(t_min)
    # Parte entera = minutos.
    ss = int(round((t_min - mm) * 60))
    # Parte decimal × 60 = segundos.
    return f"{mm}:{ss:02d}"
    # Formato con dos dígitos para los segundos.


def newton_batch_table(targets: list[int]) -> pd.DataFrame:
    # Corre Newton-Raphson para una lista de % objetivos y devuelve la tabla de resultados.
    rows: list[dict[str, Any]] = []
    # Acumulador de filas.
    for pct in targets:
        # Itera sobre cada porcentaje objetivo.
        t_star, msg, steps = newton_time_for_target(float(pct))
        # Resuelve Newton para ese porcentaje.
        rows.append(
            # Añade una fila con los resultados de esta meta.
            {
                "% objetivo": pct,
                "t* (min)": round(t_star, 4) if t_star is not None else None,
                # Tiempo solución redondeado, o None si no converge.
                "Tiempo": _minutes_to_mmss(t_star) if t_star is not None else "—",
                # Mismo tiempo en formato mm:ss.
                "Iteraciones": len(steps),
                # Cuántas iteraciones necesitó.
                "Estado": msg,
                # Mensaje de estado ("Convergió en N iteraciones" o aviso).
                "Convergió": "Sí" if t_star is not None and steps and steps[-1]["delta"] < 1e-6 else "Parcial",
                # Indicador binario: "Sí" si el último delta fue muy chico; "Parcial" en caso contrario.
            }
        )
    return pd.DataFrame(rows)
    # Devuelve toda la tabla como DataFrame.


def multivar_fit_note() -> str:
    # Devuelve un texto explicativo sobre por qué falló el ajuste multivariable de k y t₀.
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
    # Versión paramétrica de la sigmoide usada por `curve_fit` (L, k, t₀ se ajustan, no son fijos).
    return L / (1.0 + np.exp(-k * (t - t0)))


def try_logistic_curve_fit(df: pd.DataFrame) -> dict[str, Any]:
    """Intento de ajuste conjunto (Levenberg-Marquardt vía curve_fit)."""
    # Docstring: intenta el ajuste que falló en el reporte, ahora con un método más robusto.
    t = df["t_min"].to_numpy(dtype=float)
    # Tiempos como array.
    y = df["level"].to_numpy(dtype=float)
    # Porcentajes como array.
    try:
        popt, _ = curve_fit(
            # `curve_fit` minimiza por mínimos cuadrados (algoritmo Levenberg-Marquardt).
            _logistic_fit_func,
            # Función paramétrica a ajustar.
            t,
            y,
            # Datos x e y.
            p0=[L_MAX, K_SEED, T0_SEED],
            # Semillas iniciales: L=100, k≈0.1139, t₀≈21.71.
            bounds=([50.0, 0.01, 5.0], [100.0, 0.5, 60.0]),
            # Cotas inferior y superior de cada parámetro para evitar divergencia.
            maxfev=8000,
            # Máximo número de evaluaciones de la función.
        )
        L, k, t0 = map(float, popt)
        # Desempaqueta los parámetros óptimos encontrados.
        y_hat = _logistic_fit_func(t, L, k, t0)
        # Calcula las predicciones con los parámetros ajustados.
        return {
            # Devuelve un diccionario con el éxito y los parámetros encontrados.
            "ok": True,
            "L": L,
            "k": k,
            "t0": t0,
            "r2": r2_score(y, y_hat),
            "message": f"Ajuste convergió: k={k:.5f}, t₀={t0:.2f} min, R²={r2_score(y, y_hat):.4f}",
        }
    except Exception as exc:  # noqa: BLE001
        # Si el ajuste falla (matriz singular, divergencia, etc.), captura la excepción.
        return {
            "ok": False,
            "message": f"No convergió o matriz singular: {exc}",
        }


def report_fit_stats(df: pd.DataFrame) -> dict[str, float]:
    # Devuelve estadísticas resumidas del ajuste (R² y conteos) para mostrar en el dashboard.
    cmp = compare_models(df)
    # Reutiliza la comparación de modelos.
    return {
        "r2_logistic": cmp.r2_logistic,
        # R² del modelo logístico.
        "r2_linear": cmp.r2_linear,
        # R² del modelo lineal.
        "r2_spline": cmp.r2_spline,
        # R² del spline.
        "n_samples": len(df),
        # Número de muestras.
        "t_max_min": float(df["t_min"].max()),
        # Duración total del experimento.
    }
