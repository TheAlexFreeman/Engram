import React, { Dispatch, type JSX, SetStateAction, useCallback } from 'react';

import { Icon, IconButton, Text, VStack } from '@chakra-ui/react';
import { CheckFat as CheckFatIcon, PencilSimple as PencilSimpleIcon } from '@phosphor-icons/react';
import { useFormContext } from 'react-hook-form';

import { InputGroup } from '@/components/ui/input-group';

import InputField, { InputFieldProps } from './InputField';

export type EditableInputFieldProps<T extends string> = Omit<InputFieldProps<T>, 'readonly'> & {
  name: T;
  isEditable: boolean;
  setIsEditable: Dispatch<SetStateAction<boolean>>;
  labelForEdit: string;
  labelForDoneEditing: string;
  showDoneEditingIcon?: boolean;
  shouldSetNotEditableOnBlur?: boolean;
  disableLabelFocus?: boolean;
  toggleEditButton?: JSX.Element;
  onBlur?: (e: React.FocusEvent<HTMLElement>) => void;
  description?: string;
  startElement?: JSX.Element;
};

// Thanks to https://chakra-ui.com/docs/components/input#password-input-example for the
// initial inspiration and implementation.
export default function EditableInputField<T extends string>({
  name,
  isEditable,
  setIsEditable,
  labelForEdit,
  labelForDoneEditing,
  showDoneEditingIcon = true,
  shouldSetNotEditableOnBlur = true,
  disableLabelFocus = true,
  toggleEditButton,
  onBlur,
  description,
  startElement,
  ...rest
}: EditableInputFieldProps<T>) {
  const { setFocus } = useFormContext();

  const toggle = useCallback(() => setIsEditable((v) => !v), [setIsEditable]);

  const handleToggleClick = useCallback(
    (
      e: React.MouseEvent<HTMLButtonElement | HTMLDivElement>,
      preventDefault: boolean = true,
      focus: boolean = true,
    ) => {
      const shouldFocus = !isEditable && focus;

      if (preventDefault) {
        e.preventDefault();
      }

      toggle();

      if (shouldFocus) {
        window.setTimeout(() => {
          setFocus(name);
        }, 0);
      }
    },
    [name, toggle, isEditable, setFocus],
  );

  const InputWrapper = useCallback(
    ({ children }: { children: React.ReactNode }) => {
      const inputGroup = (
        <InputGroup
          w="100%"
          startElement={startElement}
          onDoubleClick={(e) => (!isEditable ? handleToggleClick(e, false, true) : undefined)}
          endElement={
            (!isEditable || showDoneEditingIcon) && toggleEditButton ? (
              toggleEditButton
            ) : (
              <IconButton
                size="sm"
                rounded="full"
                variant="ghost"
                colorPalette="gray"
                disabled={rest?.disabled}
                onClick={handleToggleClick}
                aria-label={isEditable ? labelForDoneEditing : labelForEdit}
                className="editButton"
              >
                <Icon color="text.lighter">
                  {isEditable ? <CheckFatIcon weight="fill" /> : <PencilSimpleIcon weight="fill" />}
                </Icon>
              </IconButton>
            )
          }
          {...rest?.slotProps?.inputGroup}
        >
          {children as React.ReactElement}
        </InputGroup>
      );
      return description ? (
        <VStack>
          {description && <Text alignSelf="start">{description}</Text>}
          {inputGroup}
        </VStack>
      ) : (
        inputGroup
      );
    },
    [
      rest?.slotProps?.inputGroup,
      rest?.disabled,
      isEditable,
      showDoneEditingIcon,
      toggleEditButton,
      handleToggleClick,
      labelForDoneEditing,
      labelForEdit,
      description,
      startElement,
    ],
  );

  const { slots: initialSlots, slotProps: initialSlotProps, ...remaining } = rest;
  const slots = { ...(initialSlots || {}), InputWrapper };

  const handleBlur = useCallback(
    (e: React.FocusEvent<HTMLElement>) => {
      if (initialSlotProps?.register?.onBlur) {
        initialSlotProps.register.onBlur(e);
      }

      if (shouldSetNotEditableOnBlur) {
        setIsEditable(false);
      }

      if (onBlur != null) {
        onBlur(e);
      }
    },
    [initialSlotProps?.register, shouldSetNotEditableOnBlur, setIsEditable, onBlur],
  );

  const slotProps = {
    ...(initialSlotProps || {}),
    register: { ...(initialSlotProps?.register || {}), onBlur: handleBlur },
  };
  if (slotProps.input?.variant == null && !isEditable) {
    slotProps.input = { ...(slotProps.input || {}), variant: 'subtle' };
  }

  return (
    <InputField
      name={name}
      readonly={!isEditable}
      disableLabelFocus={disableLabelFocus}
      slots={slots}
      slotProps={slotProps}
      {...remaining}
    />
  );
}
