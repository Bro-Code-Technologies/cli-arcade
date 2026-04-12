// Regexes
const HTML_TAG_REGEX = /<[^>]*>/g;

// Sanitize a string: strip HTML tags and trim whitespace
export function sanitize(value: string): string {
  return value.replace(HTML_TAG_REGEX, '').trim();
}
