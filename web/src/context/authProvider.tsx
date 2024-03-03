import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { createClient } from '@/utils/supabase/component';

// Define the shape of the context
interface AuthContextType {
  isLogged: boolean;
}

const defaultAuthContext: AuthContextType = {
  isLogged: false,
};

const AuthContext = createContext<AuthContextType>(defaultAuthContext);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [isLogged, setIsLogged] = useState(false);
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    const authenticate = async () => {
      const { pathname } = router;
      // List of paths that don't require authentication
      const authBypassPaths = [
        '/error', // Assuming this is the path for error.tsx
        '/forgot_password',
        '/public', // Assuming public.tsx doesn't require authentication
        '/update_password',
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
    <AuthContext.Provider value={{ isLogged }}>{children}</AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
