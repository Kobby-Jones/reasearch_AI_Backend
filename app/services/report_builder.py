"""Turn deterministic analysis result dictionaries into document *table* blocks.

These helpers are intentionally pure: they take a ``results`` dict (exactly the
shape produced by :mod:`app.analytics`) and return a list of table blocks that
the document generator understands.  No statistics are computed here and no AI
is involved — the numbers are passed straight through from the analytics layer,
preserving the project's core principle that figures/tables come only from
deterministic computation while the AI writes the surrounding prose.

Block shapes consumed by :mod:`app.utils.document_generator`::

    {"type": "table", "title": str, "columns": [..], "rows": [[..], ..]}
    {"type": "paragraph", "text": str}
    {"type": "heading", "text": str, "level": int}
"""
from __future__ import annotations

from typing import Any


def _round(value: Any, ndigits: int = 3) -> Any:
    try:
        if value is None:
            return "—"
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return value


def _p(value: Any) -> str:
    """Format a p-value in the conventional APA manner."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v < 0.001:
        return "< .001"
    return f"{v:.3f}".lstrip("0") or "0"


def _sig(flag: Any) -> str:
    return "Yes" if flag else "No"


# ---------------------------------------------------------------------------
# per-analysis table builders
# ---------------------------------------------------------------------------
def reliability_tables(results: dict) -> list[dict]:
    constructs = results.get("constructs", {})
    if not constructs:
        return []
    rows = []
    for name, c in constructs.items():
        rows.append([
            name,
            c.get("n_items"),
            c.get("n_cases"),
            _round(c.get("alpha")),
            (c.get("interpretation") or "").title(),
        ])
    blocks: list[dict] = [{
        "type": "table",
        "title": "Reliability of measurement scales (Cronbach's alpha)",
        "columns": ["Construct", "Items", "N", "Cronbach's \u03b1", "Interpretation"],
        "rows": rows,
    }]

    # item-level diagnostics, only where it adds value (a scale that could improve)
    for name, c in constructs.items():
        diags = c.get("item_diagnostics") or []
        flagged = [d for d in diags if d.get("improves_scale")]
        if not flagged:
            continue
        drows = [
            [d.get("item"), _round(d.get("alpha_if_deleted")),
             "Removing improves \u03b1" if d.get("improves_scale") else ""]
            for d in diags
        ]
        blocks.append({
            "type": "table",
            "title": f"Item-total diagnostics for {name}",
            "columns": ["Item", "\u03b1 if item deleted", "Note"],
            "rows": drows,
        })
    return blocks


def descriptive_tables(results: dict) -> list[dict]:
    variables = results.get("variables", {})
    if not variables:
        return []
    rows = []
    for name, v in variables.items():
        rows.append([
            name,
            v.get("count"),
            _round(v.get("mean"), 2),
            _round(v.get("std"), 2),
            _round(v.get("min"), 2),
            _round(v.get("max"), 2),
            _round(v.get("skewness"), 2),
            _round(v.get("kurtosis"), 2),
        ])
    return [{
        "type": "table",
        "title": "Descriptive statistics of study variables",
        "columns": ["Variable", "N", "Mean", "SD", "Min", "Max", "Skew", "Kurtosis"],
        "rows": rows,
    }]


def frequency_tables(results: dict) -> list[dict]:
    variables = results.get("variables", {})
    blocks: list[dict] = []
    for name, v in variables.items():
        dist = v.get("distribution") or []
        rows = [[d.get("value"), d.get("count"), f"{_round(d.get('percent'), 1)}%"] for d in dist]
        total = sum((d.get("count") or 0) for d in dist)
        rows.append(["Total", total, "100.0%"])
        blocks.append({
            "type": "table",
            "title": f"Distribution of respondents by {name}",
            "columns": [name.title(), "Frequency", "Percent"],
            "rows": rows,
        })
    return blocks


def correlation_tables(results: dict) -> list[dict]:
    pairs = results.get("pairs", [])
    if not pairs:
        return []
    rows = []
    for p in pairs:
        rows.append([
            f"{p.get('variable_a')} \u2013 {p.get('variable_b')}",
            _round(p.get("coefficient")),
            _p(p.get("p_value")),
            _sig(p.get("significant")),
            (p.get("strength") or "").title(),
            (p.get("direction") or "").title(),
        ])
    method = (results.get("method") or "pearson").title()
    return [{
        "type": "table",
        "title": f"{method} correlations among study variables",
        "columns": ["Variable pair", "r", "p", "Sig.", "Strength", "Direction"],
        "rows": rows,
    }]


def regression_tables(results: dict) -> list[dict]:
    coeffs = results.get("coefficients", [])
    blocks: list[dict] = []

    # model summary
    summary_rows = [[
        _round(results.get("r_squared")),
        _round(results.get("adj_r_squared")),
        _round(results.get("f_statistic"), 2),
        _p(results.get("f_p_value")),
        _sig(results.get("model_significant")),
        _round(results.get("durbin_watson"), 2),
    ]]
    blocks.append({
        "type": "table",
        "title": (
            f"Regression model summary "
            f"(DV: {results.get('dependent', 'outcome')})"
        ),
        "columns": ["R\u00b2", "Adj. R\u00b2", "F", "p", "Sig.", "Durbin-Watson"],
        "rows": summary_rows,
    })

    if coeffs:
        rows = []
        for c in coeffs:
            rows.append([
                "(Constant)" if c.get("term") == "intercept" else c.get("term"),
                _round(c.get("coefficient")),
                _round(c.get("std_error")),
                _round(c.get("std_beta")) if c.get("std_beta") is not None else "—",
                _round(c.get("t_value"), 2),
                _p(c.get("p_value")),
                _round(c.get("vif"), 2) if c.get("vif") is not None else "—",
            ])
        blocks.append({
            "type": "table",
            "title": "Regression coefficients",
            "columns": ["Predictor", "B", "Std. Error", "\u03b2", "t", "p", "VIF"],
            "rows": rows,
        })
    return blocks


def anova_tables(results: dict) -> list[dict]:
    blocks: list[dict] = []
    groups = results.get("group_summary", [])
    if groups:
        rows = [[g.get("group"), g.get("n"), _round(g.get("mean"), 2),
                 _round(g.get("std"), 2)] for g in groups]
        blocks.append({
            "type": "table",
            "title": (
                f"Group descriptives for {results.get('dependent', 'outcome')} "
                f"by {results.get('group_column', 'group')}"
            ),
            "columns": ["Group", "N", "Mean", "SD"],
            "rows": rows,
        })

    anova_rows = [[
        _round(results.get("f_statistic"), 2),
        _p(results.get("p_value")),
        _sig(results.get("significant")),
        _round(results.get("eta_squared")),
        (results.get("effect_size") or "").title(),
    ]]
    blocks.append({
        "type": "table",
        "title": "Analysis of variance (ANOVA) results",
        "columns": ["F", "p", "Sig.", "\u03b7\u00b2", "Effect size"],
        "rows": anova_rows,
    })

    post = results.get("post_hoc") or []
    if post:
        prows = []
        for ph in post:
            prows.append([
                f"{ph.get('group_a')} \u2013 {ph.get('group_b')}",
                _round(ph.get("mean_diff"), 2),
                _p(ph.get("p_value")),
                _sig(ph.get("significant")),
            ])
        blocks.append({
            "type": "table",
            "title": "Post-hoc pairwise comparisons (Tukey HSD)",
            "columns": ["Comparison", "Mean diff.", "p", "Sig."],
            "rows": prows,
        })
    return blocks


def plspm_tables(results: dict) -> list[dict]:
    blocks: list[dict] = []

    # 1) measurement quality per construct
    quality = results.get("quality") or {}
    if quality:
        rows = []
        for lv, q in quality.items():
            rows.append([
                lv,
                q.get("n_indicators"),
                _round(q.get("cronbach_alpha")) if q.get("cronbach_alpha") is not None else "—",
                _round(q.get("composite_reliability")),
                _round(q.get("ave")),
            ])
        blocks.append({
            "type": "table",
            "title": "Measurement model quality (reliability and convergent validity)",
            "columns": ["Construct", "Items", "Cronbach's \u03b1", "Composite reliability", "AVE"],
            "rows": rows,
        })

    # 2) outer loadings
    outer = results.get("outer_model") or {}
    if outer:
        rows = []
        for lv, items in outer.items():
            for it in items:
                rows.append([lv, it.get("indicator"), _round(it.get("loading")),
                             _round(it.get("weight")), _round(it.get("communality"))])
        blocks.append({
            "type": "table",
            "title": "Outer model: indicator loadings and weights",
            "columns": ["Construct", "Indicator", "Loading", "Weight", "Communality"],
            "rows": rows,
        })

    # 3) inner (structural) model path coefficients with inference
    inner = results.get("inner_model") or {}
    for outcome, info in inner.items():
        rows = []
        for pred, pinfo in (info.get("predictors") or {}).items():
            rows.append([
                f"{pred} \u2192 {outcome}",
                _round(pinfo.get("path_coefficient")),
                _round(pinfo.get("std_error")) if pinfo.get("std_error") is not None else "—",
                _round(pinfo.get("t_value"), 2) if pinfo.get("t_value") is not None else "—",
                _p(pinfo.get("p_value")) if pinfo.get("p_value") is not None else "—",
                _sig(pinfo.get("significant")),
            ])
        blocks.append({
            "type": "table",
            "title": (
                f"Structural model path coefficients (DV: {outcome}; "
                f"R\u00b2 = {_round(info.get('r_squared'))})"
            ),
            "columns": ["Path", "\u03b2", "Std. Error", "t", "p", "Sig."],
            "rows": rows,
        })
    return blocks


def thematic_tables(results: dict) -> list[dict]:
    themes = results.get("themes") or []
    if not themes:
        return []
    rows = []
    for t in themes:
        quotes = t.get("quotes") or []
        sample = quotes[0] if quotes else ""
        if len(sample) > 140:
            sample = sample[:137] + "..."
        rows.append([
            t.get("name", ""),
            t.get("frequency", 0),
            f"{round(t.get('prevalence', 0) * 100)}%",
            f"\u201c{sample}\u201d" if sample else "\u2014",
        ])
    return [{
        "type": "table",
        "title": (
            f"Themes from thematic analysis "
            f"(n = {results.get('n_responses', 0)} responses, {results.get('n_themes', len(themes))} themes)"
        ),
        "columns": ["Theme", "Responses", "Prevalence", "Representative quote"],
        "rows": rows,
    }]


def synthesis_tables(results: dict) -> list[dict]:
    blocks: list[dict] = []
    themes = results.get("themes") or []
    if themes:
        rows = []
        for t in themes:
            cites = "; ".join(s.get("citation", "") for s in (t.get("sources") or [])[:6])
            synth = t.get("synthesis", "")
            if len(synth) > 200:
                synth = synth[:197] + "..."
            rows.append([t.get("name", ""), synth, cites or "\u2014"])
        blocks.append({
            "type": "table",
            "title": f"Synthesis matrix ({results.get('n_themes', len(themes))} themes across {results.get('n_sources', 0)} sources)",
            "columns": ["Theme", "What the literature shows", "Key sources"],
            "rows": rows,
        })
    gaps = results.get("gaps") or []
    if gaps:
        blocks.append({
            "type": "table",
            "title": "Identified research gaps",
            "columns": ["#", "Gap in the literature"],
            "rows": [[str(i + 1), g] for i, g in enumerate(gaps)],
        })
    return blocks


_TABLE_BUILDERS = {
    "reliability": reliability_tables,
    "descriptive": descriptive_tables,
    "frequency": frequency_tables,
    "correlation": correlation_tables,
    "regression": regression_tables,
    "anova": anova_tables,
    "plspm": plspm_tables,
    "thematic": thematic_tables,
    "synthesis": synthesis_tables,
}


def tables_for(analysis_type: str, results: dict) -> list[dict]:
    """Return the table blocks for a given analysis type (never raises)."""
    builder = _TABLE_BUILDERS.get(analysis_type)
    if not builder:
        return []
    try:
        return builder(results or {})
    except Exception:  # pragma: no cover - defensive: a bad result never breaks export
        return []


# ---------------------------------------------------------------------------
# ordering + human-readable section metadata for Chapter Four
# ---------------------------------------------------------------------------
# (analysis_type, section heading, narrative "beat" handed to the AI)
SECTION_PLAN: list[tuple[str, str, str]] = [
    ("reliability", "Reliability of Measurement Instruments",
     "the internal-consistency reliability of each construct and whether the scales were dependable enough for further analysis"),
    ("frequency", "Demographic Profile of Respondents",
     "the demographic composition of the sample and what it implies for the representativeness of the findings"),
    ("descriptive", "Descriptive Statistics of Study Variables",
     "the central tendency and spread of the main study variables and any notable patterns"),
    ("correlation", "Relationships Among Study Variables",
     "the bivariate relationships among the study variables and their relevance to the research objectives"),
    ("regression", "Predictive Modelling and Hypothesis Testing",
     "what the regression model reveals about the predictors of the outcome and the hypotheses being tested"),
    ("anova", "Group Comparisons",
     "whether groups differed significantly on the outcome and the practical meaning of any differences"),
    ("plspm", "Structural Model: Drivers of the Outcome",
     "what the partial least squares path model reveals about which latent constructs significantly drive the outcome, the strength and significance of each path, the variance explained, and how the measurement model's reliability and validity support these conclusions"),
    ("thematic", "Qualitative Findings: Themes",
     "the themes that emerged from the qualitative responses, how prevalent each was across participants, what each theme means, and how the representative quotations illustrate participants' lived perspectives, integrating these qualitative insights with the study's objectives"),
    ("synthesis", "Synthesis of the Literature",
     "how the body of retrieved literature organises into themes, what the sources within each theme collectively establish, where scholarship agrees or conflicts, and the research gaps the review reveals that motivate this study, citing the key sources for each theme"),
]
