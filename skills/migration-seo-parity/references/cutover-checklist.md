# Website migration cutover checklist

A platform-neutral pre-launch checklist for moving a website to a new platform
without losing search rankings or traffic. Distilled from a real production
WordPress → static-site migration. Use it as a guide; not every item applies to
every site.

The golden rule: **at launch, every old URL must lead to the right new URL, and
every page Google already ranks must stay indexable with a correct canonical.**

---

## Before cutover (the week before)

**URLs & redirects**
- [ ] Make a list of every URL Google currently knows (from the old sitemap and
      Google Search Console). This is the master list.
- [ ] Every old URL has a destination on the new site — either the same content at
      the same path, or a **301 redirect** to its new location.
- [ ] No old URL 301-redirects to a page that then 404s or redirects again
      (no redirect chains, no dead ends).
- [ ] Decide ONE trailing-slash convention (`/page` or `/page/`) and apply it
      everywhere — canonicals, sitemap, internal links, redirects. Match what
      Google already indexed where possible.

**Indexability & canonicals**
- [ ] No important page accidentally carries "noindex" (staging sites often
      default to noindex — make sure it's removed in production).
- [ ] Every indexable page has a canonical tag pointing at **itself** on the new
      site (not the old domain, not a different page).
- [ ] Pages that *should* stay hidden (thank-you pages, login, ad landing
      variants) keep their "noindex" — match the old site's behavior.

**Sitemap & robots**
- [ ] New `sitemap.xml` exists, lists only real indexable pages, uses the chosen
      trailing-slash form, and excludes noindexed/duplicate URLs.
- [ ] Old sitemap URLs (e.g. `sitemap_index.xml`) redirect to the new sitemap.
- [ ] `robots.txt` doesn't block anything important (a leftover staging
      `Disallow: /` will deindex the whole site).

**Content & media**
- [ ] Spot-check the highest-traffic pages: content, images, and any
      forms/buttons/CTAs are present and working on the new site.
- [ ] Images are served from the new site (not still hot-linking the old one),
      so the old site can eventually be turned off.
- [ ] Structured data / schema (if used) carries over for articles and the
      organization.

**Infrastructure**
- [ ] The new site has a valid SSL certificate for the real domain **before** the
      DNS/origin flip.
- [ ] Lower DNS TTL a day ahead if you control DNS directly (faster rollback).
- [ ] Know your rollback path: keep the old site running and reachable so you can
      point traffic back instantly if something's wrong.

---

## Cutover day

- [ ] Flip traffic to the new site (DNS or origin change).
- [ ] Keep the old site warm and reachable — do not delete anything yet.
- [ ] Purge any CDN/edge cache so visitors get the new site immediately.
- [ ] Re-submit the new `sitemap.xml` in Google Search Console.
- [ ] Smoke-test live: homepage, top traffic pages, a few redirects from your map,
      the 404 page (it should return a real 404 status), and any forms.

---

## After cutover (first two weeks)

- [ ] Watch server/CDN 404 logs daily; add any missed old URLs to the redirect map.
- [ ] In Search Console, watch index coverage, sitemap processing, and canonical
      changes for surprises.
- [ ] Confirm analytics, tag manager, and conversion tracking still fire on the
      new site.
- [ ] Keep the old site available for at least 30 days before decommissioning.

---

## The signals that, if broken, cost the most rankings

1. Old URLs returning 404 instead of 301-redirecting → lost pages + lost backlinks.
2. A stray "noindex" in production → pages vanish from Google.
3. Canonicals pointing at the old domain → Google keeps the old URLs, ignores new.
4. Inconsistent trailing slashes → every URL looks "moved," diluting authority.

The single-URL probe in this skill checks all four for one page. Doing it for an
entire site automatically — and generating the complete redirect map — is the
automated migration service.
