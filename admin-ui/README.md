# React admin dashboard

The React dashboard is the mobile-first replacement for the server-rendered
admin interface. The production build is served by the Python application at
`/admin-v2`; the existing dashboard remains available at `/admin` while its
remaining pages are migrated.

## Development

```powershell
npm install
npm run dev
```

Vite proxies `/admin/api` requests to `http://localhost:8080`. Start the Python
server on that port and authenticate through `/admin-v2` before using the local
frontend.

## Production build

```powershell
npm run build
```

The generated `dist` directory is committed because the Railway Python runtime
serves those static files directly and does not require Node.js at startup.
