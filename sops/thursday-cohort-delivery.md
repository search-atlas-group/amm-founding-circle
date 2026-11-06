# Thursday cohort: session to repository to member announcement

**Standing delivery standard:** after every Thursday AMM cohort/mastermind session, turn the actual session's commitments into member-usable deliverables, push the verified bundle to this repository, and announce it in the verified **AMM-SearchAtlas** Slack channel. A local file, draft message or successful worker exit does not complete the session.

This SOP defines the operating procedure. It does not install a scheduler, grant standing permission for new integrations/spend, or prove unattended operation.

## Owner, trigger and completion

- **Accountable owner:** JD. The AMM session operator prepares, verifies, publishes and records receipts within the authorized scope.
- **Trigger:** the Thursday cohort ends and its complete verified transcript is available. If processing is delayed, record that blocker; do not substitute an older session.
- **Complete:** every promised item is either delivered with acceptance evidence or explicitly marked open with an owner/next action; the remote commit is verified; one new top-level member update is sent to the correct channel and read back.
- **Source delay:** preserve the occurrence and exact missing artifact; retrieve from approved meeting sources. Do not ask the cohort to watch an unverified recording.

## 1. Lock the occurrence before drafting

Read the complete actual transcript. Verify the calendar/note occurrence date, title, speakers and first/last timestamps. Privately preserve its source receipt, byte count and SHA-256. A recurring title, file date, topic overlap, debrief or generated summary is not enough. Keep meeting date, preparation date and recording identity separate.

If JD says the source was today's session but a candidate appears to be an older meeting, stop and resolve the conflict. Never relabel the work as an older recording for convenience.

Keep raw transcripts, participant details and source-authentication artifacts outside the shared repository. Publish sanitized teaching and reusable instructions only.

## 2. Reconcile every commitment

Create a topic-to-deliverable table. Distinguish what was taught, what was demonstrated, explicit follow-ups, future proposals and open product questions. The final Q&A counts: do not stop at the end of the prepared presentation.

For each owed item record:

| Item | Session cue | Artifact | Acceptance check | State | Owner/next action |
|---|---|---|---|---|---|
| [promised result] | [actual timestamp/segment] | [existing repo path] | [real test or review] | [delivered/open] | [named role and next step] |

Do not turn a live demo, anecdote, pricing remark or reported timing into independently measured evidence. Record uncertainty, model/hardware details and what was not measured.

## 3. Build the member bundle

Use a date-specific start page at `reports/cohort-YYYY-MM-DD/README.md` and link it from the repository's main README. Avoid reusing another session's slug or recording link.

Every implementation guide needs: prerequisites, a platform choice, ordered setup, inputs, approved knowledge and output locations, a copyable agent prompt, permissions/approval gates, acceptance checks, troubleshooting and rollback. Give the member a task they can actually run, not just an architecture sketch.

- Shared knowledge is not shared credentials, runtime access or private conversations.
- Profile names, prompts and separate working folders are not authorization or filesystem-isolation guarantees.
- State any missing integration or account-specific control explicitly.
- Benchmarks need reproducible inputs, version/hardware/context and actual raw observations. A protocol, fixture or test harness is not a completed model comparison.
- Voice guides must distinguish offline routing tests from live microphone, playback, interruption and connected-tool tests.
- Link only to a replay that matches this exact occurrence and has actually started playback. If absent, ship the written bundle with video status open and say **read/review**, not **watch**.

## 4. Verify before pushing

1. Check every linked local file, template, skill and command on the final tree. Resolve dependency closure, not just the start page.
2. Exercise safe runnable examples/tests. Keep fixture results distinct from real account/model results.
3. Inspect every changed line for private data, credentials, private paths, raw transcript text and unsupported product promises. Preserve the repository's secret/PII guard.
4. Review the source-to-artifact mapping independently of test success. A passing test does not establish correct meeting identity or correct audience.
5. Obtain an independent content/safety review when the bundle has new implementation behavior. Fix findings and rerun affected checks.
6. Review `git diff`, stage only the intended files, run the repository pre-commit guard, then commit and push to the authorized canonical remote/branch. Never reset unrelated work or force-push.
7. Read back the remote branch SHA and confirm it equals the published commit. If the repository has required CI, verify its exact-head results; do not describe local tests as CI.

Repository delivery is distinct from portal ingestion/deployment. If portal publication is also requested, follow its own manifest, CI, deployment, page-open and playback gates. Never label a repo-only bundle live in the portal.

## 5. Announce to the right members

This Thursday procedure specifically uses **AMM-SearchAtlas on Slack**. It is not the internal operations lane and must never default to `#general`. Resolve the exact channel ID from the current channel map/history, confirm the audience and read recent messages before sending. Use the verified ID, not a guessed name. Keep account/channel IDs and delivery receipts in the private release record.

Post **one new top-level message**, not a buried thread reply. Deduplicate by meeting occurrence and published commit. Replace every placeholder below with actual topics and verified links:

> Hey everyone, based on today's conversation about [actual topics], I've pushed [specific deliverables] into the Founding Circle repository.
>
> Start here: [date-specific repository link]
>
> [Read/review, or watch only when playback was verified] and let me know what you think.
>
> [Only if needed: precise open item and next action, without an invented ETA.]

If a previous message misidentified the meeting or destination, correct it transparently. Do not quote an earlier announcement without retrieving its actual text. Do not send a replacement merely because a limited history window did not show the first post.

After sending, fetch the channel history or exact event and verify the rendered text, intended channel, all links and top-level status. Record event timestamp/ID and permalink privately. A send API accepting the request is not the final readback.

## 6. Close with receipts and track gaps

Use [the release checklist](../templates/cohort-session-release-checklist.md). Record source hash, artifact list, checks, independent review, commit, remote confirmation and Slack readback. Keep member-owned ideas in member records; track only JD-owned commitments as JD actions.

A remaining product answer or live integration test stays open after the docs ship. Never turn “sent”, “escalated”, “fixture passed” or “scheduler enabled” into resolution.

Report to JD in a few lines: what was pushed, where members were notified, what was verified, and exactly what still needs input or access. Apply this procedure on every Thursday cohort, not only when JD asks whether anything was posted.
