import { useRouter } from 'next/router';
import { r2rClient } from 'r2r-js';
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from 'react';

import { AuthenticationError } from '@/lib/CustomErrors';
import { AuthState, Pipeline, UserContextProps } from '@/types';

const UserContext = createContext<UserContextProps>({
  pipeline: null,
  setPipeline: () => {},
  selectedModel: 'null',
  setSelectedModel: () => {},
  isAuthenticated: false,
  login: async () => {},
  logout: async () => {},
  authState: {
    isAuthenticated: false,
    email: null,
    password: null,
    userRole: null,
  },
  getClient: () => null,
  client: null,
  viewMode: 'admin',
  setViewMode: () => {},
});

export const useUserContext = () => useContext(UserContext);

export const UserProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);
  const [client, setClient] = useState<r2rClient | null>(null);
  const [viewMode, setViewMode] = useState<'admin' | 'user'>('admin');

  const [pipeline, setPipeline] = useState<Pipeline | null>(() => {
    if (typeof window !== 'undefined') {
      const storedPipeline = localStorage.getItem('pipeline');
      return storedPipeline ? JSON.parse(storedPipeline) : null;
    }
    return null;
  });

  const [selectedModel, setSelectedModel] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('selectedModel') || 'gpt-4o';
    }
    return 'null';
  });

  const [authState, setAuthState] = useState<AuthState>(() => {
    if (typeof window !== 'undefined') {
      const storedAuthState = localStorage.getItem('authState');
      if (storedAuthState) {
        return JSON.parse(storedAuthState);
      }
    }
    return {
      isAuthenticated: false,
      email: null,
      password: null,
      userRole: null,
    };
  });

  const [lastLoginTime, setLastLoginTime] = useState<number | null>(null);

  const login = async (
    email: string,
    password: string,
    instanceUrl: string
  ) => {
    const newClient = new r2rClient(instanceUrl);
    try {
      await newClient.login(email, password);

      let userRole: 'admin' | 'user' = 'user';
      try {
        await newClient.appSettings();
        userRole = 'admin';
      } catch (error) {
        if (
          !(error instanceof Error && 'status' in error && error.status === 403)
        ) {
          console.error('Unexpected error when checking user role:', error);
        }
      }

      const newAuthState: AuthState = {
        isAuthenticated: true,
        email,
        password,
        userRole,
      };
      setAuthState(newAuthState);
      setLastLoginTime(Date.now());
      localStorage.setItem('authState', JSON.stringify(newAuthState));

      const newPipeline = { deploymentUrl: instanceUrl };
      setPipeline(newPipeline);
      localStorage.setItem('pipeline', JSON.stringify(newPipeline));

      setClient(newClient);
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const logout = useCallback(async () => {
    if (client && authState.isAuthenticated) {
      try {
        await client.logout();
      } catch (error) {
        console.error(`Logout failed:`, error);
      }
    }
    setAuthState({
      isAuthenticated: false,
      email: null,
      password: null,
      userRole: null,
    });
    localStorage.removeItem('pipeline');
    setPipeline(null);
    setClient(null);
    localStorage.removeItem('authState');
  }, [client, authState]);

  const refreshTokenPeriodically = useCallback(async () => {
    if (authState.isAuthenticated && client) {
      if (lastLoginTime && Date.now() - lastLoginTime < 5 * 60 * 1000) {
        return;
      }
      try {
        await client.refreshAccessToken();
        setLastLoginTime(Date.now());
      } catch (error) {
        console.error('Failed to refresh token:', error);
        if (error instanceof AuthenticationError) {
          try {
            await login(
              authState.email!,
              authState.password!,
              pipeline!.deploymentUrl
            );
          } catch (loginError) {
            console.error('Failed to re-authenticate:', loginError);
            await logout();
          }
        } else {
          await logout();
        }
      }
    }
  }, [authState, client, login, logout, lastLoginTime, pipeline]);

  const getClient = useCallback((): r2rClient | null => {
    return client;
  }, [client]);

  useEffect(() => {
    if (authState.isAuthenticated && pipeline && !client) {
      const newClient = new r2rClient(pipeline.deploymentUrl);
      setClient(newClient);
    }
  }, [authState.isAuthenticated, pipeline, client]);

  useEffect(() => {
    const handleRouteChange = () => {
      if (authState.isAuthenticated && !client && pipeline) {
        const newClient = new r2rClient(pipeline.deploymentUrl);
        setClient(newClient);
      }
    };

    router.events.on('routeChangeComplete', handleRouteChange);

    setIsReady(true);

    return () => {
      router.events.off('routeChangeComplete', handleRouteChange);
    };
  }, [router, authState.isAuthenticated, client, pipeline]);

  useEffect(() => {
    let refreshInterval: NodeJS.Timeout;

    if (authState.isAuthenticated) {
      const initialDelay = setTimeout(
        () => {
          refreshTokenPeriodically();
          refreshInterval = setInterval(
            refreshTokenPeriodically,
            55 * 60 * 1000
          );
        },
        5 * 60 * 1000
      );

      return () => {
        clearTimeout(initialDelay);
        if (refreshInterval) {
          clearInterval(refreshInterval);
        }
      };
    }
  }, [authState.isAuthenticated, refreshTokenPeriodically]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('selectedModel', selectedModel);
    }
  }, [selectedModel]);

  if (!isReady) {
    return null; // or a loading spinner
  }

  return (
    <UserContext.Provider
      value={{
        pipeline,
        setPipeline,
        selectedModel,
        setSelectedModel,
        isAuthenticated: authState.isAuthenticated,
        authState,
        login,
        logout,
        getClient,
        client,
        viewMode,
        setViewMode,
      }}
    >
      {children}
    </UserContext.Provider>
  );
};
