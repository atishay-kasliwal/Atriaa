# Atria - ER reassessment demo (2-hour build)

## 1. Supabase
1. Create a project at supabase.com.
2. Open SQL Editor, paste the contents of `atria_schema.sql`, run it. This creates `patients`, `events`, `audit_log` and seeds the 4 demo patients (Bay 7, Bay 4, Bay 2, Bay 9).
3. Go to Project Settings -> API. Copy the Project URL and the **service_role** key (not the anon key).

## 2. Gemini
Get an API key from Google AI Studio (aistudio.google.com/apikey).

## 3. Backend
```
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY
uvicorn main:app --reload --port 8000
```

## 4. Frontend
Just open `frontend/index.html` in a browser (it calls http://localhost:8000 directly).
If opening the file directly causes issues, serve it instead:
```
cd frontend
python3 -m http.server 5500
```
then visit http://localhost:5500.

## 5. Verify the demo
Open the board. Bay 4 should show `persistent_change` and rank above Bay 7 (which stays `stable` despite its higher intake ESI). Bay 9's one-off spike should resolve back to `stable`, and Bay 2's long wait should not push it to the top. Click a row to see intake/current/delta, the timeline, and the action buttons. Ask Atria a question like "Why did Bay 4 move above Bay 7?" and confirm the answer cites actual numbers and timestamps, not invented ones.

## Notes
- The service_role key bypasses Row Level Security - fine for this demo, never ship it to a frontend in production.
- The trend engine (`classify_trajectory` in `main.py`) is plain Python, not a model - persistent_change requires at least 2 of 3 signals (HR up, SpO2 down, pain up) to move the same direction on every consecutive reading, so a single spike that reverses does not count.
- Gemini is only ever given computed evidence and is instructed not to invent facts, diagnose, or recommend treatment.
