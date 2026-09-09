# RCI_V1 Methodology

## 1. Motivation

Raw event totals favor high-volume actions and hide the nature and evidence of collaboration. RCI_V1 provides a transparent team-relative view while preserving raw Activity Rank and every stored Evidence record.

## 2. Definition

For contributor `d` and active dimension `m`:

```text
RCI(d) = 100 × Σ w_m R_m(d)
```

- `d`: one GitHub contributor in the current repository.
- `m`: Code Implementation, Pull Request, Issue or Code Review.
- `R_m(d)`: contributor share after dimension-specific quality filtering and team normalization.
- `w_m`: effective weight after inactive dimensions are removed and remaining weights sum to 1.

Contributor RCI values sum to approximately 100%, subject to response rounding.

## 3. Four dimensions

- **Code Implementation**: effective commit share and robust filtered churn share.
- **Pull Request**: merged, non-draft PR share.
- **Issue**: open or completed issue share.
- **Code Review**: substantive, non-self, non-dismissed, deduplicated review share.

## 4. Quality filtering

Filters affect RCI inputs only. Events remain in Contribution Evidence, so users can inspect what was excluded and why.

Bots are excluded when the GitHub login ends in `[bot]`. This is the implemented bot rule; broader bot inference is not claimed.

## 5. Code Implementation

```text
Code = 50% × Effective Commit Share + 50% × Robust Churn Share
```

A merge commit or a commit with zero raw churn is not an effective commit. If commit count or churn is unavailable team-wide, the available signal receives the full Code dimension weight.

## 6. Filtered churn

```text
Raw Churn = Additions + Deletions
Filtered Churn = included-file Additions + included-file Deletions
```

The implementation excludes files inside `node_modules`, `vendor`, `dist`, `build`, `coverage` and `generated`; common lockfiles; `.min.js`, `.min.css` and source maps; and common binary/archive/font/media suffixes. Formatting-only detection is not reliably implemented and remains Future Work.

## 7. Robust transform

```text
Robust Churn = log(1 + Filtered Churn)
```

The transform limits the influence of unusually large changes without erasing them.

## 8. Team normalization

Each raw dimension metric is divided by the corresponding team total. Dimensions with a zero team total are inactive. RCI is therefore meaningful only inside the current repository and synchronized scope; values should not be compared as absolute scores across teams.

## 9. Research Baseline

Research Baseline requests weight `1` for every dimension, producing equal effective weights across active dimensions. It is a transparent neutral baseline, not an experimentally proven “best” weight set.

## 10. Custom Weights

Users may set non-negative Code, PR, Issue and Review weights. Active weights are renormalized; at least one active dimension must remain positive. The preference is stored in browser `sessionStorage` under the current user and repository, not in the database.

Custom Weights change only that user's current Dashboard RCI view. They do not change repository data, other users, Evidence or Contribution Composition.

## 11. Contribution Composition

Composition is calculated from the contributor's unweighted normalized dimension shares. It explains what kinds of contribution form that contributor's profile and remains invariant when Custom Weights change.

## 12. Explainability

The API returns requested/effective weights, active dimensions, metric coverage, dimension scores, raw metrics and per-dimension weighted contributions. Quick View and Calculation Basis expose these values together with the final RCI and current mode.

## 13. Dimension rules

- **PR**: merged included; open pending/not counted; draft excluded; closed unmerged excluded; bot authors excluded.
- **Issue**: open included; closed with `completed` included; `not_planned` excluded; unknown closed reason is not guessed and is excluded.
- **Review**: `APPROVED` and `CHANGES_REQUESTED` are substantive. `COMMENTED` requires a non-empty body or inline comment. Self-review, `DISMISSED` and empty review are excluded. Reviews deduplicate by PR, reviewer and commit snapshot; when commit ID is missing, review ID keeps records distinct.

## 14. Limitations

GitHub cannot fully represent offline discussion, meeting organization, design reasoning, verbal support, work in private external tools or uncommitted labor. Bounded sync and partial metadata further limit coverage. RCI must support human review, never replace it.

## References

- 刘玉辉、王忠杰，《GitHub 开源软件项目团队协作过程评价》，2020. This informs the multi-indicator educational context; CollabTrace does not copy its scoring formula.
- Gousios et al., *Work Practices and Challenges in Pull-Based Development: The Integrator's Perspective*. Background on pull-based collaboration.
- Lima, Rossi and Musolesi, *Coding Together at Scale: GitHub as a Collaborative Social Network*. Background on GitHub collaboration networks.
- Forsgren et al., *The SPACE of Developer Productivity: There's More to It Than You Think*. Supports the limitation that productivity cannot be reduced to activity counts.
- GitHub REST API documentation. Authoritative source for synchronized fields and state semantics.
