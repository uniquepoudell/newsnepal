# News Nepal Crypto: setup, hosting and income guide

The site is built. This guide covers the steps that need your own accounts, then how the site can earn money.

**How it works in one line:** every hour GitHub fetches crypto and Nepal finance news, keeps only on-topic
stories, rebuilds the page and publishes it for free on GitHub Pages. Your `newsnepal.crypto` domain (and later a
normal `.com`) points at that page.

---

## Part 1. Put the site online (about 10 minutes)

### Step 1. Create the repository
1. Go to <https://github.com/new> while signed in as **uniquepoudell**.
2. Repository name: `newsnepal`. Choose **Public** (free GitHub Pages needs a public repo).
3. Leave "Add a README" unticked, then click **Create repository**.
4. Tell Claude in the project thread that it exists. Claude will push the code.
   (Or upload the files yourself: **Add file > Upload files**, and drag in everything from the `newsnepal` folder.)

### Step 2. Turn on GitHub Pages
1. In the repo, open **Settings > Pages**.
2. Under **Build and deployment > Source**, pick **GitHub Actions**.
3. Open the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
4. Click **Build and publish > Run workflow**. After about a minute your site is live at
   **https://uniquepoudell.github.io/newsnepal/**. From then on it updates by itself every hour.

### Step 3. Point newsnepal.crypto at the site
1. Sign in at <https://unstoppabledomains.com> (you used your Gmail account) and open **My Domains**.
2. Note which wallet `newsnepal.crypto` belongs to. If it is a wallet you no longer control, contact
   Unstoppable support before going further, because you can't edit records without it.
3. Click `newsnepal.crypto` > **Manage** > **Website**.
4. Choose the **redirect / forwarding URL** option and enter `https://uniquepoudell.github.io/newsnepal/`
   (or your `.com` once you have one). Save. This is the best option because the site changes every hour and the
   redirect never needs updating.
5. Saving may ask you to confirm with your wallet. Domains on Polygon usually have free edits. If it asks for a
   gas fee on Ethereum, check the amount before you approve.
6. Do the same for `nepaltrade.crypto` later if you want it to point somewhere.

**Who can open a .crypto address?** Brave and Opera open `.crypto` sites directly. Chrome, Safari and Firefox need
the Unstoppable Domains extension. That's why most of your real visitors will come through the normal web address
(Step 5). Use `newsnepal.crypto` as your brand, your donation address and a link for crypto-savvy readers.

### Step 4 (optional). Keep a copy on IPFS
IPFS is only useful if you want a censorship-resistant snapshot. An IPFS record points at one fixed version,
so it won't update hourly on its own.
1. Create a free account at <https://pinata.cloud>, then **API Keys > New Key**, with "pinFileToIPFS" allowed. Copy the **JWT**.
2. In the GitHub repo: **Settings > Secrets and variables > Actions > New repository secret**. Name `PINATA_JWT`, value the JWT.
3. Run the workflow by hand (**Actions > Build and publish > Run workflow**). The run summary shows a **CID**.
4. In Unstoppable Domains, **Website > IPFS**, paste that CID. Repeat when you want to refresh the snapshot.

### Step 5. Add a normal domain (strongly recommended for income)
Google search, Google AdSense and most sponsors only work with a normal domain.
1. Buy a matching name, for example a `.com` from Cloudflare, Namecheap or Porkbun (about US$10 a year), or a free
   `.com.np` from <https://register.com.np> (needs Nepali documents).
2. In your domain's DNS settings add:
   - four **A** records for `@`: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - a **CNAME** record for `www`: `uniquepoudell.github.io`
3. In the GitHub repo: **Settings > Secrets and variables > Actions > Variables > New variable**.
   Name `CUSTOM_DOMAIN`, value your domain, for example `newsnepalcrypto.com`.
4. **Settings > Pages > Custom domain**: enter the same domain, save, and tick **Enforce HTTPS** once it allows.
5. Change the `newsnepal.crypto` redirect (Step 3) to the new domain.

---

## Part 2. Fill in your money settings

Everything lives in the `monetization` section of `config.json`. Edit it on github.com (click the file, then the
pencil icon) and commit. The site rebuilds within a minute. Empty values stay hidden on the page.

