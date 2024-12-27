import {
  ensureCamelCase,
  ensureSnakeCase,
} from "../../src/utils/typeTransformer";
import { describe, it, expect } from "@jest/globals";

describe("Type Transformers", () => {
  describe("ensureCamelCase", () => {
    it("handles basic transformations", () => {
      expect(ensureCamelCase({ user_name: "test" })).toEqual({
        userName: "test",
      });
    });

    it("handles nested objects", () => {
      const input = {
        user_details: {
          first_name: "John",
          last_name: "Doe",
          contact_info: {
            phone_number: "123",
            email_address: "test@test.com",
          },
        },
      };
      expect(ensureCamelCase(input)).toEqual({
        userDetails: {
          firstName: "John",
          lastName: "Doe",
          contactInfo: {
            phoneNumber: "123",
            emailAddress: "test@test.com",
          },
        },
      });
    });

    it("preserves Symbols as keys", () => {
      const testSymbol = Symbol("test");
      const nestedSymbol = Symbol("nested");
      const input = {
        [testSymbol]: "value",
        nested_object: {
          [nestedSymbol]: "nested value",
        },
      };

      const result = ensureCamelCase(input);
      expect(result[testSymbol]).toBe("value");
      expect(result.nestedObject[nestedSymbol]).toBe("nested value");
    });

    it("handles special JavaScript types", () => {
      const date = new Date("2024-01-01");
      const map = new Map([["key", "value"]]);
      const set = new Set(["value"]);

      const input = {
        date_field: date,
        map_field: map,
        set_field: set,
        nested_special: {
          inner_date: date,
        },
      };

      expect(ensureCamelCase(input)).toEqual({
        dateField: date,
        mapField: map,
        setField: set,
        nestedSpecial: {
          innerDate: date,
        },
      });
    });

    it("handles arrays with nested special types", () => {
      const map = new Map([["key", "value"]]);
      const input = {
        complex_array: [
          { nested_map: map },
          { nested_date: new Date("2024-01-01") },
        ],
      };

      const result = ensureCamelCase(input);
      expect(result.complexArray[0].nestedMap).toEqual(map);
      expect(result.complexArray[1].nestedDate instanceof Date).toBeTruthy();
    });

    it("properly handles acronyms and consecutive uppercase letters", () => {
      const input = {
        xml_parser: "value",
        html_content: "value",
        api_key: "value",
        db_connection: "value",
      };

      expect(ensureCamelCase(input)).toEqual({
        xmlParser: "value",
        htmlContent: "value",
        apiKey: "value",
        dbConnection: "value",
      });
    });

    it("preserves leading underscores", () => {
      const input = {
        _private_field: "value",
        __proto_field: "value",
        nested_object: {
          _internal_value: "test",
        },
      };

      expect(ensureCamelCase(input)).toEqual({
        _privateField: "value",
        __protoField: "value",
        nestedObject: {
          _internalValue: "test",
        },
      });
    });

    it("handles null and undefined values", () => {
      expect(ensureCamelCase(null)).toBeNull();
      expect(ensureCamelCase(undefined)).toBeUndefined();
      expect(
        ensureCamelCase({ null_value: null, undefined_value: undefined }),
      ).toEqual({ nullValue: null, undefinedValue: undefined });
    });
  });

  describe("ensureSnakeCase", () => {
    it("handles basic transformations", () => {
      expect(ensureSnakeCase({ userName: "test" })).toEqual({
        user_name: "test",
      });
    });

    it("handles nested objects", () => {
      const input = {
        userDetails: {
          firstName: "John",
          lastName: "Doe",
          contactInfo: {
            phoneNumber: "123",
            emailAddress: "test@test.com",
          },
        },
      };
      expect(ensureSnakeCase(input)).toEqual({
        user_details: {
          first_name: "John",
          last_name: "Doe",
          contact_info: {
            phone_number: "123",
            email_address: "test@test.com",
          },
        },
      });
    });

    it("properly converts acronyms to snake case", () => {
      const input = {
        XMLParser: "value",
        HTMLContent: "value",
        APIKey: "value",
        DBConnection: "value",
      };

      expect(ensureSnakeCase(input)).toEqual({
        xml_parser: "value",
        html_content: "value",
        api_key: "value",
        db_connection: "value",
      });
    });

    it("preserves special types in nested structures", () => {
      const date = new Date("2024-01-01");
      const map = new Map([["key", "value"]]);

      const input = {
        complexData: {
          dateField: date,
          mapField: map,
          nestedArray: [{ innerDate: date }],
        },
      };

      const result = ensureSnakeCase(input);
      expect(result.complex_data.date_field).toBe(date);
      expect(result.complex_data.map_field).toBe(map);
      expect(result.complex_data.nested_array[0].inner_date).toBe(date);
    });

    it("handles edge cases and special characters", () => {
      const input = {
        $specialKey: "test",
        _privateKey: "test",
        constructor: "test",
        key123Key: "test",
      };

      expect(ensureSnakeCase(input)).toEqual({
        $special_key: "test",
        _private_key: "test",
        constructor: "test",
        key123_key: "test",
      });
    });
  });

  describe("Error handling", () => {
    it("handles circular references", () => {
      const circular: any = { key: "value" };
      circular.self = circular;

      expect(() => ensureCamelCase(circular)).toThrow();
      expect(() => ensureSnakeCase(circular)).toThrow();
    });

    it("handles invalid inputs gracefully", () => {
      const inputs = [function () {}, /regex/, new Error("test")];

      inputs.forEach((input) => {
        expect(ensureCamelCase(input)).toBe(input);
        expect(ensureSnakeCase(input)).toBe(input);
      });
    });
  });
});
