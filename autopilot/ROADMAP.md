# Roadmap (ranked, top = next)

Rank by: more readers or more income per hour of work. Keep each item small enough for one run, or split it.

## Next
0a. **Fast-money pivot (owner, 2026-11-26: "find something which can earn asap").** The site gets almost no
    visitors, and a news aggregator ranks poorly in Google because the stories are on other sites too. Build
    daily *utility* pages that people search every day and that we can fill from official or open data:
    - ~~"AUD to NPR today" and "NRB exchange rate today" pages~~ Done 2026-11-26 (PR #12, `rates.html`).
    - **Next: daily dated rate pages.** Keep each day's NRB table at `rates/YYYY-MM-DD.html` (plus a small archive
      list and "change since yesterday" arrows on `rates.html`), in the sitemap. Search shows ShareSansar
      publishing one dated "today's rate" post every day; fresh dated pages are how rate searches get caught.
      Needs history: commit `rates.json` snapshots or read yesterday's from the live site like `items.json`.
    - Per-currency landing pages for the big remittance corridors: `rates/sar-to-npr.html`, `qar-`, `aed-`,
      `myr-`, `krw-`, `usd-`, each with an amounts table and the GorkhaPay link.
    - "Gold and silver price today in Nepal" (only from the official FENEGOSIDA published rate; skip if no
      reliable source can be read automatically).
    - "IPO calendar Nepal": open and upcoming IPOs from the NEPSE / SEBON news we already collect, with links to
      the official result checker (never ask readers for their BOID or login).
0b. **Daily share card.** Each build makes a square "Today in Nepal money" image (rates, NEPSE line, 3 headlines)
    and a caption in English and Nepali, saved at `/share/today.png` and `/share/today.txt`, so the owner can post
    it to Facebook, TikTok or Viber groups in 30 seconds. Never post automatically.
0c. **Sell what we already have.** Link the GorkhaPay checklists (A$5, already on sale) from visa stories and the
    visa pages, as a clearly labelled product box.
1. **Story and topic pages for search traffic.** Topic pages (`/topic/nepse.html`, `/topic/nrb.html`,
   `/topic/bitcoin.html`, `/topic/student-visa.html`…) with their own title, description, intro paragraph and the
   matching stories. Add them to the sitemap and nav. Search engines rank pages, not one long home page.
2. **SEO basics on every page.** Open Graph and Twitter card tags with the story or topic picture, canonical
   URLs, JSON-LD (`NewsArticle` list / `WebSite` with search), and a better `<title>` and description per page.
3. **Daily email digest, ready to switch on.** Build the digest HTML and RSS-to-email feed and a signup box that
   stays hidden until the owner picks a provider (Buttondown, MailerLite or Beehiiv free tier). List the signup
   in `INCOME.md`. An email list is the strongest income asset a small news site can own.
4. **Speed.** Lazy-load images below the fold, set width and height on images, inline the critical CSS, and
   keep each page small. Record before and after page sizes in `log.md`.
5. **"Most read" and "Today in 60 seconds".** A short daily summary block at the top (headline list, rates,
   NEPSE move) that is easy to share on Facebook and Viber, with a share-image card.
6. **PWA.** Manifest and a small service worker so readers can add the site to their home screen and read the
   last version offline.
7. **NEPSE and rates widgets.** A daily NEPSE index line and NRB rate table page (from official sources only),
   good for search ("NRB exchange rate today", "NEPSE today").
8. **Sponsor slot.** A clearly labelled "Sponsored" card in the feed and on topic pages, empty until the owner
   signs a sponsor. Add a "Advertise with us" page with audience info (no invented numbers).
9. **Better Nepali.** Once the owner adds `ANTHROPIC_API_KEY`, check translations and the Nepali pages' titles.
10. **Feed quality.** Drop off-topic stories, add good feeds (official NRB, SEBON, Home Affairs), dedupe better.
    2026-11-26 build: SBS Nepali keeps 1 of 69 and "Nepali news: Australia visa" 0 of 3; check their keyword match.

## Done
- 2026-11-26: Rates page: AUD to NPR today, full NRB table (22 currencies), converter, GorkhaPay link (PR #12).
- 2026-11-26: redesign, logo, topic chips, search, dark mode, share, ticker, support page with Stripe link.
- 2026-11-26: AI illustrations for stories without a publisher picture (v2 prompt, web-sized).
