import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAtomValue } from 'jotai';

import { ChangeEmailRequest, ChangeEmailRequestStatus } from '@/api/types/auth/changeEmail';
import { InitialData } from '@/api/types/initialData';
import { toaster } from '@/components/ui/toaster';
import { wrapRequestWithErrorHandling } from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import authService from '@/services/auth';
import changeEmailService from '@/services/changeEmail';
import { authUserAtom } from '@/state/auth';
import { getBestSingleErrorMessageFor } from '@/utils/errors';

export default function useUserChangeEmail({
  onSuccessfullyChanged,
}: {
  onSuccessfullyChanged?: (data: { toEmail: string }) => void;
}) {
  const user = useAtomValue(authUserAtom);

  const [isLoading, setIsLoading] = useState<boolean>(true);

  const [changeEmailRequest, setChangeEmailRequest] = useState<ChangeEmailRequest>({
    id: -1,
    user: user.id,
    fromEmail: '',
    toEmail: '',
    requestedAt: null,
    successfullyChangedAt: null,
    lastRequestedANewFromOrToEmailAt: null,
    lastSentAChangeEmailAt: null,
    lastSuccessfullyChangedAt: null,
    status: ChangeEmailRequestStatus.EMPTY,
    status_display: 'Empty',
    isLoading: true,
  });

  const load = useCallback(async () => {
    try {
      setIsLoading(true);
      const requestRecord = await changeEmailService.retrieve();
      setChangeEmailRequest(requestRecord);
    } catch {
      setChangeEmailRequest((r) => ({ ...r, isLoading: null }));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const hasPersistedRequest = useMemo<boolean>(
    () =>
      changeEmailRequest?.isLoading === undefined &&
      changeEmailRequest.id !== -1 &&
      changeEmailRequest.id != null,
    [changeEmailRequest?.isLoading, changeEmailRequest.id],
  );

  const requestResend = useCallback(async () => {
    try {
      setIsLoading(true);
      const updatedRecord = await changeEmailService.resend();
      setChangeEmailRequest(updatedRecord);
      return updatedRecord;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const requestChange = useCallback(
    async ({ toEmail }: { toEmail: string }) => {
      if (
        hasPersistedRequest &&
        changeEmailRequest.fromEmail === user.email &&
        changeEmailRequest.toEmail === toEmail &&
        toEmail
      ) {
        return await requestResend();
      }

      try {
        setIsLoading(true);
        const updatedRecord = await changeEmailService.request({ toEmail });
        setChangeEmailRequest(updatedRecord);
        return updatedRecord;
      } finally {
        setIsLoading(false);
      }
    },
    [
      hasPersistedRequest,
      changeEmailRequest.fromEmail,
      changeEmailRequest.toEmail,
      user.email,
      requestResend,
    ],
  );

  const refreshRef = useRef<{ inProgress: boolean }>({ inProgress: false });
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Check if the `user`'s `email` has been changed to the new `toEmail`. We'll also
  // reload the `changeEmailRequest`.
  const refresh = useCallback(async () => {
    const toEmail = changeEmailRequest.toEmail;
    let data: InitialData | null | undefined = null;

    if (refreshRef.current.inProgress) return;

    try {
      refreshRef.current.inProgress = true;
      setIsRefreshing(true);

      const request = authService.refreshMe();
      const wrapped = await wrapRequestWithErrorHandling({ awaitable: request });

      if (wrapped.hasError) {
        const errorMessage = getBestSingleErrorMessageFor(wrapped.error);

        toaster.create({
          title: 'Failed to Refresh Email Change Status',
          description: errorMessage,
          type: 'error',
          duration: 10000,
          meta: { closable: true },
        });
      } else {
        data = wrapped.result;
      }
    } finally {
      refreshRef.current.inProgress = false;
      setIsRefreshing(false);
    }

    if (data != null) {
      // If the `user.email` matches the `toEmail` then we'll assume that the email has
      // been changed.
      if (data.user.isAuthenticated && data.user.email && data.user.email == toEmail) {
        setJustChangedTo(toEmail);
      } else {
        toaster.create({
          title: 'Not Yet Changed',
          description: `Your email has not yet been changed to ${toEmail}.`,
          type: 'warning',
          duration: 10000,
          meta: { closable: true },
        });
      }
    }

    // No matter what, at the end, reload the `changeEmailRequest`.
    void load();
  }, [changeEmailRequest.toEmail, load]);

  const [justChangedTo, setJustChangedTo] = useState<string | null>(null);

  // Handle the success case of the email just being changed. We'll display the toast
  // immediately if the screen is visible, otherwise we'll display it when the screen
  // becomes visible (I.E. when they switch back to the tab).
  useEffect(() => {
    if (!justChangedTo) return;

    let shouldRemoveListener = false;
    const makeToastAppear = () => {
      setJustChangedTo(null);
      toaster.create({
        title: 'Successfully changed',
        description: `Your email has been successfully changed to ${justChangedTo}.`,
        type: 'success',
        duration: 7000,
        meta: { closable: true },
      });
    };

    if (
      document.visibilityState === 'visible' ||
      typeof window === 'undefined' ||
      !window.addEventListener
    ) {
      makeToastAppear();
    } else {
      shouldRemoveListener = true;
      window.addEventListener('visibilitychange', makeToastAppear, false);
    }
    if (onSuccessfullyChanged != null) {
      onSuccessfullyChanged({ toEmail: justChangedTo });
    }

    return () => {
      if (shouldRemoveListener) {
        window.removeEventListener('visibilitychange', makeToastAppear, false);
      }
    };
  }, [justChangedTo, onSuccessfullyChanged]);

  // Listen to another tab changing the email, and refresh the user and email change
  // request if that happens.
  useEffect(() => {
    const originHere = window.location.origin;
    const channel = new BroadcastChannel('significantEvents');

    const onMessage = (event: MessageEvent): void => {
      const { data, origin } = event;

      if (origin !== originHere) return;
      if (typeof data !== 'object') return;

      if (data?.eventType === 'user.emailChanged') {
        void refresh();
      }
    };

    channel.addEventListener('message', onMessage, false);

    return () => {
      channel.removeEventListener('message', onMessage);
      channel.close();
    };
  }, [refresh]);

  return {
    user,
    isLoading,
    isRefreshing,
    changeEmailRequest,
    hasPersistedRequest,
    load,
    requestResend,
    requestChange,
    justChangedTo,
    refresh,
  };
}
