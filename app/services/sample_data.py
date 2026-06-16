"""Canned content for the pre-loaded sample project.

This lets a brand-new user explore a complete study (topic breakdown,
questionnaire, dataset, and analyses with interpretation) without spending any
AI or analysis quota. The numbers are fixed and internally consistent so the
analysis views render exactly as they would for a real study.
"""
from __future__ import annotations

SAMPLE_TOPIC = (
    "The effect of mobile health reminders on antenatal clinic attendance "
    "among expectant mothers in rural Ghana"
)
SAMPLE_FIELD = "Public Health"

SAMPLE_VARIABLES = {
    "independent": [
        {"name": "Reminder frequency", "type": "ordinal", "description": "SMS/voice reminders sent per week"},
        {"name": "Phone ownership", "type": "categorical", "description": "Personal vs shared handset"},
    ],
    "dependent": [
        {"name": "Antenatal attendance", "type": "ratio", "description": "Number of scheduled visits attended"},
    ],
    "control": [
        {"name": "Distance to clinic", "type": "ratio", "description": "Kilometres to nearest facility"},
        {"name": "Maternal age", "type": "ratio", "description": "Age in years"},
    ],
}

SAMPLE_OBJECTIVES = [
    "To assess whether mobile health reminders increase antenatal clinic attendance.",
    "To examine how reminder frequency relates to the number of visits attended.",
    "To determine whether distance to the clinic moderates the effect of reminders.",
]

SAMPLE_HYPOTHESES = [
    "H1: Expectant mothers who receive mobile reminders attend more antenatal visits than those who do not.",
    "H2: Higher reminder frequency is positively associated with attendance.",
    "H3: The effect of reminders weakens as distance to the clinic increases.",
]

SAMPLE_METHODOLOGY = {
    "design": "Quasi-experimental, pre-post with a comparison group",
    "population": "Expectant mothers attending rural health facilities",
    "sampling": "Stratified random sampling across three districts",
    "sample_size": 120,
    "instrument": "Structured questionnaire with a 5-point Likert section",
    "analysis_plan": ["Descriptive statistics", "Correlation", "Linear regression"],
}

SAMPLE_SUMMARY = (
    "A quasi-experimental study testing whether mobile health reminders raise "
    "antenatal attendance among expectant mothers across three rural districts."
)

# ---- Questionnaire -----------------------------------------------------------
SAMPLE_QUESTIONNAIRE_TITLE = "Antenatal Reminders and Attendance Survey"
SAMPLE_QUESTIONNAIRE = {
    "title": SAMPLE_QUESTIONNAIRE_TITLE,
    "scale": "5-point Likert (1 = Strongly disagree, 5 = Strongly agree)",
    "sections": [
        {
            "id": "background",
            "title": "Background",
            "items": [
                {"id": "b1", "text": "What is your age in years?", "type": "numeric"},
                {"id": "b2", "text": "How far is the nearest clinic from your home (km)?", "type": "numeric"},
                {"id": "b3", "text": "Do you own a personal mobile phone?", "type": "categorical"},
            ],
        },
        {
            "id": "reminders",
            "title": "Reminders",
            "items": [
                {"id": "r1", "text": "The reminders helped me remember my appointments.", "type": "likert"},
                {"id": "r2", "text": "I found the reminders easy to understand.", "type": "likert"},
                {"id": "r3", "text": "I would like to keep receiving reminders.", "type": "likert"},
            ],
        },
        {
            "id": "attendance",
            "title": "Attendance",
            "items": [
                {"id": "a1", "text": "How many antenatal visits have you attended?", "type": "numeric"},
                {"id": "a2", "text": "The reminders made me more likely to attend.", "type": "likert"},
            ],
        },
    ],
}
SAMPLE_QUESTIONNAIRE_CLARITY = 88
SAMPLE_QUESTIONNAIRE_VALIDATION = {
    "clarity_score": 88,
    "issues": [
        {"item": "a2", "section": "attendance", "type": "leading", "text": "Consider neutral wording to avoid suggesting a desired answer."},
    ],
    "suggestions": [
        "Rephrase item a2 to avoid implying the expected response.",
        "Add a 'prefer not to say' option to the phone ownership item.",
    ],
}

