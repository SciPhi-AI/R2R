import { useState } from 'react';

import { createClient } from '@/utils/supabase/component';

export default function ForgotPassword() {
  const supabase = createClient();
  const [passwordResetState, setPasswordResetState] = useState({
    email: '',
    requestStatus: 'idle',
    errorMessage: '',
    emailRequested: '',
  });

  async function resetPassword(email: string) {
    if (passwordResetState.emailRequested === email) {
      setPasswordResetState({
        ...passwordResetState,
        requestStatus: 'error',
        errorMessage: 'A reset request has already been sent for this email.',
      });
      return;
    }

    setPasswordResetState({
      ...passwordResetState,
      requestStatus: 'processing',
    });

    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/update-password`,
    });

    if (error) {
      console.error(error);
      setPasswordResetState({
        ...passwordResetState,
        requestStatus: 'error',
        errorMessage: 'Email not found.',
      });
    } else {
      setPasswordResetState({
        ...passwordResetState,
        emailRequested: email,
        requestStatus: 'success',
      });
    }
  }

  return (
    <>
      <div className="flex min-h-full flex-1 flex-col justify-center px-6 py-12 lg:px-8">
        <div className="sm:mx-auto sm:w-full sm:max-w-sm">
          <img
            className="mx-auto h-10 w-auto"
            src="images/sciphi.png"
            alt="Sciphi.AI logo"
          />
          <h2 className="mt-10 text-center text-2xl font-bold leading-9 tracking-tight text-white">
            Forgot your password?
          </h2>
        </div>

        <div className="mt-10 sm:mx-auto sm:w-full sm:max-w-sm">
          <form className="space-y-6" action="#" method="POST">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium leading-6 text-white"
              >
                Email address
              </label>
              <div className="mt-2">
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  className="block w-full rounded-md border-0 bg-white/5 py-1.5 text-white shadow-sm ring-1 ring-inset ring-white/10 focus:ring-2 focus:ring-inset focus:ring-indigo-500 sm:text-sm sm:leading-6"
                  value={passwordResetState.email}
                  onChange={(e) =>
                    setPasswordResetState({
                      ...passwordResetState,
                      email: e.target.value,
                    })
                  }
                />
              </div>
            </div>

            <div className="mt-10 sm:mx-auto sm:w-full sm:max-w-sm">
              <div className="flex space-x-4">
                {passwordResetState.requestStatus === 'success' ? (
                  <div className="flex w-full justify-center items-center rounded-md bg-white px-3 py-1.5 text-sm font-semibold leading-6 text-green-600">
                    ✅ Check your inbox
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => resetPassword(passwordResetState.email)}
                    disabled={
                      passwordResetState.requestStatus === 'processing' ||
                      passwordResetState.email ===
                        passwordResetState.emailRequested
                    }
                    className={`flex w-full justify-center rounded-md px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm ${passwordResetState.requestStatus === 'processing' || passwordResetState.email === passwordResetState.emailRequested ? 'bg-gray-500' : 'bg-indigo-500 hover:bg-indigo-400'} focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500`}
                  >
                    {passwordResetState.requestStatus === 'processing'
                      ? 'Sending...'
                      : 'Reset Password'}
                  </button>
                )}
              </div>
              {passwordResetState.requestStatus === 'error' && (
                <div className="mt-3 text-center text-sm text-red-500">
                  {passwordResetState.errorMessage}
                </div>
              )}
            </div>
          </form>
        </div>
      </div>
    </>
  );
}
