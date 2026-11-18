# Teaching frontend structure

```text
src/
  shared/
    components/teaching/   CompanionLayout, measurements, robot/
    composables/teaching/ useTeachingFlow, useTeachingLearning, useTeachingChat
    teaching/             state model, types, telemetry, SSE parser
  courses/kmeans/
    components/           calculation, ordering, Excel experiment, scatter plot
    activities.ts         B/C activity text
    pureActivities.ts     A activity text
    calculation.ts        calculation API and result types
    exploration.ts        Excel API and result types
    sorting.ts            ordering rules
    axisScale.ts          scatter chart scales
  projects/
    learning-activities/   A entry and pure-activity layout
    teaching-agent/       B entry
    meaning-making/       C entry and strategy documentation
```

`CompanionLayout.vue` is the single B/C interface. Each entry passes its fixed
condition, learning-session factory and robot component. B hides post-activity
chat and shows completion text. C puts chat inside the speech bubble and starts
discussion after measurement. The home page and both companion entries use the
same renderer in `shared/components/teaching/robot/`.

`useTeachingFlow.ts` owns registration, submissions, measurements, navigation
guards, reset and activity-entry telemetry. Only condition C opens a discussion.
Switching clears the old reflection and temporary feedback while retaining
submissions and unlocks. Incomplete measurements and active operations block
navigation. `useTeachingLearning.ts` creates an independent session per entry;
route configuration retains the existing storage cleanup keys and fresh-session
behavior.

`learningState.ts` preserves drafts, immutable submissions and completion rules.
`useTeachingChat.ts` and `chatStream.ts` handle streaming, cancellation and retry.
The current flow and layout still integrate K-means activity contracts; this
directory move does not introduce a multi-course configuration engine. K-means
experiment implementations, request types and learning materials live in the
course directory rather than among shared UI components.

Old compatibility exports and unused preview cards are removed. Backend API
paths, database structures, class conditions and student-facing URLs are unchanged.

Verification:

- `npm.cmd --prefix frontend run build`
- `node scripts/teaching_flow_smoke.mjs`
- `node scripts/teaching_learning_state_smoke.mjs`
- `node scripts/teaching_chat_stream_smoke.mjs`
- Start `scripts/teaching_chat_fixture_server.py`, start Vite on 5174 with
  `API_TARGET=http://127.0.0.1:8001`, then run
  `scripts/shared_activities_browser_smoke.py` using the project Python environment.
  This uses an isolated database and a local model test double.
