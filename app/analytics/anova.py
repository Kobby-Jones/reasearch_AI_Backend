from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from app.analytics._util import jsonable, require_columns


def _eta_squared(groups: list) -> float | None:
    """Eta-squared effect size = SS_between / SS_total."""
    all_vals = pd.concat([pd.Series(g) for g in groups])
    grand_mean = all_vals.mean()
    ss_total = float(((all_vals - grand_mean) ** 2).sum())
    if ss_total == 0:
        return None
    ss_between = float(
        sum(len(g) * (pd.Series(g).mean() - grand_mean) ** 2 for g in groups)
    )
    return ss_between / ss_total


def _interpret_eta(eta: float | None) -> str:
    if eta is None:
        return "not computable"
    if eta < 0.01:
        return "negligible"
    if eta < 0.06:
        return "small"
    if eta < 0.14:
        return "medium"
    return "large"


def _welch_anova(groups: list[np.ndarray]) -> tuple[float, float, float, float]:
    """Welch's one-way ANOVA, robust to unequal group variances.

    Returns (F, p_value, df1, df2). Requires every group to have non-zero
    variance; the caller falls back to the standard test otherwise.
    """
    k = len(groups)
    n = np.array([len(g) for g in groups], dtype=float)
    means = np.array([g.mean() for g in groups], dtype=float)
    variances = np.array([g.var(ddof=1) for g in groups], dtype=float)

    w = n / variances
    w_sum = w.sum()
    weighted_mean = float((w * means).sum() / w_sum)

    numerator = float((w * (means - weighted_mean) ** 2).sum() / (k - 1))
    tmp = float((((1 - w / w_sum) ** 2) / (n - 1)).sum())
    denominator = 1.0 + (2.0 * (k - 2) / (k * k - 1)) * tmp

    f_stat = numerator / denominator
    df1 = float(k - 1)
    df2 = 1.0 / ((3.0 / (k * k - 1)) * tmp)
    p_value = float(stats.f.sf(f_stat, df1, df2))
    return f_stat, p_value, df1, df2


def one_way_anova(
    df: pd.DataFrame,
    dependent: str,
    group_column: str,
    variance: str = "standard",
    nonparametric: bool = False,
) -> dict:
    """Compare a numeric outcome across groups.

    `variance="welch"` uses Welch's ANOVA (no equal-variance assumption);
    `nonparametric=True` uses the rank-based Kruskal-Wallis test (no normality
    assumption). Both are the alternatives the assumption card recommends, so a
    failing check can be re-run directly with the appropriate method.
    """
    require_columns(df, [dependent, group_column])
    data = df[[dependent, group_column]].dropna().copy()
    data[dependent] = pd.to_numeric(data[dependent], errors="coerce")
    data = data.dropna()

    groups, summary, labels = [], [], []
    for name, chunk in data.groupby(group_column):
        values = chunk[dependent].astype(float)
        if len(values) < 2:
            continue
        groups.append(values.values)
        labels.append(jsonable(name))
        summary.append(
            {
                "group": jsonable(name),
                "n": int(len(values)),
                "mean": float(values.mean()),
                "median": float(values.median()),
                "std": float(values.std(ddof=1)),
                "sem": float(values.std(ddof=1) / (len(values) ** 0.5)),
            }
        )

    if len(groups) < 2:
        raise ValueError("ANOVA requires at least two groups with >=2 observations.")

    # Levene's test for homogeneity of variance (an ANOVA assumption). Computed
    # in every variant so the assumption card always shows whether it holds.
    try:
        lev_stat, lev_p = stats.levene(*groups)
        levene = {"statistic": float(lev_stat), "p_value": float(lev_p),
                  "equal_variances": bool(lev_p >= 0.05)}
    except Exception:
        levene = None

    # Welch requires a positive variance in every group; fall back transparently.
    use_welch = variance == "welch" and not nonparametric
    if use_welch and any(np.var(g, ddof=1) == 0 for g in groups):
        use_welch = False

    eta = _eta_squared(groups)
    epsilon_squared = None

    if nonparametric:
        h_stat, p_value = stats.kruskal(*groups)
        statistic = float(h_stat)
        n_total = sum(len(g) for g in groups)
        k = len(groups)
        epsilon_squared = (
            float((statistic - k + 1) / (n_total - k)) if n_total > k else None
        )
        result_extra = {
            "test": "Kruskal-Wallis",
            "method": "kruskal",
            "statistic_label": "H",
            "statistic": statistic,
            "f_statistic": None,
            "h_statistic": statistic,
            "df": None,
            "eta_squared": None,
            "epsilon_squared": epsilon_squared,
            "effect_size": _interpret_eta(epsilon_squared),
        }
    elif use_welch:
        f_stat, p_value, df1, df2 = _welch_anova(groups)
        statistic = float(f_stat)
        result_extra = {
            "test": "Welch's ANOVA",
            "method": "welch",
            "statistic_label": "F",
            "statistic": statistic,
            "f_statistic": statistic,
            "df": [df1, df2],
            "eta_squared": eta,
            "epsilon_squared": None,
            "effect_size": _interpret_eta(eta),
        }
    else:
        f_stat, p_value = stats.f_oneway(*groups)
        statistic = float(f_stat)
        result_extra = {
            "test": "One-way ANOVA",
            "method": "standard",
            "statistic_label": "F",
            "statistic": statistic,
            "f_statistic": statistic,
            "df": [float(len(groups) - 1), float(sum(len(g) for g in groups) - len(groups))],
            "eta_squared": eta,
            "epsilon_squared": None,
            "effect_size": _interpret_eta(eta),
        }

    p_value = float(p_value)

    from app.analytics.assumptions import anova_assumptions
    assumptions = anova_assumptions(
        groups, levene, variance="welch" if use_welch else variance,
        nonparametric=nonparametric,
    )

    # Post-hoc pairwise comparisons (only meaningful when the omnibus test is
    # significant). Tukey HSD assumes equal variances, so it is reported for the
    # parametric tests only; rank-based Kruskal-Wallis is left without it.
    posthoc = []
    if p_value < 0.05 and len(groups) >= 2 and not nonparametric:
        try:
            from statsmodels.stats.multicomp import pairwise_tukeyhsd

            tukey = pairwise_tukeyhsd(data[dependent].astype(float), data[group_column])
            for row in tukey.summary().data[1:]:
                posthoc.append(
                    {
                        "group_a": str(row[0]),
                        "group_b": str(row[1]),
                        "mean_diff": float(row[2]),
                        "p_adj": float(row[3]),
                        "lower": float(row[4]),
                        "upper": float(row[5]),
                        "significant": bool(str(row[6]) == "True"),
                    }
                )
        except Exception:
            posthoc = []

    return jsonable(
        {
            "dependent": dependent,
            "group_column": group_column,
            "k_groups": len(groups),
            "p_value": p_value,
            "significant": bool(p_value < 0.05),
            "levene": levene,
            "assumptions": assumptions,
            "group_summary": summary,
            "post_hoc": posthoc,
            "chart": {"labels": labels, "means": [s["mean"] for s in summary],
                      "errors": [s["std"] for s in summary]},
            **result_extra,
        }
    )
