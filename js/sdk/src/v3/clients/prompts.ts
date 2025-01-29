import { r2rClient } from "../../r2rClient";
import {
  WrappedBooleanResponse,
  WrappedGenericMessageResponse,
  WrappedPromptResponse,
  WrappedPromptsResponse,
} from "../../types";

export class PromptsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new prompt with the given configuration.
   *
   * This endpoint allows superusers to create a new prompt with a
   * specified name, template, and input types.
   * @param name The name of the prompt
   * @param template The template string for the prompt
   * @param inputTypes A dictionary mapping input names to their types
   * @returns
   */
  async create(options: {
    name: string;
    template: string;
    inputTypes: Record<string, string>;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest("POST", "prompts", {
      data: options,
    });
  }

  /**
   * List all available prompts.
   *
   * This endpoint retrieves a list of all prompts in the system.
   * Only superusers can access this endpoint.
   * @returns
   */
  async list(): Promise<WrappedPromptsResponse> {
    return this.client.makeRequest("GET", "prompts");
  }

  /**
   * Get a specific prompt by name, optionally with inputs and override.
   *
   * This endpoint retrieves a specific prompt and allows for optional
   * inputs and template override.
   * Only superusers can access this endpoint.
   * @param options
   * @returns
   */
  async retrieve(options: {
    name: string;
    inputs?: string[];
    promptOverride?: string;
  }): Promise<WrappedPromptResponse> {
    const data: Record<string, any> = {
      ...(options.inputs && { inputs: options.inputs }),
      ...(options.promptOverride && {
        promptOverride: options.promptOverride,
      }),
    };

    return this.client.makeRequest("POST", `prompts/${options.name}`, {
      params: data,
    });
  }

  /**
   * Update an existing prompt's template and/or input types.
   *
   * This endpoint allows superusers to update the template and input types of an existing prompt.
   * @param options
   * @returns
   */
  async update(options: {
    name: string;
    template?: string;
    inputTypes?: Record<string, string>;
  }): Promise<WrappedGenericMessageResponse> {
    const params: Record<string, any> = {
      name: options.name,
    };
    if (options.template) {
      params.template = options.template;
    }
    if (options.inputTypes) {
      params.inputTypes = options.inputTypes;
    }

    return this.client.makeRequest("PUT", `prompts/${options.name}`, {
      data: params,
    });
  }

  /**
   * Delete a prompt by name.
   *
   * This endpoint allows superusers to delete an existing prompt.
   * @param name The name of the prompt to delete
   * @returns
   */
  async delete(options: { name: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `prompts/${options.name}`);
  }
}
