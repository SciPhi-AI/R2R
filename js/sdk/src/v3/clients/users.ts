import { r2rClient } from "../../r2rClient";
import {
  WrappedBooleanResponse,
  WrappedCollectionsResponse,
  WrappedGenericMessageResponse,
  WrappedTokenResponse,
  WrappedUserResponse,
  WrappedUsersResponse,
} from "../../types";

export class UsersClient {
  constructor(private client: r2rClient) {}

  /**
   * Register a new user.
   * @param email User's email address
   * @param password User's password
   * @returns
   */
  async register(options: {
    email: string;
    password: string;
  }): Promise<WrappedUserResponse> {
    return this.client.makeRequest("POST", "users/register", {
      data: options,
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
  async login(options: { email: string; password: string }): Promise<any> {
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
        response.results.access_token.token,
        response.results.refresh_token.token,
      );
    }

    return response;
  }

  /**
   * Log in using an existing access token.
   * @param accessToken Existing access token
   * @returns
   */
  // FIXME: What is going on here...
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
        response.results.access_token.token,
        response.results.refresh_token.token,
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

  /**
   * Request a password reset.
   * @param email User's email address
   * @returns
   */
  async requestPasswordReset(options: {
    email: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest("POST", "users/request-password-reset", {
      data: options,
    });
  }

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
   * @param email Email to filter by (partial match)
   * @param is_active Filter by active status
   * @param is_superuser Filter by superuser status
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async list(options?: {
    email?: string;
    is_active?: boolean;
    is_superuser?: boolean;
    offset?: number;
    limit?: number;
  }): Promise<WrappedUsersResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.email) {
      params.email = options.email;
    }
    if (options?.is_active) {
      params.is_active = options.is_active;
    }
    if (options?.is_superuser) {
      params.is_superuser = options.is_superuser;
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
    is_superuser?: boolean;
    name?: string;
    bio?: string;
    profilePicture?: string;
  }): Promise<WrappedUserResponse> {
    const data = {
      ...(options.email && { email: options.email }),
      ...(options.is_superuser && { is_superuser: options.is_superuser }),
      ...(options.name && { name: options.name }),
      ...(options.bio && { bio: options.bio }),
      ...(options.profilePicture && {
        profile_picture: options.profilePicture,
      }),
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
}
