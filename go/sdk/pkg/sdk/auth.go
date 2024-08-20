package sdk

import (
	"bytes"
	"encoding/json"
	"fmt"
)

type Auth struct {
	client *Client
}

// Register registers a new user with the given email and password.
//
// Parameters:
//
//	email: The email of the user to register.
//	password: The passworrd of the user to register.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (a *Auth) Register(email string, password string) (map[string]interface{}, error) {
	data := map[string]interface{}{
		"email":    email,
		"password": password,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling register data: %w", err)
	}

	result, err := a.client.makeRequest("POST", "register", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// VerifyEmail verifies the email of a user with the given verification code.
//
// Parameters:
//
//	verificationCode: The verification code to verify the email with.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (a *Auth) VerifyEmail(verificationCode string) (map[string]interface{}, error) {
	data := map[string]string{
		"verification_code": verificationCode,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling verify email data: %w", err)
	}

	result, err := a.client.makeRequest("POST", "verify_email", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// Login attempts to log in a user with the given email and password.
//
// Parameters:
//
//	email: The email of the user to log in.
//	password: The password of the user to log in.
//
// Returns:
//
//	A map containing the access and refresh tokens from the server.
//	An error if the request fails, nil otherwise.
func (a *Auth) Login(email string, password string) (map[string]interface{}, error) {
	data := map[string]string{
		"username": email,
		"password": password,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling login data: %w", err)
	}

	result, err := a.client.makeRequest("POST", "login", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	response, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	if results, ok := response["results"].(map[string]interface{}); ok {
		if accessToken, ok := results["access_token"].(map[string]interface{}); ok {
			a.client.AccessToken = accessToken["token"].(string)
		}
		if refreshToken, ok := results["refresh_token"].(map[string]interface{}); ok {
			a.client.RefreshToken = refreshToken["token"].(string)
		}
	}

	return response, nil
}

// Logout logs out the currently authenticated user.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (a *Auth) Logout() (map[string]interface{}, error) {
	result, err := a.client.makeRequest("POST", "logout", nil, "application/json")
	if err != nil {
		return nil, err
	}

	response, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	a.client.AccessToken = ""
	a.client.RefreshToken = ""

	return response, nil
}

// User retreives the information of the currently authenticated user.
//
// Returns:
//
//	A map containing the user information.
func (a *Auth) User() (map[string]interface{}, error) {
	result, err := a.client.makeRequest("GET", "user", nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// UpdateUser updates the profile information for the currently authenticated user.
//
// Parameters:
//
//	email: The updated email for the user (optional).
//	name: The updated name for the user (optional).
//	bio: The updated bio for the user (optional).
//	profilePicture: The updated profile picture URL for the user (optional).
//
// Returns:
//
//	A map containing the updated user information.
//	An error if the request fails, nil otherwise.
func (a *Auth) UpdateUser(email, name, bio, profilePicture *string) (map[string]interface{}, error) {
	data := make(map[string]interface{})
	if email != nil {
		data["email"] = *email
	}
	if name != nil {
		data["name"] = *name
	}
	if bio != nil {
		data["bio"] = *bio
	}
	if profilePicture != nil {
		data["profile_picture"] = *profilePicture
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling update user data: %w", err)
	}

	result, err := a.client.makeRequest("PUT", "user", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	response, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return response, nil
}

// RefreshAccessToken refreshes the access token for the currently authenticated user.
//
// Returns:
//
//	A map containing the new access and refresh tokens.
//	An error if the request fails, nil otherwise.
func (a *Auth) RefreshAccessToken() (map[string]interface{}, error) {
	data := map[string]string{
		"refresh_token": a.client.RefreshToken,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling refresh token data: %w", err)
	}

	result, err := a.client.makeRequest("POST", "refresh_access_token", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	response, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	if results, ok := response["results"].(map[string]interface{}); ok {
		if accessToken, ok := results["access_token"].(map[string]interface{}); ok {
			a.client.AccessToken = accessToken["token"].(string)
		}
		if refreshToken, ok := results["refresh_token"].(map[string]interface{}); ok {
			a.client.RefreshToken = refreshToken["token"].(string)
		}
	}

	return response, nil
}

// ChangePassword changes the password of the currently authenticated user.
//
// Parameters:
//
//	currentPassword: The current password of the user.
//	newPassword: The new password to set for the user.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (a *Auth) ChangePassword(currentPassword string, newPassword string) (map[string]interface{}, error) {
	data := map[string]string{
		"current_password": currentPassword,
		"new_password":     newPassword,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling change password data: %w", err)
	}

	result, err := a.client.makeRequest("POST", "change_password", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// RequestPasswordReset requests a password reset for the user with the given email.
//
// Parameters:
//
//	email: The email of the user to request a password reset for.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (a *Auth) RequestPasswordReset(email string) (map[string]interface{}, error) {
	data := map[string]string{
		"email": email,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling request password reset data: %w", err)
	}

	result, err := a.client.makeRequest("POST", "request_password_reset", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// ConfirmPasswordReset confirms a password reset for the user with the given reset token.
//
// Parameters:
//
//	resetToken: The reset token to confirm the password reset with.
//	newPassword: The new password to set for the user.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (a *Auth) ConfirmPasswordReset(resetToken, newPassword string) (map[string]interface{}, error) {
	data := map[string]string{
		"reset_token":  resetToken,
		"new_password": newPassword,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling confirm password reset data: %w", err)
	}

	result, err := a.client.makeRequest("POST", "reset_password", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	response, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return response, nil
}

// DeleteUser deletes the user with the given user ID.
//
// Parameters:
//
//	userID: The ID of the user to delete.
//	password: The password of the user to delete (optional).
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (a *Auth) DeleteUser(userID string, password *string) (map[string]interface{}, error) {
	data := map[string]interface{}{
		"user_id": userID,
	}
	if password != nil {
		data["password"] = *password
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling delete user data: %w", err)
	}

	result, err := a.client.makeRequest("DELETE", "user", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	response, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	a.client.AccessToken = ""
	a.client.RefreshToken = ""

	return response, nil
}
