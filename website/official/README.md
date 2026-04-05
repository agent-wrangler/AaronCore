# AaronCore Official Site

This directory contains the static official site for `AaronCore`. It does not change the current desktop app runtime.

## Layout

- `index.html`, `styles.css`, `app.js`
  Official site files for the current homepage.
- `assets/`
  Shared production assets used by the live site.
- `lab/`
  Experimental pages and older logo or icon exploration files.

## Where to edit public-facing info

The mutable brand and contact values are now grouped in `app.js` under `siteConfig`:

- `siteConfig.primaryDomain`
- `siteConfig.contactEmail`
- `siteConfig.contactStatus`
- `siteConfig.launchState`
- `siteConfig.releaseRoute`

The download state stays in `releaseConfig`:

- `releaseConfig.available`
- `releaseConfig.url`
- `releaseConfig.version`
- `releaseConfig.noteWhenLocked`
- `releaseConfig.noteWhenOpen`

## Current public info

- Primary domain: `aaroncore.com`
- Reserved contact mailbox: `hi@aaroncore.com`
- Current launch state: official site first, no public build yet
- Site role: brand entry, download state, release notes, future updates

## Local preview

Run a static file server from this directory:

```powershell
cd C:\Users\36459\NovaCore\website\official
python -m http.server 8080
```

Then open [http://localhost:8080](http://localhost:8080).

## Domain and mailbox later

If DNS stays on Tencent Cloud, the next steps will mostly happen in the Tencent Cloud DNS console:

- Add the `A` or `CNAME` records for the official site deployment
- Add the `MX` and `TXT` records for mailbox verification
- Add `SPF`, `DKIM`, and `DMARC` when outbound mail is enabled

That means the page structure is already ready. Later you only need deployment and DNS changes, not another site rewrite.
