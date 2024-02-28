import { useState, useContext } from 'react';

import { Provider } from '@/types';
import { useProviderDataContext } from '@/context/providerContext';

export const useModal = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { getAllProviders, getFilteredProviders, getSelectedProvider } =
    useProviderDataContext();

  const [secretProvider, setSecretProvider] = useState<Provider | null>(null);

  const toggleModal = () => setIsOpen(!isOpen);

  const handleSecretProvider = (provider: Provider | null) => {
    setSecretProvider(provider);
    console.log('Secret Provider:', provider);
    toggleModal();
    console.log('Toggling SecretModal:', isOpen);
  };

  return {
    isOpen,
    toggleModal,
    secretProvider,
    setSecretProvider,
    handleSecretProvider,
  };
};
