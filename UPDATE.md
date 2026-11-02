# Update log

## 2026-11-02 — Shared book banner

- Connected all public page types to `https://nanalab.kr/src_cdn/banner/astra.js`. Campaign, design, translated controls and the supplied YES24 book destination are maintained centrally in src_cdn.
- Shared archive assets load the banner on detail/list pages; other HTML and source templates include the stable deferred loader. HTML-only generator adapters retain the connection after rebuilds and pass non-HTML values through unchanged.
- The component is closable for the tab session, clears detected bottom navigation, and hides for modals/fullscreen/mobile input. The Astra practice site remains excluded. No additional analytics or ad-network requests are introduced by the component.
- Existing content, routes and publisher integrations are preserved. Direct HTML changes restore exactly to the baseline when the marked loader is removed. Workspace validation/deployment evidence: `.tools/shared-book-banner-20261102/`.
