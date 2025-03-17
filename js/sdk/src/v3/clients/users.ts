import { r2rClient } from "../../r2rClient";
import {
  WrappedAPIKeyResponse,
  WrappedAPIKeysResponse,
  WrappedBooleanResponse,
  WrappedGenericMessageResponse,
  WrappedCollectionsResponse,
  WrappedTokenResponse,
  WrappedUserResponse,
  WrappedUsersResponse,
  WrappedLimitsResponse,
  WrappedLoginResponse,
} from "../../types";
import { downloadBlob } from "../../utils";

let fs: any;
if (typeof window === "undefined") {
  fs = require("fs");
}

export class UsersClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new user.
   * @param email User's email address
   * @param password User's password
   * @param name The name for the new user
   * @param bio The bio for the new user
   * @param profilePicture The profile picture for the new user
   * @returns WrappedUserResponse
   */
  async create(options: {
    email: string;
    password: string;
    name?: string;
    bio?: string;
    profilePicture?: string;
  }): Promise<WrappedUserResponse> {
    const data = {
      ...(options.email && { email: options.email }),
      ...(options.password && { password: options.password }),
      ...(options.name && { name: options.name }),
      ...(options.bio && { bio: options.bio }),
      ...(options.profilePicture && {
        profile_picture: options.profilePicture,
      }),
    };

    return this.client.makeRequest("POST", "users", {
      data: data,
    });
  }

  /**
   * Send a verification email to a user.
   * @param email User's email address
   * @returns WrappedGenericMessageResponse
   */
  async sendVerificationEmail(options: {
    email: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest("POST", "users/send-verification-email", {
      data: options.email,
      headers: {
        "Content-Type": "text/plain",
      },
    });
  }
  /**
   * Delete a specific user.
   * Users can only delete their own account unless they are superusers.
   * @param id User ID to delete
   * @param password User's password
   * @returns
   */
  async delete(options: {
    id: string;
    password: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `users/${options.id}`, {
      data: {
        password: options.password,
      },
    });
  }

  /**
   * Verify a user's email address.
   * @param email User's email address
   * @param verificationCode Verification code sent to the user's email
   */
  async verifyEmail(options: {
    email: string;
    verificationCode: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest("POST", "users/verify-email", {
      data: options,
    });
  }

  /**
   * Log in a user.
   * @param email User's email address
   * @param password User's password
   * @returns
   */
  async login(options: {
    email: string;
    password: string;
  }): Promise<WrappedLoginResponse> {
    const response = await this.client.makeRequest("POST", "users/login", {
      data: {
        username: options.email,
        password: options.password,
      },
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });

    if (response?.results) {
      this.client.setTokens(
        response.results.accessToken.token,
        response.results.refreshToken.token,
      );
    }

    return response;
  }

  /**
   * Log in using an existing access token.
   * @param accessToken Existing access token
   * @returns
   */
  async loginWithToken(options: { accessToken: string }): Promise<any> {
    this.client.setTokens(options.accessToken, null);

    try {
      const response = await this.client.makeRequest("GET", "users/me");

      return {
        results: {
          access_token: {
            token: options.accessToken,
            token_type: "access_token",
          },
        },
      };
    } catch (error) {
      this.client.setTokens(null, null);
      throw new Error("Invalid token provided");
    }
  }

  /**
   * Log out the current user.
   * @returns
   */
  async logout(): Promise<WrappedGenericMessageResponse> {
    const response = await this.client.makeRequest("POST", "users/logout");
    this.client.setTokens(null, null);
    return response;
  }

  /**
   * Refresh the access token using the refresh token.
   * @returns
   */
  async refreshAccessToken(): Promise<WrappedTokenResponse> {
    const refreshToken = this.client.getRefreshToken();
    if (!refreshToken) {
      throw new Error("No refresh token available. Please login again.");
    }

    const response = await this.client.makeRequest(
      "POST",
      "users/refresh-token",
      {
        data: refreshToken,
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      },
    );

    if (response?.results) {
      this.client.setTokens(
        response.results.accessToken.token,
        response.results.refreshToken.token,
      );
    } else {
      throw new Error("Invalid response structure");
    }

    return response;
  }

  /**
   * Change the user's password.
   * @param current_password User's current password
   * @param new_password User's new password
   * @returns
   */
  async changePassword(options: {
    current_password: string;
    new_password: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest("POST", "users/change-password", {
      data: options,
    });
  }

  async requestPasswordReset(
    email: string,
  ): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest("POST", "users/request-password-reset", {
      data: email,
      headers: {
        "Content-Type": "text/plain",
      },
    });
  }

  /**
   * Reset a user's password using a reset token.
   * @param reset_token Reset token sent to the user's email
   * @param new_password New password for the user
   * @returns
   */
  async resetPassword(options: {
    reset_token: string;
    new_password: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest("POST", "users/reset-password", {
      data: options,
    });
  }

  /**
   * List users with pagination and filtering options.
   * @param ids Optional list of user IDs to filter by
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
  }): Promise<WrappedUsersResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.ids) {
      params.ids = options.ids;
    }

    return this.client.makeRequest("GET", "users", {
      params,
    });
  }

  /**
   * Get a specific user.
   * @param id User ID to retrieve
   * @returns
   */
  async retrieve(options: { id: string }): Promise<WrappedUserResponse> {
    return this.client.makeRequest("GET", `users/${options.id}`);
  }

  /**
   * Get detailed information about the currently authenticated user.
   * @returns
   */
  async me(): Promise<WrappedUserResponse> {
    return this.client.makeRequest("GET", `users/me`);
  }

  /**
   * Update a user.
   * @param id User ID to update
   * @param email Optional new email for the user
   * @param is_superuser Optional new superuser status for the user
   * @param name Optional new name for the user
   * @param bio Optional new bio for the user
   * @param profilePicture Optional new profile picture for the user
   * @returns
   */
  async update(options: {
    id: string;
    email?: string;
    isSuperuser?: boolean;
    name?: string;
    bio?: string;
    profilePicture?: string;
    metadata?: Record<string, string | null>;
  }): Promise<WrappedUserResponse> {
    const data = {
      ...(options.email && { email: options.email }),
      ...(options.isSuperuser !== undefined && {
        is_superuser: options.isSuperuser,
      }),
      ...(options.name && { name: options.name }),
      ...(options.bio && { bio: options.bio }),
      ...(options.profilePicture && {
        profile_picture: options.profilePicture,
      }),
      ...(options.metadata && { metadata: options.metadata }),
    };

    return this.client.makeRequest("POST", `users/${options.id}`, {
      data,
    });
  }

  /**
   * Get all collections associated with a specific user.
   * @param id User ID to retrieve collections for
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listCollections(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedCollectionsResponse> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
    };

    return this.client.makeRequest("GET", `users/${options.id}/collections`, {
      params,
    });
  }

  /**
   * Add a user to a collection.
   * @param id User ID to add
   * @param collectionId Collection ID to add the user to
   * @returns
   */
  async addToCollection(options: {
    id: string;
    collectionId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "POST",
      `users/${options.id}/collections/${options.collectionId}`,
    );
  }

  /**
   * Remove a user from a collection.
   * @param id User ID to remove
   * @param collectionId Collection ID to remove the user from
   * @returns
   */
  async removeFromCollection(options: {
    id: string;
    collectionId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `users/${options.id}/collections/${options.collectionId}`,
    );
  }

  /**
   * Export users as a CSV file with support for filtering and column selection.
   *
   * @param options Export configuration options
   * @param options.outputPath Path where the CSV file should be saved (Node.js only)
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which users are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments, Promise<void> in Node.js
   */
  async export(
    options: {
      outputPath?: string;
      columns?: string[];
      filters?: Record<string, any>;
      includeHeader?: boolean;
    } = {},
  ): Promise<Blob | void> {
    const data: Record<string, any> = {
      include_header: options.includeHeader ?? true,
    };

    if (options.columns) {
      data.columns = options.columns;
    }
    if (options.filters) {
      data.filters = options.filters;
    }

    const response = await this.client.makeRequest("POST", "users/export", {
      data,
      responseType: "arraybuffer",
      headers: { Accept: "text/csv" },
    });

    // Node environment
    if (options.outputPath && typeof process !== "undefined") {
      await fs.promises.writeFile(options.outputPath, Buffer.from(response));
      return;
    }

    // Browser
    return new Blob([response], { type: "text/csv" });
  }

  /**
   * Export users as a CSV file and save it to the user's device.
   * @param filename
   * @param options
   */
  async exportToFile(options: {
    filename: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    const blob = await this.export(options);
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    }
  }

  /**
   * Create a new API key for the specified user.
   * Only superusers or the user themselves may create an API key.
   * @param id ID of the user for whom to create an API key
   * @returns WrappedAPIKeyResponse
   */
  async createApiKey(options: {
    id: string;
    name?: string;
    description?: string;
  }): Promise<WrappedAPIKeyResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.description && { description: options.description }),
    };

    return this.client.makeRequest("POST", `users/${options.id}/api-keys`, {
      data,
    });
  }

  /**
   * List all API keys for the specified user.
   * Only superusers or the user themselves may list the API keys.
   * @param id ID of the user whose API keys to list
   * @returns WrappedAPIKeysResponse
   */
  async listApiKeys(options: { id: string }): Promise<WrappedAPIKeysResponse> {
    return this.client.makeRequest("GET", `users/${options.id}/api-keys`);
  }

  /**
   * Delete a specific API key for the specified user.
   * Only superusers or the user themselves may delete the API key.
   * @param id ID of the user
   * @param keyId ID of the API key to delete
   * @returns WrappedBooleanResponse
   */
  async deleteApiKey(options: {
    id: string;
    keyId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `users/${options.id}/api-keys/${options.keyId}`,
    );
  }

  async getLimits(options: { id: string }): Promise<WrappedLimitsResponse> {
    return this.client.makeRequest("GET", `users/${options.id}/limits`);
  }

  async oauthGoogleAuthorize(): Promise<{ redirect_url: string }> {
    return this.client.makeRequest("GET", "users/oauth/google/authorize");
  }

  async oauthGithubAuthorize(): Promise<{ redirect_url: string }> {
    return this.client.makeRequest("GET", "users/oauth/github/authorize");
  }

  async oauthGoogleCallback(options: {
    code: string;
    state: string;
  }): Promise<any> {
    return this.client.makeRequest("GET", "users/oauth/google/callback", {
      params: {
        code: options.code,
        state: options.state,
      },
    });
  }

  async oauthGithubCallback(options: {
    code: string;
    state: string;
  }): Promise<any> {
    return this.client.makeRequest("GET", "users/oauth/github/callback", {
      params: {
        code: options.code,
        state: options.state,
      },
    });
  }
}
