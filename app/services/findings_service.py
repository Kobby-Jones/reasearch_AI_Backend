"""Hypothesis -> test -> verdict.

For each declared hypothesis, find the analysis that tests it among the results
already computed by the deterministic engine, extract the decisive statistic and
effect size, and return an explicit verdict (supported / not supported / not
tested) with the exact numbers and any assumption caveat. No AI decides a
verdict; this is pure statistics matched against the user's hypotheses.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.dataset_repository import DatasetRepository
from app.services.auto_analysis_service import _COMPOSITE_SUFFIX, _slug
from app.services.research_service import ResearchService
from app.utils.dataset_loader import load_dataframe

_NEG_WORDS = ("negative", "negatively", "inverse", "inversely", "reduce", "reduces",
              "decrease", "decreases", "lower", "lowers", "less", "weaken")
_DIFF_WORDS = ("differ", "difference", "differs", "vary", "varies", "variation",
               "across", "between groups", "group difference")
_CORR_WORDS = ("relationship", "associate", "associated", "association", "correlat",
               "related to", "linked")
_EFFECT_WORDS = ("predict", "affect", "influence", "impact", "effect", "determinant",
                 "drives", "leads to", "contribute", "explain")


def _label_and_text(h) -> tuple[str, str]:
    if isinstance(h, dict):
        return str(h.get("label") or ""), str(h.get("text") or h.get("statement") or "")
    s = str(h).strip()
    m = re.match(r"^\s*(H\d+[a-z]?)\s*[:.\-]\s*(.+)$", s, re.I)
    if m:
        return m.group(1).upper(), m.group(2).strip()
    return "", s


def _effect_size_label(kind: str, value: float | None) -> str:
    if value is None:
        return ""
    a = abs(value)
    if kind == "beta" or kind == "r":
        return "large" if a >= 0.5 else "moderate" if a >= 0.3 else "small" if a >= 0.1 else "negligible"
    if kind == "eta" or kind == "epsilon":
        return "large" if a >= 0.14 else "moderate" if a >= 0.06 else "small" if a >= 0.01 else "negligible"
    return ""


def _first_failed_assumption(results: dict) -> str | None:
    for c in (results or {}).get("assumptions", []) or []:
        if c.get("passed") is False:
            return c.get("message") or c.get("name")
    return None


class FindingsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.research = ResearchService(db)
        self.datasets = DatasetRepository(db)
        self.results = AnalysisRepository(db)

    def compute(self, user_id: int, project_id: int, dataset_id: int) -> dict:
        project = self.research.get_owned(project_id, user_id)
        dataset = self.datasets.get(dataset_id)
        if not dataset or dataset.project_id != project.id:
            raise NotFoundError("Dataset not found for this project.")

        hypotheses = project.hypotheses or []
        if not hypotheses:
            raise ValidationError("This project has no stated hypotheses to test.")

        # construct name <-> composite column map (mirrors the auto-analysis run)
        from app.services.auto_analysis_service import AutoAnalysisService

        df = load_dataframe(dataset.storage_path)
        constructs, demographics = AutoAnalysisService(self.db)._mapping(project, df)
        name_to_col = {name: f"{_slug(name)}{_COMPOSITE_SUFFIX}" for name in constructs}
        col_to_name = {v: k for k, v in name_to_col.items()}
        construct_names = sorted(constructs.keys(), key=len, reverse=True)
        demo_names = sorted((demographics or []), key=len, reverse=True)

        analyses = self.results.list_for_dataset(dataset.id, limit=200, offset=0)
        regressions = [a for a in analyses if a.analysis_type == "regression"]
        correlations = [a for a in analyses if a.analysis_type == "correlation"]
        anovas = [a for a in analyses if a.analysis_type == "anova"]
        has_any = bool(regressions or correlations or anovas)

        findings = []
        for h in hypotheses:
            label, text = _label_and_text(h)
            findings.append(self._evaluate(
                label, text, construct_names, demo_names, name_to_col, col_to_name,
                regressions, correlations, anovas, has_any,
            ))

        counts = {"supported": 0, "not_supported": 0, "not_tested": 0}
        for f in findings:
            counts[f["verdict"]] = counts.get(f["verdict"], 0) + 1

        return {
            "project_id": project.id,
            "dataset_id": dataset.id,
            "total": len(findings),
            "summary": counts,
            "findings": findings,
            "analyses_present": has_any,
        }

    # ------------------------------------------------------------------ matching
    def _mentions(self, text: str, names: list[str]) -> list[str]:
        low = text.lower()
        found: list[str] = []
        for n in names:
            if n and n.lower() in low and n not in found:
                found.append(n)
        return found

    def _evaluate(self, label, text, construct_names, demo_names, name_to_col,
                  col_to_name, regressions, correlations, anovas, has_any) -> dict:
        low = text.lower()
        mentioned = self._mentions(text, construct_names)
        demos = self._mentions(text, demo_names)
        expects_negative = any(w in low for w in _NEG_WORDS)
        base = {"label": label, "text": text, "expected_direction":
                "negative" if expects_negative else "positive"}

        is_diff = any(w in low for w in _DIFF_WORDS) or bool(demos)
        is_corr = any(w in low for w in _CORR_WORDS)
        is_effect = any(w in low for w in _EFFECT_WORDS)

        # 1) group difference -> ANOVA (dependent construct across a demographic)
        if is_diff and mentioned and demos:
            dep_col = name_to_col.get(mentioned[0])
            for g in demos:
                hit = self._find_anova(anovas, dep_col, g)
                if hit:
                    return {**base, **hit}

        # 2) relationship -> correlation pair
        if is_corr and len(mentioned) >= 2 and not is_effect:
            hit = self._find_correlation(correlations, name_to_col.get(mentioned[0]),
                                         name_to_col.get(mentioned[1]), expects_negative)
            if hit:
                return {**base, **hit}

        # 3) predictive effect -> regression coefficient
        if mentioned:
            hit = self._find_regression(regressions, mentioned, name_to_col, expects_negative)
            if hit:
                return {**base, **hit}
            # fall back to correlation if a pair is available
            if len(mentioned) >= 2:
                hit = self._find_correlation(correlations, name_to_col.get(mentioned[0]),
                                             name_to_col.get(mentioned[1]), expects_negative)
                if hit:
                    return {**base, **hit}

        # not auto-testable
        reason = ("Run the analysis to test this hypothesis." if not has_any
                  else "Could not automatically match this hypothesis to a computed test. "
                       "Check that its variables match your constructs, or test it manually.")
        return {**base, "verdict": "not_tested", "test": None, "statistic": None,
                "p_value": None, "effect_size": None, "caveat": None, "note": reason}

    def _verdict(self, significant: bool, sign_positive: bool, expects_negative: bool) -> str:
        if not significant:
            return "not_supported"
        if expects_negative and sign_positive:
            return "not_supported"
        if (not expects_negative) and (not sign_positive):
            return "not_supported"
        return "supported"

    def _find_regression(self, regressions, mentioned, name_to_col, expects_negative):
        cols = {name_to_col.get(m) for m in mentioned}
        for a in regressions:
            res = a.results or {}
            dep = res.get("dependent")
            if dep not in cols:
                continue
            for coef in res.get("coefficients", []):
                term = coef.get("term")
                if term in cols and term != dep:
                    beta = coef.get("std_beta")
                    val = beta if beta is not None else coef.get("coefficient")
                    sig = bool(coef.get("significant"))
                    sign_pos = (val or 0) >= 0
                    stat = (f"β = {beta:.2f}, p = {coef['p_value']:.3f}" if beta is not None
                            else f"b = {coef['coefficient']:.2f}, p = {coef['p_value']:.3f}")
                    return {
                        "verdict": self._verdict(sig, sign_pos, expects_negative),
                        "test": "Multiple regression",
                        "statistic": stat,
                        "p_value": coef.get("p_value"),
                        "effect_size": _effect_size_label("beta", val),
                        "observed_direction": "positive" if sign_pos else "negative",
                        "caveat": _first_failed_assumption(res),
                        "analysis_id": a.id,
                    }
        return None

    def _find_correlation(self, correlations, col_a, col_b, expects_negative):
        if not col_a or not col_b:
            return None
        for a in correlations:
            res = a.results or {}
            method = (res.get("method") or "pearson").lower()
            test_label = "Spearman correlation" if method == "spearman" else "Pearson correlation"
            stat_symbol = "ρ" if method == "spearman" else "r"
            for pair in res.get("pairs", []):
                va, vb = pair.get("variable_a"), pair.get("variable_b")
                if {va, vb} == {col_a, col_b}:
                    sig = bool(pair.get("significant"))
                    sign_pos = pair.get("direction") != "negative"
                    return {
                        "verdict": self._verdict(sig, sign_pos, expects_negative),
                        "test": test_label,
                        "statistic": f"{stat_symbol} = {pair['coefficient']:.2f}, p = {pair['p_value']:.3f}",
                        "p_value": pair.get("p_value"),
                        "effect_size": pair.get("strength"),
                        "observed_direction": pair.get("direction"),
                        "caveat": _first_failed_assumption(a.results),
                        "analysis_id": a.id,
                    }
        return None

    def _find_anova(self, anovas, dep_col, group_col):
        if not dep_col:
            return None
        for a in anovas:
            res = a.results or {}
            if res.get("dependent") == dep_col and res.get("group_column") == group_col:
                sig = bool(res.get("significant"))
                eff = res.get("eta_squared")
                eff_kind = "eta"
                if eff is None and res.get("epsilon_squared") is not None:
                    eff = res.get("epsilon_squared")
                    eff_kind = "epsilon"
                test_name = res.get("test", "One-way ANOVA")
                stat_label = res.get("statistic_label", "F")
                stat_value = res.get("statistic", res.get("f_statistic"))
                eff_symbol = "ε²" if eff_kind == "epsilon" else "η²"
                stat_str = (
                    f"{stat_label} = {stat_value:.2f}, p = {res.get('p_value'):.3f}"
                    if stat_value is not None else f"p = {res.get('p_value'):.3f}"
                )
                if eff is not None:
                    stat_str += f", {eff_symbol} = {eff:.2f}"
                return {
                    "verdict": "supported" if sig else "not_supported",
                    "test": f"{test_name} (by {group_col})",
                    "statistic": stat_str,
                    "p_value": res.get("p_value"),
                    "effect_size": _effect_size_label(eff_kind, eff),
                    "observed_direction": None,
                    "caveat": _first_failed_assumption(res),
                    "analysis_id": a.id,
                }
        return None
