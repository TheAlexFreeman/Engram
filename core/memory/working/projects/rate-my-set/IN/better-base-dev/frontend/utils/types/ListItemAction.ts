export type Action<T> =
  | { action: 'delete'; result: 'success'; obj: T }
  | { action: 'delete'; result: 'failure'; obj: T }
  | { action: 'update'; result: 'success'; obj: T }
  | { action: 'update'; result: 'cancel'; obj: T }
  | { action: 'update'; result: 'failure'; obj: T };

export type OnActionCallback<T> = (action: Action<T>) => void;

export type ActionMenuBaseProps<T> = {
  obj: T;
  onAction?: OnActionCallback<T>;
};
