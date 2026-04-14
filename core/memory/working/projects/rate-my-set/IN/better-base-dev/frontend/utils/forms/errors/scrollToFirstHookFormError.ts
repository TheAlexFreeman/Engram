import { FieldValues, Path, UseFormReturn } from 'react-hook-form';

export type ScrollToFirstHookFormErrorArgs<
  TFieldValues extends FieldValues = FieldValues,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TContext = any,
> = {
  errors: UseFormReturn<TFieldValues, TContext>['formState']['errors'];
  setFocus: UseFormReturn<TFieldValues, TContext>['setFocus'];
};

export default function scrollToFirstHookFormError<
  TFieldValues extends FieldValues = FieldValues,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TContext = any,
>({
  errors,
  setFocus,
}: ScrollToFirstHookFormErrorArgs<TFieldValues, TContext>): Path<TFieldValues> | null {
  // Thanks to https://stackoverflow.com/a/72318129
  const firstError = (Object.keys(errors) as Array<keyof typeof errors>).reduce<
    keyof typeof errors | null
  >((field, a) => {
    const fieldKey = field as keyof typeof errors;
    return errors[fieldKey] ? fieldKey : a;
  }, null);

  if (firstError) {
    setFocus(firstError as Path<TFieldValues>);
    return firstError as Path<TFieldValues>;
  }

  return null;
}
