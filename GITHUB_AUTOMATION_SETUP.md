# GitHub automatizálás (felhőben, géptől függetlenül)

Ez a projekt tartalmaz időzített workflow-kat:
- `.github/workflows/rag-healthcheck.yml` -> 6 óránként + manuálisan
- `.github/workflows/cad-ai-radar.yml` -> óránként + manuálisan
- `.github/workflows/email-trigger-to-tasks.yml` -> óránként + manuálisan (email válasz -> TASKS)

`cad-ai-radar` forrásai (ingyenes API-k/public feed):
- arXiv API
- GitHub Search API
- HackerNews Algolia API
- Reddit JSON search API

## 1) Projekt feltöltése GitHubra

Ha még nincs git repo:

```powershell
cd "D:\GPT Projektek"
git init
git add .
git commit -m "Add GitHub Actions RAG healthcheck"
git branch -M main
git remote add origin https://github.com/<felhasznalo>/<repo>.git
git push -u origin main
```

Ha már van repo:

```powershell
cd "D:\GPT Projektek"
git add .
git commit -m "Add GitHub Actions RAG healthcheck"
git push
```

## 2) GitHub Secrets beállítása (böngészőben)

Repo -> `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

Kötelező:
- `WERISTO_MASTER_KEY` = az aktuális master kulcs
- `RESEND_API_KEY` = Resend API kulcs (kimenő email)
- `CAD_REPORT_TO` = `ottolokos@gmail.com`
- `CAD_REPORT_FROM` = pl. `info@weristo.de` (Resendben hitelesített feladó)
- `GMAIL_IMAP_USER` = figyelt Gmail cím (pl. `ottolokos@gmail.com`)
- `GMAIL_IMAP_APP_PASSWORD` = Gmail App Password

Opcionális:
- `TRIGGER_FROM_FILTER` = csak ettől a feladótól figyeljen (pl. `ottolokos@gmail.com`)

Opcionális:
- `WERISTO_RAG_URL` = `https://weristo.de/api/master/rag`
  - Ha nincs megadva, ez az alapértelmezett.

## 3) Első futtatás

Repo -> `Actions` -> `RAG Healthcheck` -> `Run workflow`

Majd:

Repo -> `Actions` -> `CAD AI SaaS Radar` -> `Run workflow`

Majd:

Repo -> `Actions` -> `Email Trigger To Tasks` -> `Run workflow`

Ha zöld, kész. Innentől GitHub felhőben fut, a saját gépedtől függetlenül.

## Email trigger minta

Ha a figyelt mailboxba ilyen szöveg érkezik, automatikusan felveszi a fejlesztési listába:
- `oksa ez egy jó funkció lenne nekünk, vedd fel fejlesztési tervbe`
- `feature request: ...`
- `backlog: ...`

## Biztonság

- A master key-t ne tedd kódba.
- A korábban használt kulcsot cseréld le.
