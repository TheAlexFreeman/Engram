// Thanks to https://stackoverflow.com/a/6234804.
export function escapeHtml(unsafeString: string): string {
  return unsafeString
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
