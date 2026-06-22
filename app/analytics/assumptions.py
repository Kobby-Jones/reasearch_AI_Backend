"""Deterministic statistical assumption checks.

Every test rests on assumptions; a defensible analysis states whether they hold.
These helpers run the standard checks and return structured, plain-language
results so the UI and report can show, for each test, what was checked, whether
it passed, and what to do if it did not. No AI is involved in any judgement.

Each check is a dict:
    {
      "name": str,            # e.g. "Normality of residuals"
      "test": str,            # e.g. "Shapiro-Wilk"
      "statistic": float|None,
      "p_value": float|None,
      "passed": bool|None,    # None when not determinable
      "severity": "ok"|"warning"|"info",
      "message": str,         # plain-language finding
      "recommendation": str,  # what to do if violated ("" if none)
    }
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from app.analytics._util import jsonable

_ALPHA = 0.05
_MAX_SHAPIRO = 5000  # Shapiro-Wilk is unreliable / slow on very large n


def _check(name, test, stat, p, passed, message, recommendation="") -> dict:
    severity = "ok" if passed else ("warning" if passed is False else "info")
    return {
        "name": name, "test": test,
        "statistic": None if stat is None else float(stat),
        "p_value": None if p is None else float(p),
        "passed": passed, "severity": severity,
        "message": message, "recommendation": recommendation,
    }


def _normality(values: np.ndarray, label: str) -> dict:
    vals = np.asarray(values, dtype=float)
    vals = vals[~np.isnan(vals)]
    n = len(vals)
    if n < 3:
        return _check(f"Normality ({label})", "Shapiro-Wilk", None, None, None,
                      "Too few observations to test normality.")
    try:
        if n <= _MAX_SHAPIRO:
            stat, p = stats.shapiro(vals)
            test = "Shapiro-Wilk"
        else:
            stat, p = stats.normaltest(vals)
            test = "D'Agostino-Pearson"
    except Exception:
        return _check(f"Normality ({label})", "Shapiro-Wilk", None, None, None,
                      "Normality could not be evaluated.")
    passed = bool(p >= _ALPHA)
    msg = (f"{label} appears normally distributed (p = {p:.3f})." if passed
           else f"{label} deviates from normality (p = {p:.3f}).")
    rec = "" if passed else "Consider a non-parametric alternative or a transformation."
    return _check(f"Normality ({label})", test, stat, p, passed, msg, rec)


# --- regression --------------------------------------------------------------
def regression_assumptions(model, x: pd.DataFrame, resid: np.ndarray, vif: dict) -> list[dict]:
    checks: list[dict] = []

    # 1. Normality of residuals
    checks.append(_normality(np.asarray(resid), "residuals"))

    # 2. Homoscedasticity (Breusch-Pagan)
    try:
        from statsmodels.stats.diagnostic import het_breuschpagan

        lm, lm_p, fval, f_p = het_breuschpagan(resid, x)
        passed = bool(lm_p >= _ALPHA)
        checks.append(_check(
            "Homoscedasticity", "Breusch-Pagan", lm, lm_p, passed,
            ("Residual variance is constant (p = %.3f)." % lm_p) if passed
            else ("Evidence of heteroscedasticity (p = %.3f)." % lm_p),
            "" if passed else "Consider robust (HC) standard errors or transforming the outcome.",
        ))
    except Exception:
        pass

    # 3. Independence of errors (Durbin-Watson)
    try:
        from statsmodels.stats.stattools import durbin_watson

        dw = float(durbin_watson(resid))
        ok = 1.5 <= dw <= 2.5
        checks.append(_check(
            "Independence of errors", "Durbin-Watson", dw, None, bool(ok),
            f"Durbin-Watson = {dw:.2f} ({'no' if ok else 'possible'} autocorrelation).",
            "" if ok else "Values far from 2 suggest autocorrelated residuals; check ordering or add lagged terms.",
        ))
    except Exception:
        pass

    # 4. Multicollinearity (max VIF)
    if vif:
        max_name, max_vif = max(vif.items(), key=lambda kv: (kv[1] if kv[1] is not None else 0))
        if max_vif is not None:
            ok = max_vif < 5
            sev_msg = (f"All VIFs acceptable (max {max_vif:.1f} for {max_name})." if ok
                       else f"High multicollinearity (VIF {max_vif:.1f} for {max_name}).")
            checks.append(_check(
                "Multicollinearity", "Variance Inflation Factor", max_vif, None, bool(ok),
                sev_msg,
                "" if ok else "Consider removing or combining correlated predictors.",
            ))

    return jsonable(checks)


# --- anova -------------------------------------------------------------------
def anova_assumptions(groups: list[np.ndarray], levene: dict | None) -> list[dict]:
    checks: list[dict] = []

    # Normality within each group (summarised)
    failed = []
    tested = 0
    for i, g in enumerate(groups):
        res = _normality(np.asarray(g, dtype=float), f"group {i + 1}")
        if res["passed"] is not None:
            tested += 1
            if res["passed"] is False:
                failed.append(res)
    if tested:
        ok = not failed
        checks.append(_check(
            "Normality within groups", "Shapiro-Wilk", None, None, ok,
            "Each group is approximately normal." if ok
            else f"{len(failed)} of {tested} groups deviate from normality.",
            "" if ok else "With non-normal groups, consider Kruskal-Wallis instead of ANOVA.",
        ))

    # Homogeneity of variance (Levene, already computed upstream)
    if levene and levene.get("p_value") is not None:
        p = float(levene["p_value"])
        ok = bool(p >= _ALPHA)
        checks.append(_check(
            "Homogeneity of variance", "Levene", levene.get("statistic"), p, ok,
            ("Group variances are comparable (p = %.3f)." % p) if ok
            else ("Group variances differ (p = %.3f)." % p),
            "" if ok else "Consider Welch's ANOVA, which does not assume equal variances.",
        ))

    return jsonable(checks)


# --- correlation -------------------------------------------------------------
def correlation_assumptions(df: pd.DataFrame, columns: list[str], method: str) -> list[dict]:
    checks: list[dict] = []
    if method != "pearson":
        checks.append(_check(
            "Distribution", "Spearman (rank-based)", None, None, True,
            "Spearman's correlation is rank-based and does not assume normality.",
        ))
        return jsonable(checks)

    failed = []
    tested = 0
    for col in columns:
        series = pd.to_numeric(df[col], errors="coerce")
        res = _normality(series.to_numpy(), col)
        if res["passed"] is not None:
            tested += 1
            if res["passed"] is False:
                failed.append(col)
    if tested:
        ok = not failed
        checks.append(_check(
            "Normality of variables", "Shapiro-Wilk", None, None, ok,
            "Variables are approximately normal, supporting Pearson's r." if ok
            else f"{len(failed)} variable(s) deviate from normality: {', '.join(failed[:4])}.",
            "" if ok else "Spearman's rank correlation is more appropriate for non-normal data.",
        ))
    return jsonable(checks)
