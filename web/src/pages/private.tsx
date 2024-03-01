import type { User } from '@supabase/supabase-js';
import type { GetServerSidePropsContext } from 'next';

import { createClient } from '@/utils/supabase/server-props';

export default function PrivatePage({ user }: { user: User }) {
  return <h1>Hello, {user.email || 'user'}!</h1>;
}

export async function getServerSideProps(context: GetServerSidePropsContext) {
  const supabase = createClient(context);

  const { data, error } = await supabase.auth.getUser();

  if (error || !data) {
    return {
      redirect: {
        destination: '/',
        permanent: false,
      },
    };
  }

  return {
    props: {
      user: data.user,
    },
  };
}
