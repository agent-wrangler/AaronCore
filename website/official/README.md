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
2. Memory thesis
3. Memory proof
4. Memory highlights
5. Beta CTA

## Where to edit public-facing values

Mutable values live in `app.js`:

- `siteConfig.primaryDomain`
- `siteConfig.contactLabel`
- `siteConfig.contactUrl`
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
- Public contact: `GitHub Issues`
- Current state: official site first, no public build yet
- Current tone: memory, continuity, action

## Local preview

Run a static file server from this directory:

```powershell
cd website/official
python -m http.server 8080
```

Then open [http://localhost:8080](http://localhost:8080).

## GitHub Pages deployment

This repo now includes a GitHub Pages workflow:

- `.github/workflows/deploy-site.yml`

What it does:

1. watches `master`
2. only reacts when `website/official/**` or the workflow itself changes
3. uploads `website/official/` as the Pages artifact
4. deploys the static site through GitHub Pages

### One-time GitHub setup

1. Open the repository on GitHub.
2. Go to `Settings -> Pages`.
3. Under **Build and deployment**, choose **GitHub Actions** as the source.
4. Push to `master` or run the workflow manually from the **Actions** tab.

### Custom domain later

If you want GitHub Pages to serve your own domain:

1. Add your domain in `Settings -> Pages`.
2. Update DNS at your provider.
3. Optionally add a `CNAME` file inside `website/official/` containing just the domain name.

For example:

```text
aaroncore.com
```

If you plan to switch between GitHub Pages and another host, it is safer to add the custom domain in GitHub first and only commit the `CNAME` file once the final domain path is settled.

## DNS and mailbox later

If DNS stays on Tencent Cloud, the next steps will mostly happen in Tencent Cloud DNS:

- Add the `A` or `CNAME` records for site deployment
- Add the `MX` and `TXT` records for mailbox verification
- Add `SPF`, `DKIM`, and `DMARC` when outbound mail is enabled

That means the page structure can keep evolving while the domain and mailbox are wired up later.
