# Writing Rules

Use these constraints for every new rule:

1. Start with the narrowest pattern that can still catch the real bug.
2. Add an anti-pattern list for common legitimate variants.
3. Add a guard when regex alone cannot prove the bug.
4. Put the rule in the lowest-risk layer that matches its certainty:
   - `hard_correctness`: deterministic bugs only
   - `semantic`: context-checked likely bugs
   - `heuristic`: useful review hints that can still be noisy
5. Add at least two positive examples and at least one negative example.
6. Run the reviewer against a real repo slice before shipping the rule.
7. If the rule is profile-specific, keep it out of `general`.

Minimum checklist:
- rule ID
- severity
- category
- description
- fix guidance
- pattern
- anti-patterns
- guard if needed
- tests
- real-scan verification

Suppression:
- preferred directive: `REVIEW-IGNORE`
- legacy alias still supported: `VB-IGNORE`
