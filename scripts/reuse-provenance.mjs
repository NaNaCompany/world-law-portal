// Shared public provenance markup. Never contains or changes statutory source text.
import assert from 'node:assert/strict';
export const escapeHtml = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
export function renderReuseSection(d) {
 assert(Array.isArray(d.reuseConditions) && d.reuseConditions.length);
 const urls = [...new Set([...(d.rightsEvidenceUrls || []), ...d.reuseConditions.flatMap(t => t.match(/https?:\/\/[^\s<>]+/g) || [])])].filter(url => !/\.pdf(?:[?#]|$)/i.test(url));
 const links = urls.map(url => { assert(/^https?:$/.test(new URL(url).protocol)); return `<li><a href="${escapeHtml(url)}" rel="noopener">${escapeHtml(url)}</a></li>`; }).join('');
 return `<section class="reuse-conditions"><h2>Reuse conditions</h2>${d.siteTermsReview ? `<p class="site-terms-review">${escapeHtml(d.siteTermsReview)}</p>` : ''}<ul>${d.reuseConditions.map(t => `<li>${escapeHtml(t)}</li>`).join('')}</ul>${links ? `<p>Reuse references:</p><ul>${links}</ul>` : ''}</section>`;
}
