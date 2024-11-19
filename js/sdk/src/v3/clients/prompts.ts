import { r2rClient } from "../../r2rClient";

export class PromptsClient {
  constructor(private client: r2rClient) {}

  async create(options: {
    name: string;
    template: string;
    inputTypes: Record<string, string>;
  }): Promise<any> {
    return this.client.makeRequest("POST", "prompts", {
      data: options,
    });
  }

  async list(): Promise<any> {
    return this.client.makeRequest("GET", "prompts");
  }

  async retrieve(options: {
    name: string;
    inputs?: string[];
    promptOverride?: string;
  }): Promise<any> {
    const data: Record<string, any> = {
      name: options.name,
      ...(options.inputs && { inputs: options.inputs }),
      ...(options.promptOverride && {
        promptOverride: options.promptOverride,
      }),
    };

    return this.client.makeRequest("POST", `prompts/${options.name}`, {
      params: data,
    });
  }

  async update(options: {
    name: string;
    template?: string;
    inputTypes?: Record<string, string>;
  }): Promise<any> {
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

  async delete(options: { name: string }): Promise<any> {
    return this.client.makeRequest("DELETE", `prompts/${options.name}`);
  }
}
