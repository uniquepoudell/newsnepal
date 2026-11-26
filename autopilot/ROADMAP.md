# Roadmap (ranked, top = next)

Rank by: more readers or more income per hour of work. Keep each item small enough for one run, or split it.

## Next
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

## Done
- 2026-11-26: redesign, logo, topic chips, search, dark mode, share, ticker, support page with Stripe link.
- 2026-11-26: AI illustrations for stories without a publisher picture (v2 prompt, web-sized).
