import {
  Dispatch,
  type JSX,
  SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {
  type CreateToasterReturn,
  Icon,
  IconButton,
  type InputProps,
  VStack,
  chakra,
} from '@chakra-ui/react';
import { PencilSimple as PencilSimpleIcon, X } from '@phosphor-icons/react';
import { FieldErrors, FormProvider, useForm } from 'react-hook-form';

import EditableInputField from '@/components/forms/fields/EditableInputField';
import { Button } from '@/components/ui/button';
import useHookFormBackendErrorsDisplay, {
  type ErrorWrappedRequestResult,
} from '@/hooks/forms/errors/useHookFormBackendErrorsDisplay';
import scrollToFirstHookFormError from '@/utils/forms/errors/scrollToFirstHookFormError';

import { type InputGroupProps } from '../ui/input-group';
import { toaster } from '../ui/toaster';

export type ConnectedSingleEditableFieldFormValues = {
  // Potential NOTE/TODO: Assuming `string` for now, if we need to make more generic
  // later we can. Also, there are some places later where `as` casts are made that
  // assume `string` for now as well.
  [fieldName: string]: string;
};

// Shorter alias for the type for this file.
type FormValues = ConnectedSingleEditableFieldFormValues;

export type ConnectedSingleEditableFieldFormProps<T extends object, F extends string & keyof T> = {
  obj: T;
  fieldName: F;
  fieldLabel: string;
  save: (data: FormValues) => Promise<T>;
  successToast: {
    // NOTE: `title` and `description` support formatting with "$new.[fieldName]" and
    // "$old.[fieldName]" if they're in the strings.
    title: string;
    description: string;
  } & Parameters<CreateToasterReturn['create']>[0];
  placeholder?: string | null;
  autocomplete?: string;
  required?: boolean;
  onSuccess?: () => void;
  hideLabel?: boolean;
  showCancelIcon?: boolean;
  startElement?: JSX.Element;
  endElement?: JSX.Element;
  inputProps?: InputProps;
  editControl?: { isEditable: boolean; setIsEditable: Dispatch<SetStateAction<boolean>> };

  isClickable?: boolean;
  isDisabled?: boolean;
};

export default function ConnectedSingleEditableFieldForm<
  T extends object,
  F extends string & keyof T,
>({
  obj,
  fieldName,
  fieldLabel,
  save,
  successToast,
  placeholder,
  autocomplete,
  required,
  onSuccess,
  hideLabel,
  showCancelIcon,
  startElement,
  endElement,
  inputProps,
  editControl,
  isClickable,
  isDisabled,
}: ConnectedSingleEditableFieldFormProps<T, F>) {
  // State for if we're currently editing the field and if a save is in progress.
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [internalIsEditable, setInternalIsEditable] = useState<boolean>(false);
  const isEditable = useMemo(
    () => (editControl ? editControl.isEditable : internalIsEditable),
    [editControl, internalIsEditable],
  );
  const setIsEditable = useMemo(
    () => (editControl ? editControl.setIsEditable : setInternalIsEditable),
    [editControl],
  );

  // Setup the form state.
  const initialValue = useMemo(() => (obj ? (obj[fieldName] as string) : ''), [obj, fieldName]);
  const formContext = useForm<FormValues>({
    defaultValues: {
      [fieldName]: initialValue,
    },
  });
  const {
    handleSubmit,
    control,
    setFocus,
    setValue,
    reset,
    formState: { isSubmitting },
  } = formContext;

  useEffect(() => {
    setValue<string>(fieldName, initialValue);
  }, [initialValue, fieldName, setValue]);

  const { BackendErrorsDisplay, errorWrappedRequest } = useHookFormBackendErrorsDisplay<FormValues>(
    { control },
  );

  // This calls the passed in `save`, wrapping it with error handling and handling
  // updating the form state, showing a success toast, and whatever else, etc. based on
  // the result.
  const performSave = useCallback(
    async (values: FormValues) => {
      let wrapped: ErrorWrappedRequestResult<T>;
      try {
        // Mark that we're saving.
        setIsSaving(true);

        // Prepare the request and wrap with error handling.
        const request = save(values);
        wrapped = await errorWrappedRequest(request);
      } finally {
        // No matter what, we're done saving.
        setIsSaving(false);
      }
      // If the request had an error they'll be shown automatically by
      // `<BackendErrorsDisplay ... />` below. Otherwise, if it was successful, we'll
      // proceed into this block and finalize things.
      if (!wrapped.hasError) {
        const updatedObj = wrapped.result;
        const updatedValue = updatedObj[fieldName] as string;

        // Reset the form state with the new value.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setValue(fieldName, updatedValue as any);
        reset({ [fieldName]: updatedValue });

        // Presuming the save completed, we're no longer editing.
        setIsEditable(false);

        // Prepare and show the toast.
        const toastTitle = successToast.title
          .replace(`$new.${fieldName}`, updatedValue)
          .replace(`$old.${fieldName}`, initialValue);
        const toastDescription = successToast.description
          .replace(`$new.${fieldName}`, updatedValue)
          .replace(`$old.${fieldName}`, initialValue);
        toaster.create({
          title: toastTitle,
          description: toastDescription,
          type: successToast.type || 'success',
          duration: successToast.duration ?? 7000,
          meta: { ...(successToast?.meta || {}), closable: successToast?.meta?.isClosable ?? true },
        });

        if (onSuccess != null) {
          onSuccess();
        }
      } else {
        // Otherwise, if there was an error, focus back in on the input.
        setTimeout(() => {
          setFocus(fieldName);
        }, 0);
      }
    },
    [
      save,
      errorWrappedRequest,
      fieldName,
      setValue,
      reset,
      setIsEditable,
      successToast.title,
      successToast.description,
      successToast.type,
      successToast.duration,
      successToast?.meta,
      initialValue,
      onSuccess,
      setFocus,
    ],
  );

  // Right now, submit is just calling `performSave`.
  const onSubmit = useCallback(
    async (data: FormValues) => {
      await performSave(data);
    },
    [performSave],
  );

  // NOTE: We may not need to actually scroll to the error since the user likely would
  // already be able to see it (and there's only one field), but we'll leave it just in
  // case.
  const onError = useCallback(
    async (errors: FieldErrors<FormValues>) => {
      scrollToFirstHookFormError({ errors, setFocus });
    },
    [setFocus],
  );

  // Cancelling, at the time of writing, is just turning off editing and resetting the
  // form state.
  const onClear = useCallback(() => {
    void performSave({ [fieldName]: '' });
    setIsEditable(false);
    reset();
  }, [fieldName, performSave, reset, setIsEditable]);

  // When we click into the editable state, we'll set the state and then set the focus
  // on the field but give the `0` delay so that React has performed the next render
  // before `setFocus` is called.
  const onIntoEditableClick = useCallback(() => {
    setIsEditable(true);
    setTimeout(() => {
      setFocus(fieldName);
    }, 0);
  }, [setIsEditable, setFocus, fieldName]);

  // By putting `type="submit"` on the button the form will submit automatically when
  // the button is clicked, etc.
  const saveButtonRef = useRef<HTMLButtonElement>(null);
  const clearButtonRef = useRef<HTMLButtonElement>(null);
  const saveButton = useMemo(
    () => (
      <>
        {showCancelIcon && (
          <IconButton
            variant="ghost"
            colorPalette="gray"
            size="sm"
            ref={clearButtonRef}
            aria-label={`Clear ${fieldLabel}`}
            onClick={onClear}
          >
            <Icon boxSize="20px" cursor="pointer">
              <X />
            </Icon>
          </IconButton>
        )}
        <Button
          size="sm"
          type="submit"
          ref={saveButtonRef}
          disabled={isSubmitting || isSaving}
          loading={isSubmitting || isSaving}
          aria-label={`Done editing ${fieldLabel}`}
          px={6}
          m={1}
          mr={showCancelIcon ? 4 : 1}
        >
          Save
        </Button>
      </>
    ),
    [showCancelIcon, onClear, isSubmitting, isSaving, fieldLabel],
  );

  // Show the save button if we're in editing mode, otherwise show the normal
  // pencil/edit button.
  const toggleEditButton = useMemo(
    () =>
      isEditable ? (
        saveButton
      ) : (
        <IconButton
          size="xs"
          variant="ghost"
          colorPalette="gray"
          onClick={onIntoEditableClick}
          aria-label={`Done editing ${fieldLabel}`}
          className="editButton"
        >
          <Icon color="text.lighter" fontSize="1rem">
            <PencilSimpleIcon weight="fill" />
          </Icon>
        </IconButton>
      ),
    [isEditable, saveButton, onIntoEditableClick, fieldLabel],
  );

  // If the blur was actually from clicking the save button, prevent the default and
  // stop the propagation so that the form submits properly through the button, etc.
  // Otherwise, if it wasn't from clicking the save button, then we'll call `onCancel`.
  const onBlur = useCallback(
    (e: React.FocusEvent<HTMLElement>) => {
      const related = e.relatedTarget;
      if (related != null && related === saveButtonRef.current) {
        e.preventDefault();
        e.stopPropagation();
      } else if (related != null && related === clearButtonRef.current) {
        e.preventDefault();
        e.stopPropagation();
        onClear();
      } else {
        setIsEditable(false);
        reset({ [fieldName]: initialValue });
      }
    },
    [fieldName, initialValue, onClear, reset, setIsEditable],
  );

  const inputGroupStartElementProps = useMemo<InputGroupProps['startElementProps']>(() => {
    if (isEditable) return { width: showCancelIcon ? '5rem' : '4rem' };
    return {};
  }, [isEditable, showCancelIcon]);

  const { finalizedInputProps, finalizedInputGroupProps } = useMemo<{
    finalizedInputProps: InputProps;
    finalizedInputGroupProps: Omit<InputGroupProps, 'children'>;
  }>(() => {
    const nextInputProps: InputProps = { name: fieldName, ...inputProps };
    const nextInputGroupProps: Omit<InputGroupProps, 'children'> = {
      w: '100%',
      startElementProps: inputGroupStartElementProps,
    };
    if (isClickable) {
      nextInputGroupProps.onClick = onIntoEditableClick;
      if (!isEditable) {
        nextInputProps.cursor = 'pointer';
        nextInputGroupProps.cursor = 'pointer';
      }
    }
    return {
      finalizedInputProps: nextInputProps,
      finalizedInputGroupProps: nextInputGroupProps,
    };
  }, [
    fieldName,
    inputProps,
    isClickable,
    onIntoEditableClick,
    isEditable,
    inputGroupStartElementProps,
  ]);

  return (
    <FormProvider {...formContext}>
      <chakra.form onSubmit={handleSubmit(onSubmit, onError)} w="100%">
        <VStack gap="2" w="100%">
          <VStack w="100%">
            <EditableInputField
              name={fieldName}
              label={hideLabel ? '' : fieldLabel}
              required={required}
              disabled={isSubmitting || isSaving || isDisabled}
              placeholder={placeholder == null ? undefined : placeholder || fieldLabel}
              autocomplete={autocomplete}
              slotProps={{
                input: finalizedInputProps,
                inputGroup: finalizedInputGroupProps,
              }}
              isEditable={isEditable}
              setIsEditable={setIsEditable}
              labelForEdit={`Edit ${fieldLabel}`}
              labelForDoneEditing={`Done editing ${fieldLabel}`}
              toggleEditButton={endElement ? endElement : toggleEditButton}
              shouldSetNotEditableOnBlur={false}
              onBlur={onBlur}
              startElement={startElement}
            />
          </VStack>
          <VStack gap="2" w="100%" align="flex-start">
            <BackendErrorsDisplay />
          </VStack>
        </VStack>
      </chakra.form>
    </FormProvider>
  );
}
