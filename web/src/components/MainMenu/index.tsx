import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Image from 'next/image';
import styles from './styles.module.scss';
import { WorkspacesSelect } from '../WorkspacesSelect';
import { createClient } from '@/utils/supabase/component';
import {
  Bug,
  Cloud,
  CreditCard,
  Github,
  Keyboard,
  LifeBuoy,
  LogOut,
  Mail,
  MessageSquare,
  Plus,
  PlusCircle,
  Settings,
  User,
  UserPlus,
  Users,
} from 'lucide-react';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export function MainMenu() {
  const supabase = createClient();
  const [user, setUser] = useState(null);
  const router = useRouter();

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user);
    });
  }, []);

  const handleLogout = async () => {
    const { error } = await supabase.auth.signOut();
    if (!error) {
      // Redirect to the login page or home page after logout
      router.push('/login');
    } else {
      // Handle error case
      console.error('Logout failed: ', error);
    }
  };

  return (
    <div className={styles.container}>
      <WorkspacesSelect />

      <div className={styles.leftMainMenuNavigation}>
        <a
          style={{ cursor: 'pointer' }}
          href="https://docs.sciphi.ai"
          target="_blank"
          rel="noopener noreferrer"
        >
          <button>Docs</button>
        </a>

        <div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Image
                src="/images/dummy_logo.png"
                alt="Acme Co."
                width="28"
                height="28"
                className={styles.userIcon}
              />

              {/* <Button variant="outline">Open</Button> */}
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56">
              <DropdownMenuLabel>
                {user === null ? 'My Account' : user.email}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem className={styles.handCursor}>
                  <User className="mr-2 h-4 w-4" />
                  <span>Profile</span>
                  <DropdownMenuShortcut>⇧⌘P</DropdownMenuShortcut>
                </DropdownMenuItem>
                <DropdownMenuItem className={styles.handCursor} disabled={true}>
                  <CreditCard className="mr-2 h-4 w-4" />
                  <span>Billing</span>
                  <DropdownMenuShortcut>⌘B</DropdownMenuShortcut>
                </DropdownMenuItem>
                <DropdownMenuItem className={styles.handCursor}>
                  <Settings className="mr-2 h-4 w-4" />
                  <span>Settings</span>
                  <DropdownMenuShortcut>⌘S</DropdownMenuShortcut>
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuItem className={styles.handCursor}>
                <Bug className="mr-2 h-4 w-4" />
                <span>Report a bug</span>
              </DropdownMenuItem>
              <DropdownMenuItem className={styles.handCursor}>
                <LifeBuoy className="mr-2 h-4 w-4" />
                <span>Support</span>
              </DropdownMenuItem>
              <DropdownMenuItem disabled>
                <Cloud className="mr-2 h-4 w-4" />
                <span>API</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleLogout}
                className={styles.handCursor}
              >
                <LogOut className="mr-2 h-4 w-4" />
                <span>Log out</span>
                <DropdownMenuShortcut>⇧⌘Q</DropdownMenuShortcut>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
}
