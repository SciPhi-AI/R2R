import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Image from 'next/image';
import { createClient } from '@/utils/supabase/component';
import {
  Bug,
  Cloud,
  CreditCard,
  LifeBuoy,
  LogOut,
  Settings,
  User,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/Button';

export function ProfileMenu({ user }) {
  const supabase = createClient();
  const router = useRouter();

  const handleLogout = async () => {
    const { error } = await supabase.auth.signOut();
    if (!error) {
      router.push('/login');
    } else {
      console.error('Logout failed: ', error);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {user &&
        user?.user_metadata?.avatar_url?.includes('googleusercontent.com') ? (
          <Image
            src={user?.user_metadata?.avatar_url}
            alt={`${user.username ? user.username : 'user'} Profile`}
            width="25"
            height="25"
            className="rounded-full bg-[var(--color-7)] p-[1px] text-[var(--color-1)]"
          />
        ) : (
          <div
            style={{
              width: '25px',
              height: '25px',
              borderRadius: '9999px', // Makes the div fully rounded
              background:
                'linear-gradient(90deg, #1f005c, #5b0060, #870160, #ac255e, #ca485c, #e16b5c, #f39060, #ffb56b)',
            }}
            aria-label="Default Profile Background"
          ></div>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="w-56"
        style={{ backgroundColor: 'inherit' }}
      >
        <DropdownMenuLabel>
          {user ? user.email : 'My Account'}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem className="cursor-pointer" disabled={true}>
            <User className="mr-2 h-4 w-4" />
            <span>Profile</span>
            <DropdownMenuShortcut>⇧⌘P</DropdownMenuShortcut>
          </DropdownMenuItem>
          <DropdownMenuItem className="cursor-pointer" disabled={true}>
            <CreditCard className="mr-2 h-4 w-4" />
            <span>Billing</span>
            <DropdownMenuShortcut>⌘B</DropdownMenuShortcut>
          </DropdownMenuItem>
          <DropdownMenuItem className="cursor-pointer" disabled={true}>
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
            <DropdownMenuShortcut>⌘S</DropdownMenuShortcut>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="cursor-pointer">
          <Bug className="mr-2 h-4 w-4" />
          <Button href="https://form.typeform.com/to/ZDkIZ2j0" variant="text">
            Report a bug{' '}
          </Button>
        </DropdownMenuItem>
        <DropdownMenuItem className="cursor-pointer">
          <LifeBuoy className="mr-2 h-4 w-4" />
          <Button href="https://discord.gg/p6KqD2kjtB" variant="text">
            Support
          </Button>
        </DropdownMenuItem>
        <DropdownMenuItem disabled>
          <Cloud className="mr-2 h-4 w-4" />
          <span>API</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
          <LogOut className="mr-2 h-4 w-4" />
          <span>Log out</span>
          <DropdownMenuShortcut>⇧⌘Q</DropdownMenuShortcut>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