| Setting | What to put |
|---|---|
| `adsense_client` | Your AdSense id, like `ca-pub-1234567890123456`. The build adds `ads.txt` for you. |
| `adsense_slot_top`, `adsense_slot_feed` | Ad unit ids from AdSense. The feed ad shows every `ad_every_n_items` stories. |
| `sponsor.text`, `sponsor.url` | A sponsor's line and link for the sidebar. |
| `affiliate_links` | Label, URL and short note for each link. |
| `donations.addresses` | Your public wallet addresses. Only the **public** address, never a seed phrase or private key. |
| `contact_email` | Shown in the footer so sponsors can reach you. Use a separate address if you want privacy. |

To preview the empty ad spots on your own computer: `SHOW_AD_PLACEHOLDERS=1 python scripts/build.py`.

---

## Part 3. How this domain can make money

To be honest about the size of it: a headline site earns from **traffic**, and traffic takes months to build.
Display ads usually pay about US$0.20 to $1 per 1,000 page views from Nepal, and roughly $2 to $8 from US,
UK or Australian readers interested in crypto. So 30,000 views a month might bring $10 to $150 from ads alone.
The bigger money usually comes from sponsors and a newsletter once you have regular readers.

Ranked from quickest to biggest:

1. **Donations at newsnepal.crypto.** Free to set up. Small but immediate. Only accept tips where receiving crypto is legal for you.
2. **Display ads.** Apply to Google AdSense once you have the `.com` and some original articles (see below).
   AdSense often rejects sites that only list other people's headlines, so original posts matter. Alternatives
   that accept smaller sites: Media.net, Ezoic. Crypto ad networks (Coinzilla, A-ADS, Bitmedia) pay more per
   view but mostly advertise exchanges and trading. Don't show those to readers in Nepal.
3. **Direct sponsors.** Sell the sidebar "Sponsor" spot by the month to legal Nepali finance businesses:
   brokers listed with SEBON, banks, insurance companies, eSewa/Khalti merchants, fintech startups, accounting
   firms, education consultancies. Even NPR 5,000 to 20,000 a month per sponsor beats ads at small traffic.
4. **Newsletter.** Add a free weekly email ("This week in Nepal finance and digital currency") with Beehiiv or
   Substack. Newsletters with 1,000+ engaged readers can sell sponsored slots.
5. **Affiliate links.** Pick things that are legal and useful for your readers: finance and investing books,
   online courses, VPN or web hosting, tax or accounting software. Exchange and trading affiliates only make sense for readers outside Nepal.
6. **Paid listings on nepaltrade.crypto.** Later, the second domain can become a paid business directory
   that this site promotes.

### How to get readers
- **Write one or two original posts a week.** Short explainers such as "What NRB's new policy means for
  savers", "What is a CBDC?" or "NEPSE this week". They bring Google traffic and make AdSense approval more likely.
  Claude can add a simple blog section when you want it.
- **Share automatically.** Connect the site's RSS feed (`/feed.xml`) to a Telegram channel, a Facebook page and
  X with a free tool such as IFTTT or Zapier.
- **Submit to Google Search Console** once the `.com` is live, so Google finds the pages.
- **Write in Nepali too.** There are few Nepali-language finance news sites, which is an opening.

### Stay on the right side of the law
Nepal Rastra Bank has declared crypto trading and mining illegal in Nepal, and Nepal's telecom regulator has
ordered crypto websites blocked in the past. The site is set up as news and education with a disclaimer on every
page. Keep it that way: no "buy now" buttons, no price predictions, no exchange referrals aimed at Nepal. Ask a
Nepali lawyer before you accept crypto payments from Nepal-based sponsors.

## Part 4. Nepali version (automatic translation)

Every page now has a Nepali twin: `index.ne.html`, `visa.ne.html` and so on. The **English / नेपाली** button in
the top bar switches between them. Headlines and summaries are translated by the Claude API during each hourly build.
Each story is translated only once and saved in `items.json`, so later builds only send new stories.

**Turn it on (5 minutes):**

1. Create an API key at https://platform.claude.com (Settings > API keys) and add a little credit.
2. In GitHub, open the repo > **Settings > Secrets and variables > Actions > New repository secret**.
3. Name: `ANTHROPIC_API_KEY`. Value: the key. Save.
4. Open **Actions > Build and publish > Run workflow**. The log shows lines starting with `Translation:`.

Without the secret the site still builds; Nepali pages show the English headline until a translation exists.

**Cost control** is in `config.json` under `translation`:

- `model`: which Claude model translates. It is set to `claude-haiku-5-5` (low cost). Change it to `claude-opus-5-5` for the most natural Nepali, at a much higher cost.
- `max_per_build`: the most stories sent in one hourly run (default 40).
- `enabled`: set to `false` to stop translating.

