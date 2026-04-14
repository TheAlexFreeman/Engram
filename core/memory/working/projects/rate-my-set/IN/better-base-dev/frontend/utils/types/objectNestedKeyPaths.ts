// eslint-disable-next-line @typescript-eslint/no-unsafe-function-type
type Path<T> = T extends string | number | boolean | null | undefined | Function | Date
  ? []
  : {
      [K in keyof T]: [K, ...Path<T[K]>];
    }[keyof T];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Join<T extends any[], D extends string = '.'> = T extends []
  ? never
  : T extends [infer F]
    ? F extends string | number
      ? F
      : never
    : T extends [infer F, ...infer R]
      ? F extends string | number
        ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
          `${F}${D}${Join<Extract<R, any[]>>}`
        : never
      : string;

// Thanks to https://chat.openai.com/share/37a3c55e-05eb-495a-be02-0cc74e155a63 as of
// 2023-11-10.
export type NestedPaths<T> = Join<Path<T>>;
