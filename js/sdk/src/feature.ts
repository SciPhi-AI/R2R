import type * as PostHogJs from "posthog-js";
import { PostHog as PostHogNodeClient } from "posthog-node";
import { v4 as uuidv4 } from "uuid";

const posthogApiKey = "phc_OPBbibOIErCGc4NDLQsOrMuYFTKDmRwXX6qxnTr6zpU";
const posthogHost = "https://us.i.posthog.com";

let posthog: PostHogJs.PostHog | PostHogNodeClient;
let isPostHogInitialized = false;
let distinctId: string = uuidv4();

function isBrowser(
  client: PostHogJs.PostHog | PostHogNodeClient,
): client is PostHogJs.PostHog {
  return typeof window !== "undefined";
}

let telemetryEnabled = true;

export function initializeTelemetry(enableTelemetry: boolean = true) {
  if (isPostHogInitialized) {
    return;
  }

  telemetryEnabled =
    enableTelemetry && process.env.R2R_JS_DISABLE_TELEMETRY !== "true";

  if (typeof window !== "undefined") {
    // Browser environment
    import("posthog-js").then((posthogJs) => {
      posthog = posthogJs.default;
      posthog.init(posthogApiKey, {
        api_host: posthogHost,
      });

      if (!telemetryEnabled) {
        posthog.opt_out_capturing();
      }

      window.addEventListener("beforeunload", () => {
        if (telemetryEnabled) {
          (posthog as PostHogJs.PostHog).capture("PageUnload");
        }
      });

      isPostHogInitialized = true;
    });
  } else {
    // Node.js environment
    posthog = new PostHogNodeClient(posthogApiKey, { host: posthogHost });
    if (!telemetryEnabled) {
      posthog.disable();
    }
    isPostHogInitialized = true;
  }
}

function captureEvent(eventName: string, properties?: Record<string, any>) {
  if (isPostHogInitialized && telemetryEnabled) {
    const environment = typeof window !== "undefined" ? "browser" : "node";
    const eventProperties = { ...properties, environment };

    if (isBrowser(posthog)) {
      posthog.capture(eventName, eventProperties);
    } else {
      (posthog as PostHogNodeClient).capture({
        distinctId: distinctId,
        event: eventName,
        properties: eventProperties,
      });
    }
  }
}

type AsyncFunction = (...args: any[]) => Promise<any>;

export function feature(operationName: string) {
  return function (
    _target: any,
    _propertyKey: string | symbol,
    descriptor: TypedPropertyDescriptor<AsyncFunction>,
  ): TypedPropertyDescriptor<AsyncFunction> {
    const originalMethod = descriptor.value!;

    descriptor.value = async function (
      this: any,
      ...args: any[]
    ): Promise<any> {
      try {
        const result = await originalMethod.apply(this, args);
        if (this.anonymousTelemetry) {
          captureEvent("TSClient", { operation: operationName });
        }
        return result;
      } catch (error: unknown) {
        if (this.anonymousTelemetry) {
          captureEvent("TSClient", {
            operation: operationName,
            errorMessage:
              error instanceof Error ? error.message : "Unknown error",
          });
        }
        throw error;
      } finally {
        if (isPostHogInitialized && !isBrowser(posthog) && telemetryEnabled) {
          // Flush events in Node.js environment
          await (posthog as PostHogNodeClient).shutdown();
        }
      }
    };

    return descriptor;
  };
}

export function featureGenerator(operationName: string) {
  return function (
    _target: any,
    _propertyKey: string | symbol,
    descriptor: TypedPropertyDescriptor<
      (...args: any[]) => AsyncGenerator<any, any, any>
    >,
  ): TypedPropertyDescriptor<
    (...args: any[]) => AsyncGenerator<any, any, any>
  > {
    const originalMethod = descriptor.value!;

    descriptor.value = async function* (
      this: any,
      ...args: any[]
    ): AsyncGenerator<any, any, any> {
      try {
        const generator = originalMethod.apply(this, args);
        for await (const chunk of generator) {
          yield chunk;
        }
        if (this.anonymousTelemetry) {
          captureEvent("TSClient", { operation: operationName });
        }
      } catch (error: unknown) {
        if (this.anonymousTelemetry) {
          captureEvent("TSClient", {
            operation: operationName,
            errorMessage:
              error instanceof Error ? error.message : "Unknown error",
          });
        }
        throw error;
      } finally {
        if (isPostHogInitialized && !isBrowser(posthog) && telemetryEnabled) {
          // Flush events in Node.js environment
          await (posthog as PostHogNodeClient).shutdown();
        }
      }
    };

    return descriptor;
  };
}
