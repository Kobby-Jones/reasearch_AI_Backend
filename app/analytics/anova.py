from __future__ import annotations

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


def one_way_anova(df: pd.DataFrame, dependent: str, group_column: str) -> dict:
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
                "std": float(values.std(ddof=1)),
                "sem": float(values.std(ddof=1) / (len(values) ** 0.5)),
            }
        )

    if len(groups) < 2:
        raise ValueError("ANOVA requires at least two groups with >=2 observations.")

    f_stat, p_value = stats.f_oneway(*groups)
    eta = _eta_squared(groups)

    # Levene's test for homogeneity of variance (an ANOVA assumption).
    try:
        lev_stat, lev_p = stats.levene(*groups)
        levene = {"statistic": float(lev_stat), "p_value": float(lev_p),
                  "equal_variances": bool(lev_p >= 0.05)}
    except Exception:
        levene = None

    # Tukey HSD post-hoc (only meaningful when the omnibus test is significant).
    posthoc = []
    if p_value < 0.05 and len(groups) >= 2:
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
            "f_statistic": float(f_stat),
            "p_value": float(p_value),
            "significant": bool(p_value < 0.05),
            "eta_squared": eta,
            "effect_size": _interpret_eta(eta),
            "levene": levene,
            "group_summary": summary,
            "post_hoc": posthoc,
            "chart": {"labels": labels, "means": [s["mean"] for s in summary],
                      "errors": [s["std"] for s in summary]},
        }
    )
