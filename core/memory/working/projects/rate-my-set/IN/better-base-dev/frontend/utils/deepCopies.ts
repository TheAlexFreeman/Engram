import cloneDeep from 'lodash-es/cloneDeep';

export function deepCopy<T>(o: T): T {
  // NOTE: At the time of writing, wrapping `cloneDeep` with `deepCopy` so that we can
  // decide to change the implementation of `deepCopy` later if we want to without
  // having to change all the places where we use `deepCopy`, etc.
  return cloneDeep(o);
}
