# Playbook: Browser Verification

If a user will see it in a browser, verify it in a browser before calling it
done.

## Minimum Proof

For a web UI change, collect:

- the URL tested;
- viewport size;
- screenshot;
- console errors;
- one sentence describing what passed.

## Prompt

```text
Verify this page in a browser. Check the layout at desktop and mobile widths,
look for console errors, and save screenshots. Do not claim success unless the
screenshots show the expected state.
```

## What To Look For

- text overlap;
- clipped buttons;
- empty states;
- broken images;
- console errors;
- layout shifts;
- forms that cannot be submitted with a keyboard;
- mobile controls that are too small or hidden.

## Common Mistake

Code inspection is not browser verification. A screenshot catches entire classes
of errors that the code can look too reasonable to reveal.

