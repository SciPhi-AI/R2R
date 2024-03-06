import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { createClient } from '@/utils/supabase/component';

// Define the shape of the context
interface AuthContextType {
  isLogged: boolean;
  cloudMode: 'cloud' | 'local';
}

const defaultAuthContext: AuthContextType = {
  isLogged: false,
  cloudMode: 'local',
};

const AuthContext = createContext<AuthContextType>(defaultAuthContext);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [isLogged, setIsLogged] = useState(false);
  const [cloudMode, setCloudMode] = useState<'cloud' | 'local'>('local');

  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    const fetchMode = () => {
      const mode =
        process.env.NEXT_PUBLIC_CLOUD_MODE === 'true' ? 'cloud' : 'local';
      setCloudMode(mode);
    };

    fetchMode();
  }, []);

  useEffect(() => {
    const authenticate = async () => {
      const { pathname } = router;
      // List of paths that don't require authentication
      const authBypassPaths = [
        '/error',
        '/forgot_password',
        '/update_password',
        '/login',
      ];

      // Check if the current path is in the list of auth bypass paths
      if (authBypassPaths.includes(pathname)) {
        console.log('Bypassing auth check for:', pathname);
        return; // Bypass the authentication check
      }

      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) {
        console.log('User is not logged in. Redirecting to /login');
        router.push('/login');
        return;
      }
      setIsLogged(true);
      console.log('User is logged in.'); // Log after setting state
    };

    authenticate();
  }, [router]);

  // Use useEffect to listen for changes to isLogged
  useEffect(() => {
    console.log(`isLogged state changed: ${isLogged}`);
  }, [isLogged]);

  return (
    <AuthContext.Provider value={{ isLogged, cloudMode }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