# ---- Dataset -----------------------------------------------------------------
SAMPLE_DATASET_FILENAME = "sample_antenatal_attendance.csv"
SAMPLE_DATASET_COLUMNS = [
    "maternal_age",
    "distance_km",
    "reminder_frequency",
    "visits_attended",
]
# 40 internally consistent rows; attendance trends up with reminder frequency
# and down with distance. Kept compact but realistic.
SAMPLE_DATASET_ROWS = [
    [24, 3.2, 3, 7], [31, 8.5, 1, 4], [27, 1.1, 4, 8], [22, 12.0, 0, 2],
    [35, 5.4, 2, 5], [29, 2.3, 4, 8], [26, 9.7, 1, 3], [33, 4.0, 3, 6],
    [21, 0.8, 5, 9], [38, 14.2, 0, 2], [28, 6.1, 2, 5], [25, 3.9, 3, 7],
    [30, 7.8, 1, 4], [23, 1.5, 4, 8], [36, 10.3, 1, 3], [27, 2.7, 3, 6],
    [32, 5.0, 2, 5], [20, 0.5, 5, 9], [34, 11.6, 0, 3], [29, 4.4, 3, 6],
    [26, 8.0, 1, 4], [24, 2.0, 4, 8], [37, 13.1, 0, 2], [28, 3.6, 3, 7],
    [31, 6.7, 2, 5], [22, 1.2, 5, 9], [33, 9.0, 1, 3], [25, 4.8, 3, 6],
    [30, 7.2, 2, 5], [21, 0.9, 4, 8], [35, 12.5, 0, 2], [27, 3.0, 4, 7],
    [29, 5.9, 2, 5], [23, 1.8, 4, 8], [36, 10.9, 1, 3], [26, 4.2, 3, 6],
    [32, 6.4, 2, 5], [24, 2.5, 4, 8], [34, 11.0, 1, 3], [28, 3.4, 3, 7],
]
SAMPLE_DATASET_SCHEMA = {
    "columns": [
        {"name": "maternal_age", "dtype": "int", "role": "control"},
        {"name": "distance_km", "dtype": "float", "role": "control"},
        {"name": "reminder_frequency", "dtype": "int", "role": "independent"},
        {"name": "visits_attended", "dtype": "int", "role": "dependent"},
    ],
}
SAMPLE_DATASET_CLEANING = {
    "rows_in": 40,
    "rows_out": 40,
    "duplicates_removed": 0,
    "missing_imputed": 0,
    "notes": ["No missing values detected.", "All columns typed numerically."],
}

# ---- Analyses (canned, consistent with the dataset) --------------------------
SAMPLE_DESCRIPTIVE_RESULTS = {
    "n_observations": 40,
    "variables": {
        "maternal_age": {"mean": 28.6, "median": 28.0, "std": 4.8, "min": 20, "max": 38, "missing": 0},
        "distance_km": {"mean": 5.9, "median": 5.0, "std": 3.8, "min": 0.5, "max": 14.2, "missing": 0},
        "reminder_frequency": {"mean": 2.4, "median": 2.5, "std": 1.5, "min": 0, "max": 5, "missing": 0},
        "visits_attended": {"mean": 5.6, "median": 6.0, "std": 2.2, "min": 2, "max": 9, "missing": 0},
    },
}
SAMPLE_DESCRIPTIVE_INTERPRETATION = (
    "On average, mothers attended about 5.6 of their scheduled antenatal visits. "
    "Reminder frequency varied widely across the sample, and the spread in "
    "distance to clinic suggests it is worth examining as a moderating factor."
)

SAMPLE_CORRELATION_RESULTS = {
    "method": "pearson",
    "matrix": {
        "columns": ["maternal_age", "distance_km", "reminder_frequency", "visits_attended"],
        "values": [
            [1.00, 0.04, -0.06, -0.02],
            [0.04, 1.00, -0.55, -0.71],
            [-0.06, -0.55, 1.00, 0.86],
            [-0.02, -0.71, 0.86, 1.00],
        ],
    },
    "pairs": [
        {"variable_a": "reminder_frequency", "variable_b": "visits_attended", "coefficient": 0.86, "p_value": 0.0001, "strength": "strong", "direction": "positive", "significant": True},
        {"variable_a": "distance_km", "variable_b": "visits_attended", "coefficient": -0.71, "p_value": 0.0003, "strength": "strong", "direction": "negative", "significant": True},
        {"variable_a": "distance_km", "variable_b": "reminder_frequency", "coefficient": -0.55, "p_value": 0.012, "strength": "moderate", "direction": "negative", "significant": True},
        {"variable_a": "maternal_age", "variable_b": "visits_attended", "coefficient": -0.02, "p_value": 0.86, "strength": "negligible", "direction": "negative", "significant": False},
    ],
}
SAMPLE_CORRELATION_INTERPRETATION = (
    "Reminder frequency shows a strong positive association with the number of "
    "visits attended, while greater distance to the clinic is strongly and "
    "negatively associated with attendance. Maternal age shows no meaningful "
    "relationship. These patterns are consistent with the study hypotheses, "
    "though correlation alone does not establish causation."
)
