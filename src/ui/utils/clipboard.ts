/**
 * Clipboard utility functions.
 */

/**
 * Copy text to clipboard with fallback for older browsers.
 */
export async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    console.error('Failed to copy text: ', err);
    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
    } catch (fallbackErr) {
      console.error('Fallback copy failed: ', fallbackErr);
    }
    document.body.removeChild(textArea);
  }
}
