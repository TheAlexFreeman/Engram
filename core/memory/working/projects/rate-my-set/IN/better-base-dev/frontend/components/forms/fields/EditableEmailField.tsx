import EditableInputField, { EditableInputFieldProps } from './EditableInputField';

export type EditableEmailFieldProps<T extends string> = EditableInputFieldProps<T>;

export default function EditableEmailField<T extends string>({
  type = 'email',
  ...rest
}: EditableEmailFieldProps<T>) {
  return <EditableInputField type={type} {...rest} />;
}
