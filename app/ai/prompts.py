"""Role-based system prompts and the chapter blueprints that drive report depth.

The previous version asked the model to "write a chapter" in one shot, which —
combined with a low token ceiling — produced thin output. Reports are now built
section by section from these blueprints, each section a focused generation with
an explicit depth target, so a full thesis runs to the expected length and
rigour instead of a few pages.
"""

# ----------------------------------------------------------------------------
# System roles
# ----------------------------------------------------------------------------
RESEARCH_ASSISTANT = (
    "You are a meticulous academic research methodologist who supervises "
    "graduate dissertations. You break topics into precise, testable, "
    "construct-level designs. You use correct methodological terminology, keep "
    "independent/dependent/moderating variables distinct, and never fabricate "
    "statistics. Objectives are specific and measurable; hypotheses are "
    "directional and falsifiable; methodology is internally consistent."
)

QUESTIONNAIRE_DESIGNER = (
    "You are an expert survey methodologist who builds publication-ready "
    "research instruments. Every latent construct is measured by MULTIPLE "
    "reflective items so a Cronbach's alpha can be computed. Items are clear, "
    "single-barrelled, unbiased, and written at a 6th–8th grade reading level. "
    "You include reverse-coded items, proper response anchors, section "
    "instructions, and a consent preamble. You never produce token 'sample' "
    "items — you produce a complete instrument a student could field as-is."
)

STAT_INTERPRETER = (
    "You are a statistics interpreter for a thesis. You are given numbers that "
    "were ALREADY computed by a deterministic engine. You must NEVER recompute, "
    "round differently, alter, or invent any number. You report the exact values "
    "given, then explain what they mean in clear APA-style prose: state the test, "
    "the statistic and p-value, whether the hypothesis is supported, the effect "
    "size and its practical meaning, and a one-line scholarly implication."
)

SUPERVISOR_EXAMINER = (
    "You are a strict but fair PhD supervisor and external examiner conducting a "
    "viva voce. You probe methodology, validity, contribution, and limitations, "
    "evaluate answers honestly, and identify weaknesses without being cruel."
)

REPORT_WRITER = (
    "You are a doctoral academic writer producing thesis chapters in formal "
    "scholarly English. You write in flowing, well-developed paragraphs (not "
    "bullet fragments) with smooth transitions and topic sentences. You ground "
    "every claim ONLY in the provided project details and computed results, "
    "never inventing data. You use APA in-text citation style with plausible "
    "placeholder authors and years where the project provides no source (e.g. "
    "(Author, 2021)), and you write to the requested depth — never padding, "
    "never truncating. You output GitHub-flavoured Markdown: '##' for sections, "
    "'###' for sub-sections, '**bold**' for emphasis, and '-' for lists only "
    "where a list is genuinely appropriate."
)


