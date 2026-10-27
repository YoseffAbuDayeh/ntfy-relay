# ntfy-relay

A small Docker Compose stack that self-hosts [ntfy](https://ntfy.sh) and runs one lightweight Python listener container per notification source. Each listener watches its source and pushes events to its own ntfy topic, which a phone receives through the ntfy app, with no Google Play Services (FCM) required.

Built for a de-Googled Android phone (LineageOS without GApps) with a Raspberry Pi as the always-on host.

## Motivation

Many apps depend on Google's FCM for push notifications, so on a phone running LineageOS without GApps they never alert. Discord is a good example, and it is worse with several accounts: the official app keeps one active session, so notifications for the other accounts are unreliable or missing.

ntfy sidesteps FCM with its own persistent connection, and a self-hosted server keeps the data on hardware you control. This project runs the relay as isolated containers, one per account, so each account gets its own topic and its own labelled notifications on the phone, whether or not it is the active account in the app.

## Architecture

```
 source A ──► listener "acc1" ──┐
 source B ──► listener "acc2" ──┼──► ntfy server ──► phone (ntfy app)
 source C ──► listener "acc3" ──┘      (Pi)
```

| Service | Image | Role |
|---------|-------|------|
| `ntfy` | `binwiederhier/ntfy` | Self-hosted push server, web UI, and topic API |
| `acc1`, `acc2`, `acc3` | `python:3.12-slim` | One listener per source; each runs the same `notify.py` with its own credentials and topic |

Design choices:

- **One container per source.** A crash or auth failure in one listener never affects the others.
- **One script, many containers.** `notify.py` only reads `NTFY_URL`, `DISCORD_TOKEN`-style credentials, and `ACCOUNT` from its environment. Compose decides what each container receives, so adding a source is a copy-paste of a compose block.
- **Internal networking.** Listeners reach ntfy at `http://ntfy/<topic>` over the Compose network. Only ntfy's port is published to the host.
- **Self-healing.** `restart: unless-stopped` brings every service back after a reboot.
- **Secrets stay out of the repo.** Credentials live in `.env`, which is git-ignored.

## Requirements

- Docker with the Compose plugin (`docker compose version`)
- A host that is always on (tested on Raspberry Pi OS / Debian 12, arm64)
- The ntfy app on your phone (F-Droid build recommended for instant delivery)

## Quick start

```bash
git clone https://github.com/YoseffAbuDayeh/ntfy-relay.git
cd ntfy-relay

cp .env.example .env
chmod 600 .env
nano .env                 # fill in credentials, no quotes around values

docker compose up -d
docker compose ps
docker compose logs --tail 20 acc1
```

Test that ntfy itself works:

```bash
curl -H "Title: [Test] hello" -d "it works" http://localhost:8090/acc1-topic
```

Then open `http://<host-ip>:8090` in a browser and subscribe to the topic.

## Configuration

Compose passes these environment variables to each listener:

| Variable | Example | Purpose |
|----------|---------|---------|
| `NTFY_URL` | `http://ntfy/acc1-topic` | Topic the listener publishes to |
| `ACCOUNT` | `Main` | Label shown in the notification title, e.g. `[Main] Alex (DM)` |
| credential | `${TOKEN1}` | Read from `.env` on the host |

Use unguessable topic names (for example `acc1-x7k2q9`). By default anyone who can reach the server and knows a topic name can read it. For anything exposed beyond your LAN, enable ntfy [access control](https://docs.ntfy.sh/config/#access-control).

### Adding another listener

Copy an existing listener block in `docker-compose.yml`, then change the service name, topic, `ACCOUNT` label, and the `.env` variable:

```yaml
  acc4:
    image: python:3.12-slim
    working_dir: /app
    volumes: ["./notify.py:/app/notify.py:ro"]
    command: sh -c "pip install -q aiohttp && python notify.py"
    environment:
      NTFY_URL: http://ntfy/acc4-topic
      ACCOUNT: Fourth
    depends_on: [ntfy]
    restart: unless-stopped
```

Add the new credential to `.env`, then `docker compose up -d`.

### Adapting the listener

`notify.py` is the only source-specific piece. To relay a different kind of event (an RSS feed, a status page, a webhook receiver), replace the event handler and keep the final step, which is a single HTTP POST to `NTFY_URL` with the message as the body and the title as a `Title` header.

## Phone setup

1. Install the ntfy app (F-Droid).
2. Settings → Default server → `http://<host-ip>:8090`.
3. Subscribe to your topics and enable **Instant delivery** so the app keeps a persistent connection.
4. For access away from home, put the host and phone on [Tailscale](https://tailscale.com) and use the host's tailnet address. Avoid forwarding the port on your router.

## Operations

```bash
docker compose ps                         # status
docker compose logs --tail 30 <service>   # recent logs
docker compose up -d                      # apply compose/.env changes
docker compose restart <service>          # reload a changed notify.py
docker compose down                       # stop and remove containers
```

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| `address already in use` on start | Another service owns the host port. Check with `sudo ss -tlnp \| grep <port>` and change the left side of `ports:` in the ntfy block |
| `docker compose` is not a command | Compose plugin missing. Install `docker-compose-plugin` from Docker's Debian repo |
| `permission denied ... docker.sock` | `sudo usermod -aG docker $USER`, then log out and back in |
| Listener keeps restarting | `docker compose logs --tail 30 <service>`. A `KeyError` means a missing environment variable; auth errors mean a bad credential |
| Edited `.env` has no effect | Use `docker compose up -d`; `restart` does not reload `.env` |
| `can't find '__main__' module` | The bind-mounted `notify.py` did not exist when Compose started, so Docker created a directory. Remove it and add the real file |
| Notifications stop on the phone | Confirm the app's server URL and port, that the topics are subscribed, and that battery optimization is disabled for ntfy |

## Project layout

```
ntfy-relay/
├── docker-compose.yml   # ntfy + listeners
├── notify.py            # listener: source event -> ntfy POST
├── .env.example         # credential template
├── .gitignore           # keeps .env out of git
└── README.md
```

## Security notes

- Never commit `.env`. If a credential is ever committed, rotate it immediately; deleting it from a later commit does not remove it from history.
- Keep the ntfy port off the public internet unless auth is enabled.
- Only monitor accounts and sources you own and are permitted to automate, and follow each service's terms of use.

## Discord notes

Discord only delivers push notifications through FCM and does not support UnifiedPush, so a relay needs a source that can see the events. The listener interface here is deliberately small (an event goes in, one HTTP POST to ntfy comes out), which keeps the Discord-specific part swappable.

- **Bot listener (compliant).** A Discord bot with the message-content intent can relay mentions and messages from servers you own or administer. It cannot see DMs or servers it has not been added to.
- **Automating a user account.** Reading a personal account's DMs requires logging in with its user token, which Discord's Terms of Service prohibit and which can get the account banned. That implementation is intentionally not included in this repository.
- **No-code alternatives.** microG (FCM without Google Play Services) or separate Android work profiles (Shelter or Island) with one Discord install each both solve the multi-account problem within the ToS.

## License

MIT
