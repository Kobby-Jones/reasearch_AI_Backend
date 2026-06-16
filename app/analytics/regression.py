from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.analytics._util import jsonable, require_columns


def _interpret_r2(r2: float) -> str:
    if r2 < 0.02:
        return "negligible explanatory power"
    if r2 < 0.13:
        return "small explanatory power"
    if r2 < 0.26:
        return "moderate explanatory power"
    return "substantial explanatory power"


def linear_regression(
    df: pd.DataFrame, dependent: str, independents: list[str]
) -> dict:
    if not dependent or not independents:
        raise ValueError("Regression requires a dependent variable and >=1 independent.")
    require_columns(df, [dependent, *independents])

    data = df[[dependent, *independents]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(data) <= len(independents) + 1:
        raise ValueError("Not enough complete observations for regression.")

    y = data[dependent].astype(float)
    x = sm.add_constant(data[independents].astype(float))
    model = sm.OLS(y, x).fit()

    # Standardised (beta) coefficients for comparing predictor importance.
    z = data[[dependent, *independents]].astype(float)
    z = (z - z.mean()) / z.std(ddof=1)
    try:
        std_model = sm.OLS(z[dependent], sm.add_constant(z[independents])).fit()
        std_betas = {name: float(std_model.params.get(name, float("nan"))) for name in independents}
    except Exception:
        std_betas = {name: None for name in independents}

    # Variance inflation factors (multicollinearity check).
    vif = {}
    try:
        from statsmodels.stats.outliers_influence import variance_inflation_factor

        xv = x.values
        for i, name in enumerate(x.columns):
            if name == "const":
                continue
            vif[name] = float(variance_inflation_factor(xv, i))
    except Exception:
        vif = {}

    coeffs = []
    for name in x.columns:
        term = "intercept" if name == "const" else name
        coeffs.append(
            {
                "term": term,
                "coefficient": float(model.params[name]),
                "std_error": float(model.bse[name]),
                "t_value": float(model.tvalues[name]),
                "p_value": float(model.pvalues[name]),
                "significant": bool(model.pvalues[name] < 0.05),
                "std_beta": std_betas.get(name) if name != "const" else None,
                "vif": vif.get(name) if name != "const" else None,
            }
        )

    try:
        dw = float(sm.stats.stattools.durbin_watson(model.resid))
    except Exception:
        dw = None

    return jsonable(
        {
            "dependent": dependent,
            "independents": independents,
            "n": int(len(data)),
            "r_squared": float(model.rsquared),
            "adj_r_squared": float(model.rsquared_adj),
            "explanatory_power": _interpret_r2(float(model.rsquared)),
            "f_statistic": float(model.fvalue) if model.fvalue is not None else None,
            "f_p_value": float(model.f_pvalue) if model.f_pvalue is not None else None,
            "model_significant": bool(model.f_pvalue is not None and model.f_pvalue < 0.05),
            "durbin_watson": dw,
            "coefficients": coeffs,
            "equation": _equation(dependent, model),
        }
    )


def _equation(dependent: str, model) -> str:
    parts = []
    for name in model.params.index:
        c = model.params[name]
        if name == "const":
            parts.append(f"{c:.3f}")
        else:
            sign = "+" if c >= 0 else "-"
            parts.append(f"{sign} {abs(c):.3f}·{name}")
    return f"{dependent} = " + " ".join(parts)
