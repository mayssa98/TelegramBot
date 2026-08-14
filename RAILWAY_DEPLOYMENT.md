# Railway deployment

The production service now runs entirely on Railway: Telegram webhook, admin
dashboard, public assets, buyer API, restock checks, and supplier price checks.

## 1. Generate the public domain

In the Railway service, open **Settings > Networking > Public Networking** and
select **Generate Domain**. The application automatically reads Railway's
`RAILWAY_PUBLIC_DOMAIN`; `HP_PUBLIC_BASE_URL` can remain unset.

## 2. Configure variables

Copy the real values from the previous production environment. Never use the
literal value `[SENSITIVE]`.

Required variables:

- `HP_BOT_TOKEN`
- `HP_ADMIN_ID`
- `HP_MONGODB_URI`
- `HP_MONGODB_DB=heavenprem`
- `HP_WEBHOOK_SECRET` (letters, numbers, `_` and `-` only)
- `CRON_SECRET` (a different random value, at least 24 characters)
- `HP_DASHBOARD_PASSWORD`
- `HP_INVENTORY_KEY` when encrypted inventory is enabled
- Provider API keys used by the active catalog
- `HP_REQUIRED_CHANNEL=@blackmarketBotChannel`
- `HP_BOT_USERNAME=blackmarketa_bot`

Generate independent webhook and cron secrets locally with PowerShell:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLower()
```

Run the command twice and store the two different results in Railway. Do not
commit either result.

## 3. Deploy

`railway.json` starts `python railway_server.py`, checks `/health`, binds to
Railway's injected `PORT`, and keeps one European replica. On startup, the
service registers `${RAILWAY_PUBLIC_DOMAIN}/api/webhook` with Telegram.

After deployment, confirm:

- `https://YOUR-DOMAIN/health` returns `{"ok": true, ...}`.
- `https://YOUR-DOMAIN/` opens the public bot page.
- `https://YOUR-DOMAIN/admin` requests the dashboard password.
- Railway logs contain `Telegram webhook registered`.

The process runs its own restock and supplier-price scheduler, replacing the
two Vercel cron entries. Keep exactly one Railway replica to prevent duplicate
scheduled announcements.
