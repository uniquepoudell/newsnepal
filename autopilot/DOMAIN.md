# Moving News Nepal to your own domain

Everything (code, settings, autopilot records) is in this GitHub repo, so nothing needs copying. The site
already supports a custom domain.

1. Buy the domain (for example a .com or .com.np).
2. In GitHub: repo **Settings → Secrets and variables → Actions → Variables → New repository variable**:
   name `CUSTOM_DOMAIN`, value `yourdomain.com` (no https).
3. At your DNS (Cloudflare or the registrar):
   - for `www.yourdomain.com`: CNAME to `uniquepoudell.github.io`
   - for the bare `yourdomain.com`: A records `185.199.108.153`, `185.199.109.153`, `185.199.110.153`,
     `185.199.111.153`
4. Repo **Settings → Pages → Custom domain**: enter the domain, wait for the check, tick **Enforce HTTPS**.
5. Run the "Build and publish" workflow once. Links, sitemap and the canonical address switch to the new domain.
6. Tell Claude in the project, so the autopilot updates Search Console steps and AdSense steps.
