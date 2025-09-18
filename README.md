
# HOROSKOP.ONE — Gold Standard Frontend

This package sets up:
- **Prebuild via esbuild** (no in-browser Babel)
- **CSP** and **SRI** (script tag integrity filled at build time)
- **Geocoding Autocomplete** using OSM Nominatim (with 1 req/s throttle & debounce)
- **Share-Card** generator (PNG 1200×630) for social sharing
- **Seeded permalinks** and tone modes (balanced / skeptic / poetic / trailer)

## Quickstart

```bash
npm i
npm run build
# serve /dist (e.g.) npx http-server dist -p 5173
```

For development:

```bash
npm run dev
# open http://localhost:5173 (or your static server) pointing to dist/
```

### Why esbuild?
- Bundles your TS/JS into `dist/assets/main.js`
- No inline scripts → strict CSP compatible
- Build script computes **SRI** (sha384) and injects it into `index.html`

### CSP
- See `<meta http-equiv="Content-Security-Policy">` in `public/index.html`
- Netlify/CF headers also included in `/_headers` (copied to `dist/` on build).
- If you host elsewhere, configure equivalent server headers.

### Nominatim usage
- We throttle to **≥1.1s** per request and debounce inputs by **400ms**.
- Consider setting `email` query parameter in `src/geocode.ts` to identify your app for OSM.
- Do **not** cache personal queries on your server without consent.

### Backend API
- The frontend posts to: `https://horoskopone-production.up.railway.app/reading`
- Payload includes `birthDate` in `DD.MM.YYYY`, optional `birthTime`, `approxDaypart`, `period`, `coords` and `mode`.
- There is a fallback to `/readings` if needed.

### Share-Card
- Generates a clean PNG (Twitter/OpenGraph size 1200×630)
- Pulls top 3 `highlights` (or first 3 sections) from the API response
- Download via **"Card downloaden"**

### Seeds & Permalinks
- Permalink at footer updates with current form values and a stable `seed`.
- Use it to reproduce a reading exactly (client will pass `seed` to backend).

---

## Project Layout
```
public/
  index.html     # CSP meta, no inline JS. Placeholders __APP_JS__/__INTEGRITY__ filled at build.
  styles.css
src/
  main.ts        # app bootstrap
  geocode.ts     # autocomplete (OSM)
  readingApi.ts  # backend client
  sharecard.ts   # PNG card renderer
  zodiac.ts      # decorative wheel
scripts/
  build.mjs      # esbuild + SRI injection + copy
_headers         # optional Netlify headers (CSP etc.)
```

---

### Roadmap (optional)
- Move `style-src` away from `'unsafe-inline'` by extracting all inline styles & adding nonces/hashes.
- Add Worker cache for idempotent readings (seed+params key).
