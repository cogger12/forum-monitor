# NES .45 handgun monitor

Watches the public [WTS/WTT Handguns](https://www.northeastshooters.com/xen/forums/wts-wtt-handguns.213/) forum on Northeast Shooters and alerts you when a new listing is a pistol chambered in .45.

It reads the newest threads (not bumped old ones), checks the title and the first post, and remembers thread ids in a local database so each listing alerts once. The first run records what is already on the forum and does not alert. Only threads that show up after that are sent.

Checks stay at least 5 minutes apart. The default is 15 minutes. Nothing is posted to the forum.

## What counts as a match

A listing matches when the title or the first post says one of:

- .45 ACP, .45 Auto, .45 GAP, .45 Super, .45 Colt / .45 Long Colt, .45 Winchester Magnum
- a bare `.45` (for example "chambered in .45")
- a model that is .45 ACP: Glock 21, 30, 36, 41, HK45, FNX-45, FNP-45, XD-45, M&P45, USP 45

These do not match:

- **Glock 45**, G45, and "45 gen 6". That is a 9mm model, not a caliber.
- Prices such as `$450`
- 9mm, .40, 10mm, .22, .380, and the other common handgun calibers
- .450 Bushmaster, .454 Casull, .458, .45-70
- Black-powder ".45" kits
- Threads prefixed SOLD, WTB, or delete

A 1911 with no caliber in the title is read in full. It alerts only if the post actually says .45, because a lot of 1911s on this forum are 9mm. Sold threads are ignored.

## Notify

Set any of these. If none are set, alerts are written to the log only.

- **ntfy** is the simplest. Create a long unguessable topic and subscribe on your phone.
- A Discord webhook, Slack webhook, or generic JSON POST
- Email over SMTP

Environment variables override the config file: `NES_NTFY_URL`, `NES_WEBHOOK_URL`, `NES_WEBHOOK_FORMAT`, `NES_SMTP_HOST`, `NES_SMTP_PORT`, `NES_SMTP_USER`, `NES_SMTP_PASSWORD`, `NES_SMTP_FROM`, `NES_SMTP_TO`.

## Run it on the VPS

The server needs Python 3.9 or newer. No extra packages.

```bash
sudo useradd --system --create-home --home-dir /opt/nes-45-monitor --shell /usr/sbin/nologin nes45
sudo mkdir -p /opt/nes-45-monitor /var/lib/nes-45-monitor
sudo cp -a nes_monitor /opt/nes-45-monitor/
sudo cp config.example.ini /opt/nes-45-monitor/config.ini
sudo cp deploy/nes-45-monitor.service /etc/systemd/system/nes-45-monitor.service
```

Edit `/opt/nes-45-monitor/config.ini` and set:

```ini
state_db = /var/lib/nes-45-monitor/state.sqlite
```

Put the notifier secret in `/etc/nes-45-monitor.env` instead of the ini file:

```bash
sudo tee /etc/nes-45-monitor.env >/dev/null <<'EOF'
NES_NTFY_URL=https://ntfy.sh/a-long-unguessable-topic-name
EOF
sudo chmod 600 /etc/nes-45-monitor.env
sudo chown -R nes45:nes45 /opt/nes-45-monitor /var/lib/nes-45-monitor
```

Check the notifier, then start the service:

```bash
sudo bash -c 'set -a; . /etc/nes-45-monitor.env; set +a; cd /opt/nes-45-monitor; runuser --preserve-environment -u nes45 -- python3 -m nes_monitor --config /opt/nes-45-monitor/config.ini --test-notify'

sudo systemctl enable --now nes-45-monitor
sudo journalctl -u nes-45-monitor -f
```

The first check seeds the current page and logs any .45 listings already up without sending them. Listings posted after that are sent.

To get alerts for what is on the forum right now, stop the service, delete `/var/lib/nes-45-monitor/state.sqlite`, and run once with `--notify-existing` before starting it again. That sends one alert per current match.

## Try it locally

```bash
cp config.example.ini config.ini
python3 -m nes_monitor --dry-run
python3 -m unittest discover -s tests
```

`--dry-run` prints current matches and does not write the database or send alerts.
