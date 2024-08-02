export const getSearchUrl = (query: string) => {
  const prefix = '';
  return `${prefix}?q=${encodeURIComponent(query)}`;
};
