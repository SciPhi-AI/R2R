import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { User } from '@supabase/supabase-js';
import { createClient } from '@/utils/supabase/component';

export default function UpdatePasswordPage({ user }: { user: User }) {
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const router = useRouter();
  const supabase = createClient();
  const token_hash = router.query.token_hash;
  const email = router.query.email as string;

  useEffect(() => {
    const validateToken = async () => {
      console.log('Token hash:', token_hash);
      console.log('Email:', email);
      // if (!token_hash || !email) {
      //   router.push('/login'); // Redirect if no token hash is found
      //   return;
      // }
    };

    validateToken();
  }, [router]);

  const updatePassword = async () => {
    if (password !== passwordConfirm) {
      alert('Passwords do not match!');
      return;
    }

    try {
      const { data: updateData, error: updateError } =
        await supabase.auth.updateUser({ password });

      if (updateError) {
        console.error('Error updating password:', updateError.message);
        throw new Error('Failed to update password');
      }

      console.log('Password updated successfully');

      const { data: signInData, error: signInError } =
        await supabase.auth.signInWithPassword({
          email,
          password,
        });

      if (signInError) {
        console.error(
          'Error signing in after password update:',
          signInError.message
        );
        throw new Error('Failed to sign in after password update');
      }

      console.log('Signed in successfully after password update');

      router.push('/');
    } catch (error) {
      console.error('Error:', error.message);
      alert(`An error occurred: ${error.message}`);
    }
  };

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault(); // Prevent default form submission
        await updatePassword();
      }}
    >
      {/* Your form fields for password and password confirmation */}
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="New Password"
        required
      />
      <input
        type="password"
        value={passwordConfirm}
        onChange={(e) => setPasswordConfirm(e.target.value)}
        placeholder="Confirm New Password"
        required
      />
      {/* Submit button */}
      <button type="submit">Update Password</button>
    </form>
  );
}
