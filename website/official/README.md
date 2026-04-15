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
- Public contact: `hello@aaroncore.com`
- Current state: official site first, no public build yet
- Current tone: memory, continuity, action

## Local preview

Run a static file server from this directory:

```powershell
cd website/official
python -m http.server 8080
```

Then open [http://localhost:8080](http://localhost:8080).

## Recommended deployment: Cloudflare Pages

This site is already static output, so the lowest-friction overseas deployment is Cloudflare Pages.

Why it fits this repo well:

- works with private GitHub repositories
- no build step is required for the current site
- global CDN by default
- preview deployments on new pushes

### One-time Cloudflare setup

1. Create a Pages project in Cloudflare.
2. Choose **Connect to Git**.
3. Authorize GitHub and select this repository.
4. Use these build settings:

   - Framework preset: `None`
   - Build command: leave empty
   - Build output directory: `website/official`
   - Root directory: leave empty

5. Deploy.

For the current site, Cloudflare can publish the contents of `website/official/` directly.

### Custom domain later

If you want the Pages project to serve `aaroncore.com` later:

1. Add the custom domain in Cloudflare Pages.
2. Update DNS at your provider.
3. If the DNS zone is also moved into Cloudflare, the domain hookup becomes simpler.

If DNS stays elsewhere, keep the domain at the current provider and follow the DNS records Cloudflare gives you for the Pages project.

## Vercel alternative

Vercel also works well for static sites, but for private Git repositories the permissions and plan rules are a little more particular. If you want the least setup friction for a private repo, Cloudflare Pages is the safer default.

## GitHub Pages note

The repo still contains a GitHub Pages workflow at `.github/workflows/deploy-site.yml`, but that path is mainly useful if the repository is public again or the GitHub plan and organization settings allow private-repo Pages publishing.

## DNS and mailbox later

If DNS stays on Tencent Cloud, the next steps will mostly happen in Tencent Cloud DNS:

- Add the `A` or `CNAME` records for site deployment
- Add the `MX` and `TXT` records for mailbox verification
- Add `SPF`, `DKIM`, and `DMARC` when outbound mail is enabled

That means the page structure can keep evolving while the domain and mailbox are wired up later.
