from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.services.research_service import ResearchService

# These are editable starting templates, not legal advice. They give researchers
# a structured, defensible starting point that they adapt to their institution's
# ethics board requirements.


def _consent_form(topic: str, field: str | None) -> str:
    return f"""# Informed Consent Form

**Study title:** {topic}
{f"**Field:** {field}" if field else ""}
**Date:** {date.today().isoformat()}

## Invitation
You are being invited to take part in a research study. Before you decide, it is
important that you understand why the research is being done and what it will
involve. Please read the information below and ask if anything is unclear.

## Purpose of the study
This study examines: {topic}. Your participation will help advance understanding
in this area.

## What participation involves
- Completing a questionnaire / interview lasting approximately ___ minutes.
- Participation is entirely voluntary.

## Voluntary participation and withdrawal
You are free to decline to participate and free to withdraw at any time, without
giving a reason and without any disadvantage to you.

## Confidentiality and data protection
Your responses will be kept confidential. Identifying information will be removed
or anonymised, and data will be stored securely and used only for the purposes of
this research.

## Risks and benefits
There are no anticipated risks beyond those of everyday life. There may be no
direct benefit to you, but the findings may benefit the wider community.

## Consent
By signing below, I confirm that I have read and understood the information above,
that my questions have been answered, and that I voluntarily agree to take part.

Participant name: ______________________  Signature: ______________  Date: ________

Researcher name: ______________________  Signature: ______________  Date: ________
"""


def _participant_sheet(topic: str, field: str | None) -> str:
    return f"""# Participant Information Sheet

**Study title:** {topic}

## Who is conducting this research?
This research is being conducted by [researcher name], [institution/department].

## Why have I been approached?
You have been approached because you meet the criteria relevant to this study on
{topic}.

## Do I have to take part?
No. Participation is voluntary. You may withdraw at any time without penalty.

## What will happen to my data?
- Your data will be anonymised and stored securely.
- Only the research team will have access to the raw data.
- Results will be reported in aggregate; you will not be identifiable.
- You may request that your data be deleted at any point before analysis is
  finalised.

## Who has reviewed this study?
This study has been reviewed by [name of ethics committee / IRB], reference
number [____].

## Contact for questions
Researcher: [name, email]
Ethics committee: [contact]
"""


def _irb_protocol(topic: str, field: str | None) -> str:
    return f"""# Ethics / IRB Protocol Summary

**Study title:** {topic}
{f"**Discipline:** {field}" if field else ""}

## 1. Background and rationale
Briefly state the problem this study addresses and why it matters.

## 2. Aims and objectives
State the primary aim and specific objectives of the study.

## 3. Study design and methods
Describe the design (e.g., cross-sectional survey, experimental), the sampling
strategy, sample size and justification, and the instruments used.

## 4. Participants
- Inclusion criteria: ______
- Exclusion criteria: ______
- Recruitment procedure: ______

## 5. Informed consent procedure
Describe how informed consent will be obtained and documented.

## 6. Risks and mitigation
Identify any physical, psychological, social or legal risks and how they will be
minimised.

## 7. Data management and confidentiality
- How data will be collected, stored, and secured.
- Anonymisation / de-identification procedures.
- Data retention period and disposal plan.

## 8. Benefits
State any direct or indirect benefits to participants or society.

## 9. Conflicts of interest and funding
Declare any conflicts of interest and the funding source.

## 10. Dissemination
Describe how findings will be shared (thesis, publication, community feedback).
"""


def templates_for_project(db: Session, user_id: int, project_id: int) -> list[dict]:
    project = ResearchService(db).get_owned(project_id, user_id)
    topic = project.topic
    field = project.field
    return [
        {"id": "consent", "title": "Informed Consent Form", "body": _consent_form(topic, field)},
        {"id": "participant", "title": "Participant Information Sheet", "body": _participant_sheet(topic, field)},
        {"id": "irb", "title": "Ethics / IRB Protocol Summary", "body": _irb_protocol(topic, field)},
    ]
