# One-job agent, filled in

The same template as `one-job-agent.md`, completed for one deliverable: a weekly client report. This is an example, not a report anyone should send.

```
JOB: Every Monday, draft last week's work report for one named client.
TRIGGER: A scheduled run at 07:00 every Monday. Nobody opens it.
MAY READ: That client's task log and the published pages changed in the last seven days.
MUST NEVER: Send the report, email the client, or edit the live site.
FINISHED LOOKS LIKE: A one-page draft with what shipped, what slipped, and what is next.
RESULT GOES TO: drafts/weekly-report.md in the client folder, overwritten each Monday.

CHECK 1: YES. One job, the weekly report. It does not also audit or write pages.
CHECK 2: YES. It runs at 07:00 whether or not anyone is there.
CHECK 3: YES. It may read the task log and the changed pages, and it may not send or edit.
CHECK 4: YES. Monday's draft was complete at 07:04. Nobody corrected it mid-run.
CHECK 5: YES. The draft was waiting in drafts/weekly-report.md.
```

All five are yes, so this one counts. A workflow that needs someone to open it and ask for the report would fail check 2, and would not be an agent.
