# Update log

## 2026-11-02 — Shared book banner

- Connected all public page types to `https://nanalab.kr/src_cdn/banner/astra.js`. Campaign, design, translated controls and the supplied YES24 book destination are maintained centrally in src_cdn.
- Shared archive assets load the banner on detail/list pages; other HTML and source templates include the stable deferred loader. HTML-only generator adapters retain the connection after rebuilds and pass non-HTML values through unchanged.
- The component is closable for the tab session, clears detected bottom navigation, and hides for modals/fullscreen/mobile input. The Astra practice site remains excluded. No additional analytics or ad-network requests are introduced by the component.
- Existing content, routes and publisher integrations are preserved. Direct HTML changes restore exactly to the baseline when the marked loader is removed. Workspace validation/deployment evidence: `.tools/shared-book-banner-20261102/`.

## 2026-11-14 — Connect 20 verified Japanese law additions

- Connected 20 newly represented official Act snapshots only after JP02 commit e0138dfdb9322aa3c700b2e2ca650e7bf96a3c68 was built and all 231 selected public files matched the exact committed bytes (known Cloudflare injection normalization only).
- Japanese coverage: 794 distinct law IDs / 804 edition pages. Per-document dated metadata remains; older observations were not relabelled as freshly rechecked. No national completeness, legal-force or search-indexing guarantee.
- Preserved all existing root/JP01 law HTML, existing routes, four-language template, tags and the root canonical sitemap. JP02 leaf sitemap expands to 218 URLs through its existing main-index reference. New documents preserve exact source revision IDs, amendment effective dates, rights and omissions.
- Existing 194 JP02 provenance records retain a separate immutable hash assertion alongside the newly reviewed full-registry hash.
