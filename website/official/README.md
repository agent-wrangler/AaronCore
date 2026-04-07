# AaronCore Official Site

This directory contains the static official homepage for `AaronCore`.

## Layout

- `index.html`, `styles.css`, `app.js`
  The live homepage.
- `assets/`
  Production assets used by the live homepage.
- `lab/`
  Exploration pages and older logo or icon experiments.

## Homepage structure

The current page follows this sequence:

1. Hero
2. How it works
3. Core capabilities
4. Product proof
5. Use cases
6. Differentiators
7. Trust layer
8. Docs teaser
9. Final CTA

## Where to edit public-facing values

Mutable values live in `app.js`:

- `siteConfig.primaryDomain`
- `siteConfig.contactEmail`
- `siteConfig.contactStatus`
- `siteConfig.launchState`
- `siteConfig.releaseRoute`
- `siteConfig.betaUrl`
- `siteConfig.demoUrl`
- `siteConfig.docsUrl`

Release-state values stay in `releaseConfig`:

- `releaseConfig.available`
- `releaseConfig.url`
- `releaseConfig.version`
- `releaseConfig.noteWhenLocked`
- `releaseConfig.noteWhenOpen`

## Current public-facing details

- Primary domain: `aaroncore.com`
- Reserved mailbox: `hi@aaroncore.com`
- Current state: official site first, no public build yet
- Current tone: memory-first, execution-oriented, built to evolve

## Local preview

Run a static file server from this directory:

```powershell
cd C:\Users\36459\NovaCore\website\official
python -m http.server 8080
```

Then open [http://localhost:8080](http://localhost:8080).

## DNS and mailbox later

If DNS stays on Tencent Cloud, the next steps will mostly happen in Tencent Cloud DNS:

- Add the `A` or `CNAME` records for site deployment
- Add the `MX` and `TXT` records for mailbox verification
- Add `SPF`, `DKIM`, and `DMARC` when outbound mail is enabled

That means the page structure can keep evolving while the domain and mailbox are wired up later.
