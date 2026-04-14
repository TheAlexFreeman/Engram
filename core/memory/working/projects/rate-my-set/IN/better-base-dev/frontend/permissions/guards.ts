import { redirect } from '@tanstack/react-router';

import { userAtom } from '@/state/auth';
import store from '@/state/store';

export function authGuard() {
  const user = store.get(userAtom);

  if (!user.isAuthenticated) {
    throw redirect({ to: '/auth/login' });
  }
}

export function verifiedGuard() {
  const user = store.get(userAtom);

  if (!user.isAuthenticated) {
    throw redirect({ to: '/auth/login' });
  } else if (!user.emailIsVerified && user.emailVerifiedAsOf == null) {
    throw redirect({ to: '/auth/signup/verify-email' });
  } else if (!user.emailIsVerified) {
    throw redirect({ to: '/auth/verify-email' });
  }
}
