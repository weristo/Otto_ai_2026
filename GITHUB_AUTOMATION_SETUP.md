# GitHub automatizálás (felhőben, géptől függetlenül)

Ez a projekt tartalmaz időzített workflow-kat:
- `.github/workflows/rag-healthcheck.yml` -> 6 óránként + manuálisan
- `.github/workflows/cad-ai-radar.yml` -> óránként + manuálisan

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

Opcionális:
- `WERISTO_RAG_URL` = `https://weristo.de/api/master/rag`
  - Ha nincs megadva, ez az alapértelmezett.

## 3) Első futtatás

Repo -> `Actions` -> `RAG Healthcheck` -> `Run workflow`

Majd:

Repo -> `Actions` -> `CAD AI SaaS Radar` -> `Run workflow`

Ha zöld, kész. Innentől GitHub felhőben fut, a saját gépedtől függetlenül.

## Biztonság

- A master key-t ne tedd kódba.
- A korábban használt kulcsot cseréld le.
