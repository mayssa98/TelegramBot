# React admin dashboard

The React dashboard is the mobile-first administration interface. The Python
application serves its production build at `/admin` and exposes the secured
JSON and form-action endpoints used by every React page. The former
server-rendered interface is retained only as an emergency fallback at
`/admin-legacy`.

## Development

```powershell
npm install
npm run dev
```

Vite proxies `/admin/api` requests to `http://localhost:8080`. Start the Python
server on that port and authenticate through `/admin` before using the local
frontend.

## Production build

```powershell
npm run build
```

The generated `dist` directory is committed because the Railway Python runtime
serves those static files directly and does not require Node.js at startup.
