import React, { createContext, useContext, ReactNode } from 'react';
import { Provider } from '@/types';
import { useFetchProviders } from '@/hooks/useFetchProviders';

interface ProviderDataContextType {
  getAllProviders: () => Provider[];
  getFilteredProviders: (providerType: string) => Provider[];
  getSelectedProvider: (providerType: string) => Provider | null;
}

const ProviderDataContext = createContext<ProviderDataContextType | undefined>(
  undefined
);

export const ProviderContextProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const { providers } = useFetchProviders();
  const [selectedProvider, setSelectedProvider] =
    React.useState<Provider | null>(null);

  const getAllProviders = () => {
    return providers;
  };

  const getFilteredProviders = (providerType: string) => {
    return providers.filter((provider) => provider.type === providerType);
  };

  const getSelectedProvider = (providerName: string) => {
    return providers.find((provider) => provider.name === providerName) || null;
  };

  return (
    <ProviderDataContext.Provider
      value={{
        getAllProviders,
        getFilteredProviders,
        getSelectedProvider,
      }}
    >
      {children}
    </ProviderDataContext.Provider>
  );
};

// Custom hook to use the provider data context
export const useProviderDataContext = () => {
  const context = useContext(ProviderDataContext);
  if (context === undefined) {
    throw new Error(
      'useProviderDataContext must be used within a ProviderDataProvider'
    );
  }
  return context;
};
