# ER Priority (live waiting room frontend)

Next.js app for patient check-in and the staff ER dashboard, backed by the Atria FastAPI service in `../backend`.

```
npm ci
npm run dev   # http://localhost:3000
```

`/api/*` is proxied to `ATRIA_API_URL` (default `http://127.0.0.1:8001`). For a production build, set it before `npm run build`, because Next reads rewrites at build time.

- `/` staff workspace: ER dashboard, patient intake, Ask Atria
- `/checkin` patient check-in (phone / QR code)
- `/status/<id>` the patient's ticket and place in line

See the repo README for the full demo flow.
