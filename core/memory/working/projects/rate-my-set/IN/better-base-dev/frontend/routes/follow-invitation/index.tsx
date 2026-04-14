import { useCallback, useEffect, useRef } from 'react';

import { createFileRoute, redirect } from '@tanstack/react-router';

import { Invitation } from '@/api/types/accounts/invitations';
import { User } from '@/api/types/accounts/users';
import { ProgressCircleRing, ProgressCircleRoot } from '@/components/ui/progress-circle';
import { toaster } from '@/components/ui/toaster';
import { wrapRequestWithErrorHandling } from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import invitationService from '@/services/invitations';
import { initialDataAtom } from '@/state/auth';
import store from '@/state/store';

export const Route = createFileRoute('/follow-invitation/')({
  loader: followInvitationLoader,
  component: FollowInvitation,
});

function followInvitationLoader() {
  const initialValues = store.get(initialDataAtom);
  const data = initialValues.extra.followInvitation as FollowInvitationData | null;

  if (data == null || data.hasError) {
    throw redirect({ from: Route.fullPath, to: 'error' });
  }

  return data;
}

export interface FollowInvitationDataWithoutError {
  hasError: false;
  canFollow: true;
  invitation: Invitation;
  existingUser: User | null;
  requiresSignup: boolean;
  followedThroughEmail: string | null;
  authenticatedUser: User | null;
  inviteeIsAuthenticated: boolean;
  shouldAutoAccept: boolean;
}

export interface FollowInvitationDataWithError {
  hasError: true;
  canFollow: boolean;
  invitation: null;
  existingUser: null;
  requiresSignup: 'unknown';
  followedThroughEmail: null;
  authenticatedUser: User | null;
  inviteeIsAuthenticated: null;
  shouldAutoAccept: false;
}

export type FollowInvitationData = FollowInvitationDataWithoutError | FollowInvitationDataWithError;

function FollowInvitation() {
  const navigate = Route.useNavigate();

  const data = Route.useLoaderData();
  const { invitation, requiresSignup, inviteeIsAuthenticated, shouldAutoAccept } = data;

  const inProgressRef = useRef<{ action: 'accepting' | '' }>({ action: '' });

  const autoAcceptHandler = useCallback(async () => {
    if (inProgressRef.current?.action) return;

    let wrapped;
    try {
      inProgressRef.current.action = 'accepting';
      const request = invitationService.accept(invitation.id);
      wrapped = await wrapRequestWithErrorHandling({ awaitable: request });
    } finally {
      inProgressRef.current.action = '';
    }
    if (wrapped.hasError) {
      // NOTE: At this time of writing, in practice, this should almost never happen. If
      // it does, going to this page should show a better error message and/or
      // potentially work properly in case there was an authentication-related mismatch
      // or error, etc.
      void navigate({ to: '/auth/login/from-invitation' });
    } else {
      toaster.create({
        title: 'Success',
        description: `Successfully logged in and joined ${invitation.teamDisplayName}.`,
        type: 'success',
        duration: 7000,
        meta: { closable: true },
      });
      void navigate({
        to: '/accounts/$accountId/team',
        params: { accountId: invitation.account.id.toString() },
      });
    }
  }, [invitation.id, invitation.teamDisplayName, invitation.account.id, navigate]);

  useEffect(() => {
    if (requiresSignup) {
      void navigate({ to: '/auth/signup/from-invitation' });
    } else if (inviteeIsAuthenticated && shouldAutoAccept) {
      void autoAcceptHandler();
    } else {
      void navigate({ to: '/auth/login/from-invitation' });
    }
  }, [autoAcceptHandler, inviteeIsAuthenticated, navigate, requiresSignup, shouldAutoAccept]);

  return (
    <ProgressCircleRoot value={null} size="md">
      <ProgressCircleRing cap="round" />
    </ProgressCircleRoot>
  );
}
