import InputField, { InputFieldProps } from './InputField';

export type EmailFieldProps<T extends string> = InputFieldProps<T>;

export default function EmailField<T extends string>({
  type = 'email',
  ...rest
}: EmailFieldProps<T>) {
  return <InputField type={type} {...rest} />;
}
