import React, { ReactElement, useCallback, useMemo, useState } from 'react';

import { Icon, IconButton } from '@chakra-ui/react';
import EyeIcon from '@heroicons/react/24/solid/EyeIcon';
import EyeSlashIcon from '@heroicons/react/24/solid/EyeSlashIcon';

import { InputGroup } from '@/components/ui/input-group';

import InputField, { InputFieldProps } from './InputField';

export type PasswordFieldProps<T extends string> = Omit<InputFieldProps<T>, 'type'>;

// Thanks to https://chakra-ui.com/docs/components/input#password-input-example for the
// initial inspiration and implementation.
export default function PasswordField<T extends string>(props: PasswordFieldProps<T>) {
  const [show, setShow] = useState<boolean>(false);
  const toggle = useCallback(() => setShow((v) => !v), []);

  const inputType = useMemo(() => (show ? 'text' : 'password'), [show]);

  const InputWrapper = useCallback(
    ({ children }: { children: React.ReactNode }) => {
      return (
        <InputGroup
          w="100%"
          endElement={
            <IconButton
              size="sm"
              variant="ghost"
              colorPalette="gray"
              onClick={toggle}
              aria-label={show ? 'Hide password' : 'Show password'}
            >
              <Icon asChild>{show ? <EyeSlashIcon /> : <EyeIcon />}</Icon>
            </IconButton>
          }
        >
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {children as ReactElement<any>}
        </InputGroup>
      );
    },
    [show, toggle],
  );

  // eslint-disable-next-line react/prop-types
  const { slots: initialSlots, ...rest } = props;
  const slots = { ...(initialSlots || {}), InputWrapper };

  return <InputField type={inputType} slots={slots} {...rest} />;
}
