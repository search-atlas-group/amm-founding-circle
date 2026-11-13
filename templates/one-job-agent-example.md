# One-job agent, filled in

The same template as `one-job-agent.md`, completed for one deliverable: a weekly client report. The point of the example is the choice. On a quiet week the agent decides there is nothing worth reporting, and says why. A workflow would have written the report anyway.

```
JOB: Every Monday, read one client's week and decide whether there is anything worth reporting.
TRIGGER: A scheduled run at 07:00 every Monday. Nobody opens it. The trigger only wakes it.
OPTIONS: Draft the report. Or write nothing, when the week does not clear the bar the member set.
MAY READ: That client's task log and the published pages changed in the last seven days.
MUST NEVER: Send the report, email the client, or edit the live site.
FINISHED LOOKS LIKE: Either a one-page draft, or a note that says nothing was worth reporting. Both include the reason.
RESULT GOES TO: drafts/weekly-report.md in the client folder, overwritten each Monday.

CHECK 1: YES. One job, the weekly judgment. It does not also audit or write pages.
CHECK 2: YES. It runs at 07:00 whether or not anyone is there.
CHECK 3: YES. It may read the task log and the changed pages, and it may not send or edit.
CHECK 4: YES. Last Monday it found two typos and no shipped work, judged that below the bar, and wrote "nothing to report" with that reason.
CHECK 5: YES. The note was waiting in drafts/weekly-report.md.
```

All five are yes, so this one counts. The same run writing a report every Monday regardless of the week would fail check 4. It never chose.
