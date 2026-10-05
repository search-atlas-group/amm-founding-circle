# Shep — repository scope

Read this before opening a merge request, adding a release gate, or treating
anything here as customer-facing.

## What this repository is

Shep is **internal research and development tooling**. It is a governed terminal
command deck that supervises agent sessions on a developer workstation. Its users
are the engineers working in this repo.

## What this repository is not

**Shep is not a production application.** It is not deployed to
baremetal-production or baremetal-staging, it is not fronted by an Ingress, it
serves no customers, and no customer data passes through it. There is no
production surface to protect, no release train, and no on-call rotation.

## What that means in practice

| Standard SearchAtlas process | Applies here? |
|---|---|
| Merge requests reviewed before merge | **Yes** |
| Tests + inventory pins green before merge | **Yes** — see `## Verify` in the README |
| Linear issue link in the MR description | **No** — waived, see below |
| ClickUp Clip (QA recording) in the MR description | **No** — waived, see below |
| Deployment / rollback plan | **No** — nothing is deployed |

### The MR evidence requirement is waived here

The company rule requires every merge request to carry a real Linear issue link
and a real ClickUp Clip recording. That rule exists to prove that a change
affecting customers was ticketed and demonstrated. **This repository has no
customer-facing surface, so the requirement does not apply to it.** Waived
explicitly by Project Owner on 2026-09-16.

This is a scope exemption, not a lowered bar. It does **not** licence a
placeholder, dummy, or borrowed URL in any repository, here or anywhere else — a
fake evidence link is a false claim and is never acceptable. If a change in this
repo does happen to have a real ticket, link it.

The verification gates below are not waived and are the evidence for changes here.

## What is currently in flight

[docs/open-work.md](docs/open-work.md) is the list of live work items. Check it
before starting something, so two efforts do not collide. It is maintained by
hand — if you open, finish, or abandon an item, edit that file in the same
merge request.

## Verification is still mandatory

Every change runs the full matrix before merge. Use `python3.11` — the host
`python3` may be 3.9, and Shep requires >= 3.10.

```bash
python3.11 -m pytest -q
python3.11 tools/verify_test_inventory.py
python3.11 -m compileall -q scripts tests
ruff check scripts tests
```

The pinned node inventory in `tests/pinned-node-ids.txt` is order-sensitive:
regenerate it in pytest collection order and rerun the verifier.

## If this ever changes

If Shep gains a deployed surface, a customer, or a hosted endpoint, delete this
exemption and restore the full evidence requirement before the first deploy.
