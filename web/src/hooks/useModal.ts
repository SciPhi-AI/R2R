import { useState } from 'react';

import { Provider } from '@/types';

export const useModal = () => {
  const [isOpen, setIsOpen] = useState(false);

  const [secretProvider, setSecretProvider] = useState<Provider | null>(null);

  const toggleModal = () => setIsOpen(!isOpen);

  const handleSecretProvider = (provider: Provider | null) => {
    setSecretProvider(provider);
    toggleModal();
  };

  return {
    isOpen,
    toggleModal,
    secretProvider,
    setSecretProvider,
    handleSecretProvider,
  };
};
