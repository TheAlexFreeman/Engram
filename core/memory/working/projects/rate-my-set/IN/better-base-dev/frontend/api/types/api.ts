export interface ValidationErrorData {
  [key: string]: string[] | undefined;
}

export class ValidationError extends Error {
  constructor(
    public response: Response,
    public data: ValidationErrorData,
  ) {
    super(JSON.stringify(data, null, 2));

    this.name = 'ValidationError';

    // We do the below 👇️ because we are extending a built-in class.
    Object.setPrototypeOf(this, ValidationError.prototype);
  }

  // --- Field Errors ---
  get fieldErrors(): Record<string, string[]> {
    return Object.entries(this.data as Record<string, string[]>).reduce((acc, [key, value]) => {
      if (key === 'nonFieldErrors' || key === 'MainCode_') {
        return acc;
      }
      return { ...acc, [key]: value };
    }, {});
  }

  get numFieldErrors(): number {
    return Object.keys(this.fieldErrors).length;
  }

  get hasFieldErrors(): boolean {
    return this.numFieldErrors > 0;
  }

  get hasExactlyOneFieldError(): boolean {
    return this.numFieldErrors === 1;
  }

  get firstFieldError(): [string, string] | [undefined, undefined] {
    const fieldName = Object.keys(this.fieldErrors)[0];
    return [fieldName, this.fieldErrors[fieldName][0]];
  }

  // ---              ---

  // --- Non-Field Errors ---
  get nonFieldErrors(): string[] {
    return this.data.nonFieldErrors || [];
  }

  get numNonFieldErrors(): number {
    return this.nonFieldErrors.length;
  }

  get hasNonFieldErrors(): boolean {
    return this.numNonFieldErrors > 0;
  }

  get hasExactlyOneNonFieldError(): boolean {
    return this.numNonFieldErrors === 1;
  }

  get firstNonFieldError(): string | undefined {
    return this.nonFieldErrors[0];
  }

  // ---                  ---

  // --- Total Errors ---

  get numTotalErrors(): number {
    return this.numFieldErrors + this.numNonFieldErrors;
  }

  // ---              ---

  // --- Error Codes ---

  get mainCode(): string | null {
    return (this.data?.MainCode_ as never as string | null | undefined) || null;
  }

  // ---             ---
}

export interface NotAuthenticatedErrorData {
  detail: string;
}

export class NotAuthenticatedError extends Error {
  constructor(
    public response: Response,
    public data: NotAuthenticatedErrorData,
  ) {
    super(data?.detail || '');

    this.name = 'NotAuthenticatedError';

    // We do the below 👇️ because we are extending a built-in class.
    Object.setPrototypeOf(this, NotAuthenticatedError.prototype);
  }

  get errorMessage(): string {
    return this.data?.detail || '';
  }
}

export interface PermissionsErrorData {
  detail: string;
}

export class PermissionsError extends Error {
  constructor(
    public response: Response,
    public data: PermissionsErrorData,
  ) {
    super(data?.detail || '');

    this.name = 'PermissionsError';

    // We do the below 👇️ because we are extending a built-in class.
    Object.setPrototypeOf(this, PermissionsError.prototype);
  }

  get errorMessage(): string {
    return this.data?.detail || '';
  }

  get isCSRFError(): boolean {
    return this.errorMessage.includes('CSRF');
  }

  get isNotAuthenticatedError(): boolean {
    return this.errorMessage.includes('Authentication credentials were not provided.');
  }

  asValidationError(): ValidationError {
    return new ValidationError(this.response, {
      nonFieldErrors: [this.errorMessage || 'You are not permitted to perform that action.'],
    });
  }

  asNotAuthenticatedError(): NotAuthenticatedError {
    return new NotAuthenticatedError(this.response, this.data);
  }
}

export class NotFoundError extends Error {
  constructor(
    public response: Response,
    message?: string,
  ) {
    super(message);

    this.name = 'NotFoundError';

    // We do the below 👇️ because we are extending a built-in class.
    Object.setPrototypeOf(this, NotFoundError.prototype);
  }

  asValidationError() {
    return new ValidationError(this.response, {
      nonFieldErrors: ['Not found.'],
    });
  }
}

export class ServerError extends Error {
  constructor(
    public response: Response,
    message?: string,
  ) {
    super(message);

    this.name = 'ServerError';

    // We do the below 👇️ because we are extending a built-in class.
    Object.setPrototypeOf(this, ServerError.prototype);
  }

  asValidationError() {
    return new ValidationError(this.response, {
      nonFieldErrors: [
        'An unexpected server error occurred. Please try again. If the issue continues ' +
          'please contact support.',
      ],
    });
  }
}
