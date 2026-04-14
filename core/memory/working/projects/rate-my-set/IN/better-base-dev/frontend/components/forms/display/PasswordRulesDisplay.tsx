import { useMemo } from 'react';

import { Icon, List } from '@chakra-ui/react';
import CheckIcon from '@heroicons/react/20/solid/esm/CheckIcon';
import { default as MinusIcon, default as XMark } from '@heroicons/react/20/solid/esm/MinusIcon';
import { useFormContext, useWatch } from 'react-hook-form';

import { CheckedPasswordRule, checkPasswordRules } from '../validation/passwords';

export interface PasswordRulesDisplayProps<T extends string> {
  fieldName: T;
}

export default function PasswordRulesDisplay<T extends string>({
  fieldName,
}: PasswordRulesDisplayProps<T>) {
  const {
    control,
    formState: { errors },
  } = useFormContext();

  const error = errors[fieldName];
  const errorMessage = error?.message as string | undefined;
  const hasError = !!error && !!errorMessage;

  const password = useWatch({ control, name: fieldName });

  const checkedRules = useMemo<CheckedPasswordRule[]>(() => {
    return checkPasswordRules(password);
  }, [password]);

  return (
    <List.Root textStyle="body2" display="flex" flexDirection="column" gap="2" color="text.light">
      {checkedRules.map((checkedRule) => {
        const { isValid } = checkedRule;
        const color = !hasError && !isValid ? 'inherit' : isValid ? 'fg.success' : 'fg.error';
        return (
          <List.Item key={checkedRule.rule.key} color={color} listStyleType={'none'} ms="1">
            <List.Indicator asChild color={color} marginInlineStart="calc(-0.25em - 0)">
              <Icon size="sm">
                {!hasError && !isValid ? <MinusIcon /> : isValid ? <CheckIcon /> : <XMark />}
              </Icon>
            </List.Indicator>
            <span>{checkedRule.rule.label}</span>
          </List.Item>
        );
      })}
    </List.Root>
  );
}
