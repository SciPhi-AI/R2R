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
      if (process.env.NEXT_PUBLIC_CLOUD_MODE === 'true') {
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) {
          router.push('/login');
          return;
        }
        setIsLogged(true);
      } else {
        setIsLogged(true);
      }
    };

    authenticate();
  }, [router]);

  return (
    <AuthContext.Provider value={{ isLogged }}>{children}</AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
