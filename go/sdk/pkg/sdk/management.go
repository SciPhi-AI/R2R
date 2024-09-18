package sdk

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/url"
	"strconv"
)

type Management struct {
	client *Client
}

// ServerStats gets statistics about the server, including the start time, uptime, CPU usage, and memory usage.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (m *Management) ServerStats() (map[string]interface{}, error) {
	result, err := m.client.makeRequest("GET", "server_stats", nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// UpdatePrompt updates a prompt in the database.
//
// Parameters:
//
//	name: The name of the prompt to update.
//	template: The new template for the prompt.
//	inputTypes: The new input types for the prompt.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (m *Management) UpdatePrompt(name string, template *string, inputTypes map[string]string) (map[string]interface{}, error) {
	data := map[string]interface{}{
		"name": name,
	}

	if template != nil {
		data["template"] = *template
	}
	if inputTypes != nil {
		data["input_types"] = inputTypes
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	result, err := m.client.makeRequest("POST", "update_prompt", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// Analytics gets analytics data from the server.
//
// Parameters:
//
//	filterCriteria: The filter criteria to use.
//	analysisTypes: The types of analysis to perform.
//
// Returns:
//
//	A map containing the analytics data from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) Analytics(filterCriteria, analysisTypes interface{}) (map[string]interface{}, error) {
	params := url.Values{}

	if filterCriteria != nil {
		switch fc := filterCriteria.(type) {
		case map[string]interface{}:
			jsonFC, err := json.Marshal(fc)
			if err != nil {
				return nil, fmt.Errorf("error marshaling filter criteria: %w", err)
			}
			params.Set("filter_criteria", string(jsonFC))
		case string:
			params.Set("filter_criteria", fc)
		default:
			return nil, fmt.Errorf("unsupported type for filter criteria: %T", filterCriteria)
		}
	}

	if analysisTypes != nil {
		switch at := analysisTypes.(type) {
		case map[string]interface{}:
			jsonAT, err := json.Marshal(at)
			if err != nil {
				return nil, fmt.Errorf("error marshaling analysis types: %w", err)
			}
			params.Set("analysis_types", string(jsonAT))
		case string:
			params.Set("analysis_types", at)
		default:
			return nil, fmt.Errorf("unsupported type for analysis types: %T", analysisTypes)
		}
	}

	endpoint := "analytics"
	if len(params) > 0 {
		endpoint += "?" + params.Encode()
	}

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	analytics, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return analytics, nil
}

// Logs gets logs from the server.
//
// Parameters:
//
//	runTypeFilter: The run type to filter by.
//	maxRuns: Specifies the maximum number of runs to return. Values outside the range of 1 to 1000 will be adjusted to the nearest valid value with a default of 100.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (m *Management) Logs(runTypeFilter *string, maxRuns *int) (map[string]interface{}, error) {
	params := make(map[string]interface{})

	if runTypeFilter != nil {
		params["run_type_filter"] = *runTypeFilter
	}

	if maxRuns != nil {
		params["max_runs"] = *maxRuns
	}

	values := url.Values{}
	for key, value := range params {
		values.Add(key, fmt.Sprintf("%v", value))
	}

	endpoint := fmt.Sprintf("logs?%s", values.Encode())

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// AppSettings gets the configuration settings for the app.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (m *Management) AppSettings() (map[string]interface{}, error) {
	result, err := m.client.makeRequest("GET", "app_settings", nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// ScoreCompletion assigns a score to a message from an LLM completion. The score should be a float between -1.0 and 1.0.
//
// Parameters:
//
//	messageID: The ID of the message to score.
//	score: The score to assign to the message.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (m *Management) ScoreCompletion(messageID string, score *float32) (map[string]interface{}, error) {
	data := map[string]interface{}{
		"message_id": messageID,
	}

	if score != nil {
		data["score"] = *score
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	result, err := m.client.makeRequest("POST", "score_completion", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// UsersOverview get an overview of the users in the R2R deployment.
//
// Parameters:
//
//	userIds: A list of user IDs to get an overview for.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (m *Management) UsersOverview(userIds []string) (map[string]interface{}, error) {
	values := url.Values{}

	if len(userIds) > 0 {
		for _, id := range userIds {
			values.Add("user_ids", id)
		}
	}

	endpoint := "users_overview"
	if len(values) > 0 {
		endpoint += "?" + values.Encode()
	}

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// Delete deletes data from the database given a set of filters.
//
// Parameters:
//
//	filters: A map of filters to delete by.
func (m *Management) Delete(filters map[string]string) (map[string]interface{}, error) {
	filtersJSON, err := json.Marshal(filters)
	if err != nil {
		return nil, fmt.Errorf("error marshaling filters: %w", err)
	}

	values := url.Values{}
	values.Add("filters", string(filtersJSON))

	endpoint := "delete?" + values.Encode()

	result, err := m.client.makeRequest("DELETE", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// DocumentsOverview gets an overview of documents in the R2R deployment.
//
// Parameters:
//
//	documentIDs: A list of document IDs to get an overview for.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (m *Management) DocumentsOverview(userIDs []string) (map[string]interface{}, error) {
	values := url.Values{}

	addIDsToValues := func(key string, ids []string) {
		for _, id := range ids {
			values.Add(key, id)
		}
	}

	if len(userIDs) > 0 {
		addIDsToValues("user_ids", userIDs)
	}

	endpoint := "documents_overview"
	if len(values) > 0 {
		endpoint += "?" + values.Encode()
	}

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil

}

// DocumentChunks gets the chunks for a document.
//
// Parameters:
//
//	documentID: The ID of the document to get chunks for.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) DocumentChunks(documentID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("document_chunks?document_id=%s", documentID)

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// InspectKnowledgeGraph inspects the knowledge graph associated with your R2R deployment.
//
// Parameters:
//
//	limit: The maximum number of nodes to return. Defaults to 100.
//
// Returns:
//
//	A map containing the response from the server.
func (m *Management) InspectKnowledgeGraph(limit *int) (map[string]interface{}, error) {
	values := url.Values{}

	if limit != nil {
		values.Set("limit", strconv.Itoa(*limit))
	}

	endpoint := "inspect_knowledge_graph"
	if len(values) > 0 {
		endpoint += "?" + values.Encode()
	}

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// GroupsOverview gets an overview of existing groups.
//
// Parameters:
//
//	groupIDs: A list of group IDs to get an overview for.
//	limit: The maximum number of groups to return.
//	offset: The offset to start at.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) GroupsOverview(groupIDs []string, limit, offset *int) (map[string]interface{}, error) {
	params := url.Values{}

	if len(groupIDs) > 0 {
		for _, id := range groupIDs {
			params.Add("collection_ids", id)
		}
	}
	if limit != nil {
		params.Set("limit", strconv.Itoa(*limit))
	}
	if offset != nil {
		params.Set("offset", strconv.Itoa(*offset))
	}

	endpoint := "collections_overview"
	if len(params) > 0 {
		endpoint += "?" + params.Encode()
	}

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// CreateGroup creates a new group.
//
// Parameters:
//
//	name: The name of the group to create.
//	description: The description of the group to create.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) CreateGroup(name string, description *string) (map[string]interface{}, error) {
	data := map[string]interface{}{
		"name": name,
	}
	if description != nil {
		data["description"] = *description
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling request data: %w", err)
	}

	result, err := m.client.makeRequest("POST", "create_collection", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// GetGroup gets a group by its ID.
//
// Parameters:
//
//	groupID: The ID of the group to get.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) GetGroup(groupID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("get_collection/%s", url.PathEscape(groupID))

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// UpdateGroup updates the name and description of a group.
//
// Parameters:
//
//	groupID: The ID of the group to update.
//	name: The new name for the group.
//	description: The new description for the group.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) UpdateGroup(groupID string, name, description *string) (map[string]interface{}, error) {
	data := map[string]interface{}{
		"collection_id": groupID,
	}
	if name != nil {
		data["name"] = *name
	}
	if description != nil {
		data["description"] = *description
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling request data: %w", err)
	}

	result, err := m.client.makeRequest("PUT", "update_collection", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// DeleteGroup deletes a group by its ID.
//
// Parameters:
//
//	groupID: The ID of the group to delete.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) DeleteGroup(groupID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("delete_collection/%s", url.PathEscape(groupID))

	result, err := m.client.makeRequest("DELETE", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// ListGroups lists all groups in the R2R deployment.
//
// Parameters:
//
//	offset: The offset to start at.
//	limit: The maximum number of groups to return.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) ListGroups(offset, limit *int) (map[string]interface{}, error) {
	params := url.Values{}
	if offset != nil {
		params.Set("offset", strconv.Itoa(*offset))
	}
	if limit != nil {
		params.Set("limit", strconv.Itoa(*limit))
	}

	endpoint := "list_collections"
	if len(params) > 0 {
		endpoint += "?" + params.Encode()
	}

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// AddUserToGroup adds a user to a group.
//
// Parameters:
//
//	userID: The ID of the user to add.
//	groupID: The ID of the group to add the user to.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) AddUserToGroup(userID, groupID string) (map[string]interface{}, error) {
	data := map[string]string{
		"user_id":  userID,
		"collection_id": groupID,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling request data: %w", err)
	}

	result, err := m.client.makeRequest("POST", "add_user_to_collection", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// RemoveUserFromGroup removes a user from a group.
//
// Parameters:
//
//	userID: The ID of the user to remove.
//	groupID: The ID of the group to remove the user from.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) RemoveUserFromGroup(userID, groupID string) (map[string]interface{}, error) {
	data := map[string]string{
		"user_id":  userID,
		"collection_id": groupID,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling request data: %w", err)
	}

	result, err := m.client.makeRequest("POST", "remove_user_from_collection", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// GetUsersInGroup gets all users in a group.
//
// Parameters:
//
//	groupID: The ID of the group to get users for.
//	offset: The offset to start at.
//	limit: The maximum number of users to return.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) GetUsersInGroup(groupID string, offset, limit *int) (map[string]interface{}, error) {
	params := url.Values{}

	if offset != nil {
		params.Set("offset", strconv.Itoa(*offset))
	}
	if limit != nil {
		params.Set("limit", strconv.Itoa(*limit))
	}

	endpoint := fmt.Sprintf("get_users_in_collection/%s", url.PathEscape(groupID))
	if len(params) > 0 {
		endpoint += "?" + params.Encode()
	}

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// GetGroupsForUser gets all groups a user is in.
//
// Parameters:
//
//	userID: The ID of the user to get groups for.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) GetGroupsForUser(userID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("get_collections_for_user/%s", url.PathEscape(userID))

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// AssignDocumentToGroup assigns a document to a group.
//
// Parameters:
//
//	documentID: The ID of the document to assign.
//	groupID: The ID of the group to assign the document to.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) AssignDocumentToGroup(documentID string, groupId string) (map[string]interface{}, error) {
	data := map[string]string{
		"document_id": documentID,
		"collection_id":    groupId,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	result, err := m.client.makeRequest("POST", "assign_document_to_collection", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// RemoveDocumentFromGroup removes a document from a group.
//
// Parameters:
//
//	documentID: The ID of the document to remove.
//	groupID: The ID of the group to remove the document from.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) RemoveDocumentFromGroup(documentID string, groupId string) (map[string]interface{}, error) {
	data := map[string]string{
		"document_id": documentID,
		"collection_id":    groupId,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	result, err := m.client.makeRequest("POST", "remove_document_from_collection", bytes.NewBuffer(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// GetDocumentGroups gets all groups that a document is assigned to.
//
// Parameters:
//
//	documentID: The ID of the document to get groups for.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) GetDocumentGroups(documentID string) (map[string]interface{}, error) {
	endpoint := fmt.Sprintf("get_document_collections/%s", url.PathEscape(documentID))

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// GetDocumentsInGroup gets all documents in a group.
//
// Parameters:
//
//	groupID: The ID of the group to get documents for.
//	offset: The offset to start listing documents from.
//	limit: The maximum number of documents to return.
//
// Returns:
//
//	A map containing the response from the server.
//	An error if the request fails, nil otherwise.
func (m *Management) GetDocumentsInGroup(groupID string, offset, limit *int) (map[string]interface{}, error) {
	params := url.Values{}

	if offset != nil {
		params.Set("offset", strconv.Itoa(*offset))
	}
	if limit != nil {
		params.Set("limit", strconv.Itoa(*limit))
	}

	endpoint := fmt.Sprintf("group/%s/documents", url.PathEscape(groupID))
	if len(params) > 0 {
		endpoint += "?" + params.Encode()
	}

	result, err := m.client.makeRequest("GET", endpoint, nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

func (m *Management) Health() (map[string]interface{}, error) {
	result, err := m.client.makeRequest("GET", "health", nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}
