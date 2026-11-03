# Mae Ann Laurel | Networking & IT Support

One-page, mobile-first, vanilla HTML/CSS/JavaScript portfolio with a **Python 3.13 FastAPI contact service**. Static profile information lives in version-controlled JavaScript modules. There is **no application database**, no CMS, and no frontend framework.

**Frontend:** Vercel static project at `https://mal.jpano.dev`  
**Backend:** separate Vercel FastAPI project with a Vercel-generated `https://...vercel.app` URL  
**Content updates:** edit the repository, push to GitHub, and let Vercel redeploy.

## Project structure

```text
anyang/
├── client/
│   ├── index.html, 404.html, build.py, vercel.json
│   ├── data/                  # profile.js, education.js, experience.js, skills.js
│   ├── scripts/               # vanilla JavaScript UI and contact form
│   ├── styles/                # theme, layout, components and responsive design
│   ├── assets/                # optimized images, networking M icon, local WOFF2 fonts
│   │   └── career/            # add Resume/CV PDFs here when available
│   ├── .env                  # local public config; ignored by Git
│   └── .env.example
├── server/
│   ├── app.py                # Vercel FastAPI entrypoint
│   ├── main.py               # local Uvicorn entrypoint
│   ├── api/contact.py        # validation, Turnstile, email submission
│   ├── core/config.py        # SMTP, origin and security configuration
│   ├── core/guard.py         # best-effort per-instance duplicate/rate guard
│   ├── services/email_service.py
│   ├── tools/                # dev launcher and ZIP packaging
│   ├── requirements.txt, pyproject.toml, .python-version
│   ├── .env                  # local private secrets; ignored by Git
│   └── .env.example
├── .env, .env.example         # nonsecret local ports / Python version
├── .gitignore
├── start.bat
├── zip.bat
└── README.md
```

The source ZIP includes **safe `.env` placeholders only**; real secrets should be entered in local ignored `.env` files and hosting-provider settings. The launcher creates any missing files from their `.env.example` templates, without overwriting existing settings.

## Run locally on Windows (Python 3.13)

1. Extract the archive to a fresh folder, not over an old `.venv`.
2. Open the folder in VS Code.
3. Run `py -3.13 --version` in a PowerShell terminal.
4. Run `./start.bat` or `.\start.bat` from the project root.
5. Open `http://127.0.0.1:3000` (frontend); health endpoint is `http://127.0.0.1:8000/api/health`.
6. Press Ctrl+C to stop the processes created by the launcher.

To view the frontend without dependencies, use `.\start.bat --frontend-only`. The launcher starts static HTML even if Python packages cannot be downloaded. It uses `server/.venv` with Python 3.13 and never changes your global Python 3.14 setup.

Select this interpreter in VS Code if needed: `server\.venv\Scripts\python.exe`.

## Editing portfolio information

- `client/data/profile.js`: name, professional title, student/graduate/work status, portrait caption, hero/about text, public email, WhatsApp, Resume/CV filenames, developer credit.
- `client/data/education.js`: uncomment and replace the documented template with approved education details.
- `client/data/experience.js`: add real roles, internships and training; do not publish example employers as facts.
- `client/data/skills.js`: review the displayed technical interests and professional skills; never claim proficiency without evidence.
- `client/index.html`: also review search metadata and no-JavaScript fallback copy after major identity changes.
- `client/assets/career/`: place actual PDFs matching the filenames in `profile.js`.

Fonts are included locally (Inter normal/italic and Manrope variable WOFF2). **No CDN is needed**. The networking-inspired M icon and both optimized portrait sizes are included.

## Deployment: two Vercel projects, one GitHub repository

### A. Deploy backend FIRST

