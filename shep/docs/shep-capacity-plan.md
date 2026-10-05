# Shep capacity plan

`shep --capacity-plan --json` is a read-only observation pass. It joins:

- Shep's AFK-ranked mission candidates;
- queued and in-flight missions from Shep's canonical mission store;
- Herdr panes;
- the gateway cockpit's `-gw` lane health and selected models; and
- the workstation resource gate.

It returns a `mission-scheduler-cycle/v1` envelope containing the exact
observation and the deterministic `mission-scheduler-plan/v1` proposal derived
from it.

The command never creates a bead, worktree, lease, reservation, Herdr pane, or
model request. An assignment is only a recommendation. A future dispatcher
must re-read Shep state and capacity, obtain explicit approval, and use the
existing mission-launch path so Beads, Herdr, and lifecycle receipts remain
canonical.

The scheduled `shep_control_loop.py` runs this command after nudge, reap, and
reconcile. It uses the existing singleton loop lock. A failed source blocks the
plan and makes the scheduled pass non-zero, but does not stop normal nudge or
reap maintenance.

The gateway cockpit currently supplies health probes, not durable reservations.
The planner therefore treats a healthy lane as one available slot unless the
source provides explicit capacity fields. This is safe for advice, but it is
not sufficient for autonomous dispatch.

Run it by hand:

```bash
python3 scripts/shep.py --capacity-plan --json
```

The scheduled loop adds `--capacity-plan-summary` so its log contains counts,
source health, and proposed assignments without repeating hundreds of waiting
mission rows every five minutes.
