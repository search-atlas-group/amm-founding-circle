# The 90-second version

An agent can produce a convincing result and still miss the request. We reduce that risk by separating four responsibilities: observe permitted evidence, write a clear specification, build from that brief, and independently verify the result.

There are two different boundaries. A clean-room information boundary controls what the builder is allowed to see. A quality gate controls what the result must prove before it advances. Neither replaces the other.

Craft Anything is a concrete reference: its documented workflow is Study, Build, Check, Ready. We are borrowing the pattern, not claiming it guarantees legality or that we have verified two teams with a strict information firewall.

We already use related practices in our website work: staged changes, a separate integration step, and independent browser checks. We do not have universal technical enforcement across every workflow.

The companion example is a teaching pattern: a negative test would omit a required link, and the intended gate should reject it. Missing evidence should block the handoff. A corrected artifact may pass stated checks, but that still does not grant permission to publish. The principle is simple: specification before interpretation, evidence before acceptance, permission before publication.