1. Push the extracted project to your own GitHub repository (instructions below).
2. Visit `https://vercel.com/new`, import your repository.
3. Project Name: `mae-ann-portfolio-api` (any available name is fine).
4. **Root Directory:** `server` (important).
5. **Framework Preset:** `FastAPI` if detected. Keep the deployment build/output settings at the Python preset defaults. Do **not** set `client/dist` as backend output.
6. Python runtime: pinned to **3.13** by `server/.python-version` and `server/pyproject.toml`.
7. Environment Variables, **Production** (and Preview if you specifically need it):

```dotenv
APP_ENV=production
ALLOWED_ORIGINS=https://mal.jpano.dev
CONTACT_TO=<YOUR_OWNER_EMAIL>
CONTACT_SENDER_NAME=Mae Ann Laurel - Portfolio
SMTP_USER=<SMTP_SENDER_EMAIL_1>,<SMTP_SENDER_EMAIL_2>
SMTP_PASS=<SMTP_APP_PASSWORD_1>,<SMTP_APP_PASSWORD_2>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_TIMEOUT_SECONDS=5
SMTP_TOTAL_BUDGET_SECONDS=24
TURNSTILE_SECRET_KEY=<PRIVATE_CLOUDFLARE_TURNSTILE_SECRET>
TURNSTILE_ALLOWED_HOSTNAMES=mal.jpano.dev
TURNSTILE_REQUIRED=true
```

Replace all angle-bracket examples with real values in **Vercel Settings**, never in GitHub or client files. `SMTP_USER` and `SMTP_PASS` must contain the same number of comma-separated entries. To use separate SMTP hosts, ports, or passwords containing commas, use `SMTP_ACCOUNTS_JSON` as described in `server/.env.example`.

8. Deploy. Copy the **actual backend URL**, for example `https://mae-ann-portfolio-api-xxxxx.vercel.app`.
9. Visit `https://YOUR-BACKEND.vercel.app/api/health`; it should return `{"status":"ok",...}`. Also check `/api/contact/status`. It returns `ready:true` only after SMTP and Turnstile production configuration is complete.

**Important:** Backend API deployment can succeed even when `contact/status` reports not ready; this deliberately keeps email disabled until security/credentials are configured.

### B. Create Cloudflare Turnstile widget

1. In Cloudflare Dashboard > Turnstile, create a widget that accepts `mal.jpano.dev`.
2. Copy its **site key** for the public frontend project.
3. Copy its **secret key** for the private backend project (`TURNSTILE_SECRET_KEY`).
4. Token verification occurs **server-side** on every new submission. Production rejects contact submissions without configured Turnstile. Preview deployments need an explicitly allowed hostname; do not use wildcard origins.

### C. Deploy frontend SECOND

1. In Vercel, **Add New > Project**, import the **same GitHub repository** again.
2. Project Name: `mae-ann-portfolio` (or any name).
3. **Root Directory:** `client`.
4. **Framework Preset:** `Other` (static HTML/CSS/JS, no React/Next.js).
5. **Build Command:** `python3 build.py` (provided in `client/vercel.json`; if Vercel shows an override, use this exact command).
6. **Output Directory:** `dist` (also in `client/vercel.json`).
7. **Install Command:** leave default/empty. No Node packages are needed.
8. In Frontend project **Environment Variables (Production)**, set:

```dotenv
PUBLIC_API_BASE_URL=https://ACTUAL-BACKEND-PROJECT.vercel.app
PUBLIC_SITE_URL=https://mal.jpano.dev
PUBLIC_TURNSTILE_SITE_KEY=<PUBLIC_TURNSTILE_SITE_KEY>
```

9. Deploy. Open your generated `*.vercel.app` frontend preview to verify assets and links. Contact submission will require that the widget hostname matches the domain on which it is used.
10. Open Frontend Project > **Settings > Domains**, add `mal.jpano.dev`, and follow Vercel's project-specific DNS instructions.
11. If `jpano.dev` DNS is managed by Cloudflare: create/update the `mal` **CNAME** with the exact target Vercel displays. Use DNS-only initially to simplify verification; enable Cloudflare proxy after HTTPS is verified if desired.
12. Check `https://mal.jpano.dev` for correct themes, contact status, Turnstile and a real SMTP delivery to your recipient inbox.

