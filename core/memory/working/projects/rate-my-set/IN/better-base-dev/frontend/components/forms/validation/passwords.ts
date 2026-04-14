export interface PasswordRule {
  key: string;
  label: string;
}

export interface CheckedPasswordRule {
  rule: PasswordRule;
  isValid: boolean;
}

export function checkPasswordRules(password: string): CheckedPasswordRule[] {
  const checkers: [(password: string) => boolean, string, string][] = [
    [minLength, 'minLength', 'At least 9 characters long'],
    [number, 'number', 'At least 1 number'],
    [specialCharacter, 'specialCharacter', 'At least 1 special character, !@#$&*%?'],
  ];

  const checked: CheckedPasswordRule[] = [];
  for (const [checker, key, label] of checkers) {
    const isValid = checker(password);
    checked.push({
      rule: {
        key,
        label,
      },
      isValid,
    });
  }

  return checked;
}

export function isValidPassword(password: string): boolean {
  for (const checked of checkPasswordRules(password)) {
    if (!checked.isValid) return false;
  }
  return !!password;
}

function minLength(password: string): boolean {
  return !!(password && password.length >= 9);
}

function specialCharacter(password: string): boolean {
  return !!(password && password.match(/[^a-zA-Z0-9]+/));
}

function number(password: string): boolean {
  return !!(password && password.match(/[0-9]+/));
}
