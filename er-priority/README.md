# Atria application prototype

The Next.js frontend is in `frontend/`. The FastAPI API is in `../backend/`.
The public landing and waitlist are separate, in `../landing/`.

```sh
cd frontend
npm ci
npm run dev
```

Start the API from the repository root with `./scripts/dev.sh` to run both
services. The frontend forwards `/api/*` to `ATRIA_API_URL`, which defaults to
`http://127.0.0.1:8001`. Set it before a production build.

The home page lets visitors choose patient check-in or the nurse station.
Patients use `/checkin` and `/status/<id>`. Staff use `/nurse` and its intake,
assistant, trends, and nearby-department views.

See [the frontend guide](frontend/README.md) for fonts, verification, and Vercel
configuration, and [the repository README](../README.md) for the synthetic demo.
