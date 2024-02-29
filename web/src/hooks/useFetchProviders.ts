import { useEffect, useState } from 'react';
import { Provider } from '@/types';

export const useFetchProviders = () => {
  const [allProviders, setProviders] = useState<Provider[]>([]);

  useEffect(() => {
    fetch(`/api/integrations`)
      .then((res) => res.json())
      .then(setProviders)
      .catch((error) => console.error('Error fetching providers:', error));
  }, []);

  return { allProviders };
};
