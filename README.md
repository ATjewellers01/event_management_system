# Event Hub

Lead capture for jewellery trade shows. Staff scan business cards or enter
visitors by hand; visitors can also self-register by scanning a QR code at the
stand. Cards are read with OCR.

Built for JewelFactory (AT Jewellers) by Botivate.

## Architecture

```
Browser ──► FastAPI (backend/) ──► Turso        (all data)
                              ├──► Cloudinary   (card images, WebP)
                              └──► OpenAI       (card OCR)
                              └──► Groq         (transliteration)
```

- **Turso (libSQL)** is the only data store: events, team members, scanned
  cards, visitors and the company profile.
- **Cloudinary** stores card photos, capped at 1600px and saved as WebP only.
  WebP rather than AVIF because GPT-4o vision accepts png/jpeg/gif/webp and
  rejects AVIF — an AVIF-only store would break any future re-OCR of a card.
- **No response cache.** Turso answers in tens of milliseconds, so a TTL cache
  would add staleness and invalidation complexity for almost no gain.

Google Sheets, Apps Script and Google Drive were the original backend and have
been removed. They were the cause of 3-40 second page loads and intermittent
"stream not found" / "unable to open the file" failures.

## Card pipeline

1. **OCR** — GPT-4o vision reads both sides of the card. Output is forced to
   English/Latin script; Indic-script names are transliterated rather than
   translated, so `श्री जिनकुशल ज्वेलर्स` becomes `Shri Jinkushal Jewellers`.
2. **Store** — images to Cloudinary as WebP, row to Turso.

There is no enrichment step. It resolved the company website, scraped it and
looked up registration data, but every field it produced (industry, website,
trust score, key people, social media) was dropped when the tables moved to one
shared layout — so it was spending three Google searches and an LLM call per
scan on data nothing reads. Removing it took a scan from 20-60s to about 8s.

The OCR prompt defines every field explicitly, because a loose prompt put
values in the wrong columns.

## Pages

| Route | What it is |
|---|---|
| `/` | Event list, card scanner, New Visitor form, per-event drilldown |
| `/leads` | Leads Database — all scanned cards and all visitors |
| `/visitor-form/{eventId}` | Public self-registration form behind the QR code |
| `/scanner/` | BotivateScanner React app (built separately) |
| `/api/health` | Database and image-storage status |

## Setup

Requires Python 3.10 (see `.python-version`).

```bash
# 1. Dependencies
uv venv --python 3.10 .venv
uv pip install -r requirements.txt

# 2. Configuration
cp backend/.env.example backend/.env
#    then fill in the values — that file documents what each one does

# 3. Run
uv run python run.py        # http://127.0.0.1:8000
```

To build the React scanner app (only needed if you change it):

```bash
cd BotivateScanner && npm install && npm run build
```

`/scanner/` returns 404 until `BotivateScanner/dist` exists.

## Deployment

Production runs on AWS EC2 (`ap-south-1`, same region as the Turso database)
behind nginx, in a Docker container built from the `Dockerfile`.

```bash
cd /home/ubuntu/app && git pull origin <branch>
docker build -t eventhub-app:<tag> .
docker stop event-hub && docker rm event-hub
docker run -d --name event-hub --restart unless-stopped \
  -p 127.0.0.1:8000:8000 --env-file /home/ubuntu/app/backend/.env eventhub-app:<tag>
```

Keep the previous image tagged so a bad deploy can be rolled back by re-running
the last command against it.

nginx proxies `event.zold.in` to `127.0.0.1:8000`, so that port mapping must stay
as above. The instance is registered with AWS SSM, so these steps can also be run
remotely via `aws ssm send-command`.

## Notes

- **Row identity.** Cards and visitors are addressed by database primary key,
  exposed to the frontend as `_id`. The earlier Sheets version updated rows by
  position, which silently edited the wrong row when rows were added or removed.
- **Partial updates.** Update endpoints write only the fields present in the
  request, so the inline Tag dropdown cannot blank the rest of a row.
- **Tags and Groups** are set from the Customer Data tables after a visitor is
  created, not on the entry forms.
- **Pincode.** Both visitor forms auto-fill city and state from the pincode via
  `api.postalpincode.in`. Both fields stay editable, and a lookup failure never
  blocks the form.
- **Connection reuse.** The Turso handshake is ~115ms, which dominated query
  time, so one connection is shared with a reconnect guard for stale streams.
