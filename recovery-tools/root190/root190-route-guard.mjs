import fs from 'node:fs/promises';
export async function isPartialRoot(marker) {
  try { await fs.access(marker); return true; }
  catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}
export async function blockLegacyMutation(marker, action) {
  if (await isPartialRoot(marker)) throw new Error(`JP190 partial routing is active. ${action} is disabled before writes. Use a reviewed route-aware workflow; redirect files are not local legislation.`);
}