# ----------------------------------------------------------------------------
# Chapter blueprints: ordered (section_title, brief, target_words)
# Ch4 sections are written around the real tables/figures by the report service.
# ----------------------------------------------------------------------------
CHAPTER_BLUEPRINTS: dict[str, dict] = {
    "1": {
        "title": "Chapter One: Introduction",
        "sections": [
            ("1.1 Background to the Study",
             "Set the broad context of the topic, narrowing from the global/regional picture to the "
             "specific problem. Reference the key constructs and why they matter in this field and setting.", 450),
            ("1.2 Statement of the Problem",
             "Articulate the specific gap or problem the study addresses, the evidence it exists, who is "
             "affected, and the consequence of leaving it unaddressed. End with what remains unknown.", 400),
            ("1.3 Objectives of the Study",
             "Present one general objective and the specific objectives, derived directly from the project's "
             "stated objectives. Number them.", 220),
            ("1.4 Research Questions",
             "Convert each specific objective into a matching research question.", 180),
            ("1.5 Research Hypotheses",
             "State each hypothesis from the project in null and alternative form where appropriate.", 200),
            ("1.6 Significance of the Study",
             "Explain the theoretical, practical, and policy contributions and who benefits.", 320),
            ("1.7 Scope and Delimitations",
             "Define the boundaries: variables covered, population, geography, and timeframe, plus what is "
             "deliberately excluded.", 220),
            ("1.8 Operational Definition of Terms",
             "Define each key variable/construct operationally as used in this study.", 220),
        ],
    },
    "2": {
        "title": "Chapter Two: Literature Review",
        "sections": [
            ("2.1 Introduction",
             "Preview the structure of the review and its purpose.", 160),
            ("2.2 Theoretical Framework",
             "Present one or two established theories that underpin the study, explain their core "
             "propositions, and justify their relevance to the constructs.", 480),
            ("2.3 Conceptual Review",
             "Review each major construct (independent and dependent variables) in turn, defining it and "
             "synthesising how the literature characterises it.", 600),
            ("2.4 Empirical Review",
             "Summarise prior empirical studies on the relationships among the variables, noting their "
             "methods, findings, and contexts, with APA in-text citations.", 600),
            ("2.5 Conceptual Framework",
             "Describe the proposed conceptual framework linking the independent variables to the dependent "
             "variable, consistent with the hypotheses; describe it in prose (a diagram is implied).", 280),
            ("2.6 Research Gap",
             "Identify the specific gap (contextual, methodological, or empirical) this study fills.", 240),
            ("2.7 Chapter Summary",
             "Summarise the review and bridge to the methodology.", 160),
        ],
    },
    "3": {
        "title": "Chapter Three: Research Methodology",
        "sections": [
            ("3.1 Introduction", "State what the chapter covers.", 130),
            ("3.2 Research Design",
             "State and justify the design (e.g. quantitative cross-sectional survey) given the objectives.", 320),
            ("3.3 Population of the Study",
             "Define the target population and its characteristics.", 220),
            ("3.4 Sample Size and Sampling Technique",
             "State the sampling technique and justify the sample size (reference the actual N from the "
             "analyses where available).", 320),
            ("3.5 Research Instrument",
             "Describe the questionnaire: sections, response scale, and how items map to constructs.", 320),
            ("3.6 Validity and Reliability",
             "Explain how validity was ensured and how reliability was assessed (Cronbach's alpha), "
             "referencing the actual reliability results where available.", 320),
            ("3.7 Data Collection Procedure",
             "Describe how data were gathered.", 220),
            ("3.8 Method of Data Analysis",
             "State exactly which statistical techniques were used for each objective/hypothesis and why.", 320),
            ("3.9 Ethical Considerations",
             "Cover informed consent, confidentiality, anonymity, and voluntary participation.", 220),
        ],
    },
    "4": {
        "title": "Chapter Four: Data Presentation, Analysis and Results",
        # Section narrative is woven around the deterministic tables/figures by
        # the report service; these are the narrative beats it requests.
        "sections": [],
    },
    "5": {
        "title": "Chapter Five: Summary, Conclusions and Recommendations",
        "sections": [
            ("5.1 Introduction", "State what the chapter covers.", 130),
            ("5.2 Summary of the Study",
             "Restate the purpose, objectives, methodology, and overall approach concisely.", 320),
            ("5.3 Summary of Major Findings",
             "Summarise the key findings for each objective/hypothesis using ONLY the computed results "
             "provided. Reference whether each hypothesis was supported.", 420),
            ("5.4 Conclusions",
             "Draw reasoned conclusions answering the research questions, grounded in the findings.", 360),
            ("5.5 Recommendations",
             "Give specific, actionable recommendations flowing from each major finding, for the relevant "
             "stakeholders.", 380),
            ("5.6 Contribution to Knowledge",
             "State what the study adds theoretically and practically.", 220),
            ("5.7 Limitations of the Study",
             "State honest methodological and scope limitations.", 220),
            ("5.8 Suggestions for Further Research",
             "Propose concrete next studies that build on this work.", 220),
        ],
    },
}
