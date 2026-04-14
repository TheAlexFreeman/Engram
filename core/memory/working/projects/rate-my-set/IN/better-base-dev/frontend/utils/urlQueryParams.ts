// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getQueryParamsString(params: Record<string, any>) {
  return Object.entries(params)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value.toString())}`)
    .join('&');
}
