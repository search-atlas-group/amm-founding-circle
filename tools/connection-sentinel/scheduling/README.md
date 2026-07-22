# Scheduling -- keep the watch running without a server

Connection Sentinel is a small always-on loop, not a server -- it just needs
to keep running somewhere. Two ways to do that, no server required, plus the
zero-setup option.

## macOS -- launchd

1. Copy `com.amm.connection-sentinel.plist` to `~/Library/LaunchAgents/`.
2. Edit the three `/ABSOLUTE/PATH/TO/...` lines to your real checkout path.
3. Load it:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.amm.connection-sentinel.plist
   ```
4. Check it's running:
   ```bash
   launchctl list | grep connection-sentinel
   ```
5. Stop it any time:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.amm.connection-sentinel.plist
   ```

`KeepAlive` restarts it if it ever exits unexpectedly; `RunAtLoad` starts it
on login/reboot too. Logs land at `/tmp/connection-sentinel.log` /
`connection-sentinel.err`.

## Windows -- Task Scheduler

1. Open **Task Scheduler** -> **Create Task...**
2. **General:** name it `Connection Sentinel`; check "Run whether user is
   logged on or not."
3. **Triggers:** New -> **At log on** (or **At startup**).
4. **Actions:** New -> Program/script: `python` -- Arguments:
   ```
   sentinel.py --config connections.yaml --interval 900
   ```
   Start in: the full path to `tools\connection-sentinel\`.
5. **Settings:** check "If the task fails, restart every" 1 minute, up to 3
   times -- the Windows equivalent of `KeepAlive`.
6. Save. It now starts on every log-on and keeps itself running.

## Either platform -- just run it in a terminal

No always-on daemon yet? Leave a terminal open:

```bash
python3 sentinel.py --config connections.yaml --interval 900
```

`Ctrl-C` stops it. Move to the scheduled version above once you've watched it
catch a real, deliberate failure and trust it.
