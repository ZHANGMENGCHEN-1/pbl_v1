# K-means course

`components/` contains the three experiments and their scatter plot. Change these
implementations once for all three classes. `activities.ts` supplies B/C activity
text; `pureActivities.ts` preserves A's distinct wording. The neighboring modules
contain K-means API contracts, ordering rules and chart scale calculations.

The A/B/C entry points stay in `src/projects`. General teaching UI, workflow and
state infrastructure are described in [the shared structure](../../shared/teaching/README.md).
No student-facing URL, backend endpoint or database schema changes with this move.