**Production build safeguards:** `client/build.py` reads public production values from Vercel environment variables, **not** the local `client/.env`. A missing backend URL leaves the contact form unavailable rather than pointing visitors at `127.0.0.1`.

### Updating from GitHub

After the first successful deployment, changes on your Vercel production branch automatically trigger deployments. For typical content updates edit `client/data/*.js` and run:

```powershell
git status
git add -A
git diff --cached --stat
git commit -m "Update Mae Ann portfolio content"
git push origin main
```

Check `git branch --show-current` first. If your production branch is not `main`, use its actual name. Do not use `git push --force`.

### Git security

This package has no `.git` directory. If updating an existing repository, **clone the repository into a separate folder** and copy the new project contents into the clone without deleting `.git`; remove the obsolete tracked `database/` folder in the clone, review `git status` and then commit. Check `git remote -v` to confirm the destination. Real `.env` files must never be committed; use safe `.env.example` files and Vercel Environment Variables.

## Contact form, limitations and privacy

- The API validates names, email, subject, message, consent and request size; it uses a honeypot and Turnstile, and checks exact permitted browser origins.
- SMTP is delivered **through a separate sending account** to `CONTACT_TO`; the visitor's email is set to `Reply-To`. One account is attempted at a time, stopping after confirmed acceptance. Unexpected disconnections after SMTP DATA are **uncertain**; the app will **not** automatically send the same content again.
- The application has **no database**. A warm Python process keeps a short-lived in-memory request/rate guard. In Vercel serverless environments these counters are **not durable or shared between instances**, so global rate limits and exactly-once delivery **are not guaranteed**. Cloudflare Turnstile is required in production as the principal anti-bot layer.
- Messages may remain in your SMTP provider's outgoing mail records, your recipient inbox, and provider logs. Do not claim that no information is collected. The Privacy & Contact dialog describes these limitations.
- Vercel officially blocks SMTP port 25 but allows other outbound SMTP ports subject to provider/hosting limitations. SMTP port 587 should be **tested after deployment**. A third-party HTTPS email API is an option if the email provider refuses SMTP.
- A production backend requires exact HTTPS `ALLOWED_ORIGINS`, `TURNSTILE_SECRET_KEY`, and `TURNSTILE_ALLOWED_HOSTNAMES`.

## Clean source ZIP

Run `.\zip.bat` on Windows with Python 3.13. A sanitized ZIP is created **outside** the project directory. It excludes `.env` credentials, virtual environments, caches, database files, tests and generated assets, while including the three local fonts and their licenses.

## Troubleshooting

- `Python 3.14` selected: run `py -3.13 --version`, use `start.bat`, and select `server/.venv/Scripts/python.exe` in VS Code.
- pip says no matching distribution after `getaddrinfo failed`: check DNS/network to `pypi.org`, then retry. The frontend can run independently with `start.bat --frontend-only`.
- `/api/health` works but contact says not connected: check the backend project Environment Variables and redeploy. For production, SMTP recipient and Turnstile configuration are mandatory.
- Wrong API URL: `PUBLIC_API_BASE_URL` on **frontend** must be the backend project's HTTPS origin, not `mal.jpano.dev`, and not `127.0.0.1`.
- CORS issue: `ALLOWED_ORIGINS` on **backend** must include the exact `https://mal.jpano.dev` origin, no slash or wildcard.
- Wrong font: verify `client/assets/fonts/` WOFF2 files exist. They are included in this ZIP.
- Content changes are not visible: confirm the Git push reached Vercel's production branch and a new deployment succeeded. Check cached browser assets after deployment.

Useful references: [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi), [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python), [Domains](https://vercel.com/docs/domains/set-up-custom-domain), [Turnstile validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/).
