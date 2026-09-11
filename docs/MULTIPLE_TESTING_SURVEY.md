# Systematic Long Short — multiple-testing survey

Surveyed 2026-09-11 through the user's signed-in Safari session. The publication archive returned 79 posts, dated 2025-12-13 through 2026-07-06. Searched the readable page text of all 79 for multiple hypothesis testing, multiple comparisons, Bonferroni, false discovery, hypothesis counts, selection bias, p-hacking, and related terminology. Inspected the matching passages; this was a targeted text survey, not a methodological review of every article. No article was recorded as inaccessible during the scan.

Coverage is the publication archive, not confirmation of which posts the user previously read. Comments, Notes, image-only equations, and outbound papers were not exhaustively surveyed. No full subscriber article text is reproduced here.

## Direct mentions

| Article | Date | Relevant passage / takeaway |
|---|---|---|
| [Some Common Mistakes Beginner Quants Make](https://www.systematiclongshort.com/p/some-common-mistakes-beginner-quants) | 2026-03-24 | **Explicit Bonferroni mention**, under “The Root Cause & Some Fixes.” Describes repeated searches followed by winner selection as a source of inflated edge. Calls for logging hypothesis counts and counting changes to lookbacks, filters and related variants; recommends rolling/blocked validation and an untouched final holdout. This is the strongest general research-process reference. |
| [How To Build An Actually Useful Factor Model](https://www.systematiclongshort.com/p/how-to-build-an-actually-useful-factor) | 2026-03-05 | **Explicit Bonferroni mention.** Discusses multiple testing across candidate factors and contrasts a conventional t-ratio near 2 with a stricter threshold near 3.5. Cites Harvey, Liu and Zhu on multiple testing and Feng, Giglio and Xiu on incremental factor testing. This is the more factor-specific reference. |
| [How Not To Be A Shit Gambler](https://www.systematiclongshort.com/p/dont-be-a-shit-gambler) | 2026-01-08 | Explicitly says assessment of historical trading edge needs to account for multiple hypothesis testing. Brief warning; the matching passage does not specify a correction method. |
| [Stop Chasing Strong Signals. They Might Be Hurting You.](https://www.systematiclongshort.com/p/stop-chasing-strong-signals-they) | 2025-12-19 | Qualifies confidence inferred from an IC t-stat on the research not having been biased by multiple hypothesis testing. Relevant to the signal scorecard; the displayed t-stat shortcut still needs the observation-unit and dependence qualifications already recorded in the project plan. |

The keyword scan produced a fifth hit in [Knowing Institutional Datasets Makes You Extremely Valuable](https://www.systematiclongshort.com/p/knowing-institutional-datasets-makes), 2025-12-25. That passage concerns selection of consumers into email-receipt datasets, not multiple-testing correction, so it is excluded from the four direct matches above.

## Related material

Nineteen additional posts matched broader terms such as holdout, out-of-sample, overfitting or cross-validation, without the direct multiple-testing terminology above. Two particularly relevant starting points are:

- [Automated Alpha Mining, Not Useless Formula Factories](https://www.systematiclongshort.com/p/automated-alpha-mining-not-useless), 2026-03-17: warns that many formula/parameter variants are not independent new ideas, and emphasizes out-of-sample diversity and the gap between search results and trading outcomes.
- [How To Run An Amazing Forward Feature Selection Technique](https://www.systematiclongshort.com/p/how-to-run-an-amazing-forward-feature), 2026-01-12: related feature-selection material; the scan found validation terminology but no explicit named multiple-testing correction. It should not be cited as establishing Bonferroni or false-discovery guarantees.

## Implications for the plan — interpretation, not new owner decisions

1. Record a `study_id`, hypothesis family, model/instrument/contract identity, variant definitions, tested outcomes, and search history. External residualization and weighting stay external, but upstream choices that affected candidate selection need provenance in the study record.
2. Keep raw inferential results separate from corrected results. Consider Bonferroni as a transparent baseline, with the family size, significance level and valid underlying p-values explicit. Record an alternative such as Holm only after selecting and documenting the intended error-control contract. [Statsmodels' official multiple-testing interface](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html) provides these named methods.
3. Do not turn the factor article's approximate 3.5 t-ratio into a universal threshold. As a simple two-sided normal-reference calculation at family error level 0.05, the Bonferroni critical value is approximately 3.4808 for 100 tests and 3.8906 for 500 tests. Finite-sample and dependence-aware underlying inference must be specified separately. [Harvey, Liu and Zhu's paper](https://www.nber.org/papers/w20592) motivates higher factor-discovery hurdles in its own empirical setting; it does not supply one project-independent cutoff.
4. Preserve ordered validation and an untouched final assessment. A correction cannot repair unavailable-at-the-time inputs, invalid base p-values, an incomplete search history, or an assessment sample reused for selection. These remain separate acceptance requirements.

The Bonferroni and critical-value discussion is a candidate implementation direction. The project owner has not selected the final multiple-testing policy.