Nepali page text that is not a headline (menus, guides, the agent check tool) is written by hand in
`scripts/build.py` and `scripts/visa_content.py`. Please have a native speaker read it once before you promote the site.

## Part 5. Australia visa section

Pages: `visa.html` (hourly visa news), `check-agent.html` (check your migration agent), `visa-changes-2026.html`
(what changed, with sources) and `visa-scams.html` (warning signs and where to report). Each has a Nepali twin.

- **News sources** are in `config.json` under `visa.feeds`. A story is kept only if it mentions a visa word and Australia.
- **Rule changes** are in `scripts/visa_content.py`. Check them against the official Home Affairs page at least
  once a month and update the "Last checked" date in `render_changes` in `scripts/build.py`.

**Ways it earns money**

- Google AdSense (same account as the rest of the site; set `visa.adsense_slot_top` for the visa page).
- **Featured registered agents** (`visa.featured_agents`): sell a monthly listing to registered agents and lawyers.
  Before adding one, look up their MARN on the official register yourself. Never list someone who is not registered.
- A visa-page sponsor (`visa.sponsor`), for example a college, a remittance company or a tax agent.
- Referral fees from registered agents are allowed, but the agent must tell their client about the fee
  (Code of Conduct). Ask them to put that in writing.

**Legal line, important.** In Australia only a registered migration agent or an Australian lawyer may give
immigration assistance, that is, advise someone on their own visa or help prepare their application. Doing it without
registration is an offence under the Migration Act, whether or not you charge (with narrow exceptions such as close family).
So this section must stay general: explain news and official rules, link to official sources, and send people to
registered agents. Do not answer "what should I do about my visa?" questions in comments, messages or Facebook.
Do not name or accuse a specific agent unless you are quoting an official decision or court result (defamation risk).

## Part 6. Getting paid directly (Support button)

The site has a red **Support** button in the header and a "Support News Nepal" box in the sidebar. Both link to
`support.html` (and `support.ne.html` in Nepali). They stay hidden until you add at least one payment method in
`config.json` under `monetization` → `support` and `donations`.

### Card payments in AUD (Stripe Payment Link), about 15 minutes
1. Sign up at stripe.com as an Australian business (ABN or sole trader details, and your bank account for payouts).
2. In the Stripe Dashboard go to **Payment Links → New**. Choose a product such as "Support News Nepal", set the
   price type to **Customers choose what to pay** (currency AUD, suggested amount A$5) and create the link.
3. Copy the link (it starts with `https://buy.stripe.com/`) into `"stripe_payment_link"`.
Fees: about 1.7% + A$0.30 per domestic card payment. Readers can pay with card, Apple Pay or Google Pay.

### Payments from Nepal (eSewa, Khalti or Fonepay QR)
1. In your eSewa or Khalti app (or your Nepali bank's mobile app, for a Fonepay QR) open **My QR / Receive money**
   and save the QR image.
2. Put the image in the `static` folder, for example `static/support-qr.png`.
3. Set `"nepal_qr_image": "support-qr.png"` and your account name in `"nepal_account_name"`.
A personal wallet QR is fine for small tips. For regular income, ask your bank for a **merchant** Fonepay QR.

### Crypto tips (from outside Nepal only)
Fill in the wallet addresses under `donations` → `addresses`. These only show on the full support page, with a
note that they are for readers outside Nepal, because crypto transactions are illegal in Nepal.

Optional: add `"message_ne"`, `"stripe_button_text_ne"` or `"nepal_qr_label_ne"` to show your own Nepali wording.

## Part 7. Images, logo and live prices
- **Story images** come from each publisher's feed (media:content, enclosure or the first picture in the story).
  If the feed has none, the build reads the article's own preview picture (og:image), up to 30 new articles
  per hourly build (`images.og_lookups_per_build`). Each picture is credited "Image: <publisher>" and links to
  the original article. Google News stories have no image, so they show a branded News Nepal picture.
  If a publisher asks you to stop showing its pictures, set `"enabled": false` on its feed.
- **Logo**: `static/logo.svg` (full) and `static/logo-mark.svg` (square icon, also the favicon). They are original
  vector files you can reuse for social media profiles.
- **Price strip**: exchange rates come from Nepal Rastra Bank's free daily API at build time; BTC, ETH and USDT
  prices load live from CoinGecko's free API in the reader's browser. Change the lists under `ticker`, or empty
  them to hide the strip. Prices are shown as market news only.
