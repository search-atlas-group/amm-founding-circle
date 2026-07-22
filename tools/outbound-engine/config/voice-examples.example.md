# Outreach voice examples

Copy this to `config/voice-examples.md` and paste in 2-3 real cold emails you've
sent that got a good reply (or that best capture how you actually talk to
prospects). The personalizer (`outbound_engine/personalize/personalizer.py`)
uses these as a **style reference only** — tone, sentence length, how direct
you are, whether you use humor — never as a template to copy verbatim, and it
never invents facts about a prospect beyond what's in their record.

If you leave this empty, drafts fall back to a plain, direct, professional
default tone (see `personalize/personalizer.py`'s `_mock_draft`).

---

## Example 1 — subject + body that got a reply

Subject: quick one about [Company]'s Google reviews

Hey [First Name],

Saw [Company] pop up on our radar — noticed you're sitting at [X] reviews
on Google but a few of your competitors in [city] are pulling ahead on that.
Not pitching anything yet, just curious whether that's on your radar or if
your plate's full with other stuff right now.

If it's useful, happy to send over the 2-minute breakdown we ran. No pressure
either way.

— [Your name]

---

## Example 2 — (add your own)

Subject:

Body:
