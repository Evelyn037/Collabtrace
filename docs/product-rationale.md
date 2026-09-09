# Product Rationale

## Target users

- University course instructors and teaching teams reviewing group-project collaboration.
- Student project teams that need consistent, verifiable evidence of individual work.
- Repository or project administrators organizing contribution evidence and access.

No user survey count, paying customer, institutional deployment or GitHub partnership is claimed.

## Concrete pain points

Teachers can inspect the final submission but cannot directly observe every collaboration step. Students may struggle to explain personal contributions with consistent, independently verifiable evidence. GitHub records Commit, Pull Request, Issue and Review activity, but those records are distributed across views and are not naturally organized as a course-team contribution analysis and evidence chain.

## Why GitHub data

GitHub already provides auditable collaboration records with stable identifiers, timestamps, authors and original URLs. CollabTrace collects a bounded scope of those real records, normalizes them into four activity types and preserves their source links. It does not fabricate missing activity or treat GitHub as a complete representation of all work.

## Value proposition

CollabTrace turns dispersed repository activity into an explainable team-relative view: repository overview, RCI, contribution composition, contributor detail, filtering and source evidence. The value is evidence-supported collaboration interpretation—not automatic grading, performance evaluation or an assertion of absolute truth.

## End-to-end data loop

```text
GitHub collaboration evidence
→ collection
→ normalization
→ SQLite persistence and sync history
→ contribution analytics
→ RCI and formation explanation
→ Contributor Detail
→ Evidence
→ original GitHub record
```

This loop keeps the analysis inspectable: users can move from an aggregate visualization back to the stored event and then to GitHub's source record.

## Difference from native GitHub views

GitHub's primary role is code hosting and software collaboration. CollabTrace is a course-team interpretation layer over GitHub evidence. It combines multiple contribution types, calculates a transparent repository-relative RCI, explains its formation, supports Evidence filtering, and separates System and Repository administration. It complements rather than replaces GitHub.

## RCI limitations

RCI applies only inside the current repository and synchronized scope. It does not measure absolute coding ability, code quality, actual working hours, offline work, meetings, messaging, absolute labor value or a student's complete grade. Custom weights change the current user's RCI view, not source evidence or contribution composition.

## Responsible interpretation

Use RCI as a navigation and discussion aid alongside human review. Inspect Evidence and context before drawing conclusions. Never use CollabTrace as an employee-scoring system or claim that it captures collaboration outside synchronized GitHub records.
