'use client';

import { type CreateToasterReturn, createToaster } from '@chakra-ui/react';

const toaster = createToaster({
  placement: 'bottom',
  pauseOnPageIdle: true,
});

export type ToasterCreateArgs = Parameters<CreateToasterReturn['create']>[0];

export default toaster;
