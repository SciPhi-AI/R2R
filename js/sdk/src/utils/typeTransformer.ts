/**
 * Utility type to convert string to camelCase
 */
type CamelCase<S extends string> = S extends `${infer P}_${infer Q}`
  ? `${P}${Capitalize<CamelCase<Q>>}`
  : S;

/**
 * Recursively transforms object keys to camelCase
 */
type CamelCaseKeys<T> = {
  [K in keyof T as K extends string ? CamelCase<K> : K]: T[K] extends Record<
    string,
    any
  >
    ? CamelCaseKeys<T[K]>
    : T[K] extends Array<any>
      ? Array<CamelCaseKeys<T[K][number]>>
      : T[K];
};

/**
 * Utility type to convert string to snake_case
 */
type SnakeCase<S extends string> = S extends `${infer T}${infer U}`
  ? T extends Uppercase<T>
    ? `${T extends Lowercase<T> ? "" : "_"}${Lowercase<T>}${SnakeCase<U>}`
    : `${T}${SnakeCase<U>}`
  : S;

/**
 * Recursively transforms object keys to snake_case
 */
type SnakeCaseKeys<T> = {
  [K in keyof T as K extends string ? SnakeCase<K> : K]: T[K] extends Record<
    string,
    any
  >
    ? SnakeCaseKeys<T[K]>
    : T[K] extends Array<any>
      ? Array<SnakeCaseKeys<T[K][number]>>
      : T[K];
};

const isObject = (value: unknown): value is Record<string | symbol, unknown> =>
  typeof value === "object" &&
  value !== null &&
  !Array.isArray(value) &&
  !(value instanceof Date) &&
  !(value instanceof Map) &&
  !(value instanceof Set) &&
  !(value instanceof Error) &&
  !(value instanceof RegExp);

const isValidInput = (value: unknown): boolean =>
  value !== null && value !== undefined;

const convertToCamelCase = (str: string): string => {
  // Preserve leading underscores
  const matches = str.match(/^(_+)/);
  const leadingUnderscores = matches ? matches[1] : "";
  const withoutLeadingUnderscores = str.slice(leadingUnderscores.length);

  if (!withoutLeadingUnderscores) {
    return str;
  }

  // Split by underscore and capitalize
  const converted = withoutLeadingUnderscores
    .split("_")
    .map((word, index) => {
      if (index === 0) {
        return word.toLowerCase();
      }
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join("");

  return leadingUnderscores + converted;
};

const convertToSnakeCase = (str: string): string => {
  // Preserve leading underscores
  const matches = str.match(/^(_+)/);
  const leadingUnderscores = matches ? matches[1] : "";
  const withoutLeadingUnderscores = str.slice(leadingUnderscores.length);

  if (!withoutLeadingUnderscores) {
    return str;
  }

  // Handle acronyms and regular camelCase
  const withAcronyms = withoutLeadingUnderscores
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1_$2")
    .replace(/([a-z\d])([A-Z])/g, "$1_$2")
    .toLowerCase();

  return leadingUnderscores + withAcronyms;
};

export function ensureCamelCase<T>(input: T): CamelCaseKeys<T> {
  if (!isValidInput(input)) {
    return input as CamelCaseKeys<T>;
  }

  if (Array.isArray(input)) {
    return input.map((item) => ensureCamelCase(item)) as CamelCaseKeys<T>;
  }

  if (!isObject(input)) {
    return input as CamelCaseKeys<T>;
  }

  try {
    const result = {} as Record<string | symbol, unknown>;

    // Handle all properties including symbols
    const allKeys = [
      ...Object.getOwnPropertyNames(input),
      ...Object.getOwnPropertySymbols(input),
    ];

    for (const key of allKeys) {
      const descriptor = Object.getOwnPropertyDescriptor(input, key)!;

      if (typeof key === "symbol") {
        Object.defineProperty(result, key, descriptor);
      } else {
        const newKey = convertToCamelCase(key.toString());
        const value = (input as any)[key];

        if (isObject(value)) {
          // Transform nested object and preserve its symbol properties
          const transformed = ensureCamelCase(value);
          result[newKey] = transformed;

          // Copy all symbol properties from the original nested object
          Object.getOwnPropertySymbols(value).forEach((symKey) => {
            const symDesc = Object.getOwnPropertyDescriptor(value, symKey)!;
            Object.defineProperty(transformed, symKey, symDesc);
          });
        } else if (Array.isArray(value)) {
          result[newKey] = value.map((item) => ensureCamelCase(item));
        } else {
          result[newKey] = value;
        }
      }
    }

    return result as CamelCaseKeys<T>;
  } catch (error) {
    throw new Error(
      `Failed to transform to camelCase: ${error instanceof Error ? error.message : "Unknown error"}`,
    );
  }
}

export function ensureSnakeCase<T>(input: T): SnakeCaseKeys<T> {
  if (!isValidInput(input)) {
    return input as SnakeCaseKeys<T>;
  }

  if (Array.isArray(input)) {
    return input.map((item) => ensureSnakeCase(item)) as SnakeCaseKeys<T>;
  }

  if (!isObject(input)) {
    return input as SnakeCaseKeys<T>;
  }

  try {
    const result = {} as Record<string | symbol, unknown>;
    const descriptors = Object.getOwnPropertyDescriptors(input);

    for (const key of [
      ...Object.getOwnPropertyNames(input),
      ...Object.getOwnPropertySymbols(input),
    ]) {
      const desc = descriptors[key as any];
      const { value } = desc;

      if (typeof key === "symbol") {
        if (isObject(value)) {
          const transformed = ensureSnakeCase(value);
          Object.defineProperty(result, key, {
            enumerable: true,
            configurable: true,
            writable: true,
            value: transformed,
          });
        } else {
          result[key] = value;
        }
      } else {
        const newKey = convertToSnakeCase(key.toString());
        if (isObject(value)) {
          const transformed = ensureSnakeCase(value) as Record<
            string | symbol,
            unknown
          >;
          result[newKey] = transformed;

          // Copy symbol properties
          Object.getOwnPropertySymbols(value).forEach((symKey) => {
            Object.defineProperty(transformed, symKey, {
              ...Object.getOwnPropertyDescriptor(value, symKey)!,
              value: value[symKey],
            });
          });
        } else if (Array.isArray(value)) {
          result[newKey] = value.map((item) => ensureSnakeCase(item));
        } else {
          result[newKey] = value;
        }
      }
    }

    return result as SnakeCaseKeys<T>;
  } catch (error) {
    throw new Error(
      `Failed to transform to snake_case: ${error instanceof Error ? error.message : "Unknown error"}`,
    );
  }
}
