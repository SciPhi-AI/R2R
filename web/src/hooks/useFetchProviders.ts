import { useEffect, useState } from 'react';
import { Provider } from '@/types';

export const useFetchProviders = () => {
  const [allProviders, setProviders] = useState<Provider[]>([]);

  useEffect(() => {
const [error, setError] = useState(null);

// In the fetch request
.catch((error) => {
  console.error('Error fetching providers:', error);
  setError(error);
});

// Return the error state
return { allProviders, error };
      .then((res) => res.json())
      .then(setProviders)
      .catch((error) => console.error('Error fetching providers:', error));
  }, []);

  return { allProviders };
};
