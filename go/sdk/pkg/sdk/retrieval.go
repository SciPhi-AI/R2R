package sdk

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
)

type Retrieval struct {
	client *Client
}

type VectorSearchResult struct {
	FragmentID   string                 `json:"fragment_id"`
	ExtractionID string                 `json:"extraction_id"`
	DocumentID   string                 `json:"document_id"`
	UserID       string                 `json:"user_id"`
	GroupIDs     []string               `json:"collection_ids"`
	Score        float64                `json:"score"`
	Text         string                 `json:"text"`
	Metadata     map[string]interface{} `json:"metadata"`
}

type KGSearchResult [][]interface{}

type SearchResponse struct {
	VectorSearchResults []VectorSearchResult `json:"vector_search_results"`
	KGSearchResults     *KGSearchResult      `json:"kg_search_results,omitempty"`
}

type RAGResponse struct {
	Completion    map[string]interface{} `json:"completion"`
	SearchResults SearchResponse         `json:"search_results"`
}

type VectorSearchSettings struct {
	UseVectorSearch  bool                   `json:"use_vector_search"`
	Filters          map[string]interface{} `json:"filters"`
	SearchLimit      int                    `json:"search_limit"`
	DoHybridSearch   bool                   `json:"use_hybrid_search"`
	SelectedGroupIDs []string               `json:"selected_collection_ids"`
}

type KGSearchSettings struct {
	UseKGSearch                   bool              `json:"use_kg_search"`
	KGSearchType                  string            `json:"kg_search_type"`
	KGSearchLevel                 *int              `json:"kg_search_level,omitempty"`
	KGSearchGenerationConfig      *GenerationConfig `json:"kg_search_generation_config,omitempty"`
	EntityTypes                   []string          `json:"entity_types"`
	Relationships                 []string          `json:"relationships"`
	MaxCommunityDescriptionLength int               `json:"max_community_description_length"`
	MaxLLMQueriesForGlobalSearch  int               `json:"max_llm_queries_for_global_search"`
	LocalSearchLimits             map[string]int    `json:"local_search_limits"`
}

type GenerationConfig struct {
	Model               string                    `json:"model"`
	Temperature         float64                   `json:"temperature"`
	TopP                float64                   `json:"top_p"`
	MaxTokensToSample   int                       `json:"max_tokens_to_sample"`
	Stream              bool                      `json:"stream"`
	Functions           *[]map[string]interface{} `json:"functions,omitempty"`
	Tools               *[]map[string]interface{} `json:"tools,omitempty"`
	AddGenerationKwargs *map[string]interface{}   `json:"add_generation_kwargs,omitempty"`
	APIBase             *string                   `json:"api_base,omitempty"`
}

type Message struct {
	Role         string                    `json:"role"`
	Content      *string                   `json:"content,omitempty"`
	Name         *string                   `json:"name,omitempty"`
	FunctionCall *map[string]interface{}   `json:"function_call,omitempty"`
	ToolCalls    *[]map[string]interface{} `json:"tool_calls,omitempty"`
}

// Search conducts a vector and/or KG search.
//
// Parameters:
//
//	query: The query to search for.
//	vectorSearchSettings: Vector search settings.
//	kgSearchSettings: KG search settings.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (r *Retrieval) Search(query string, vectorSearchSettings *VectorSearchSettings, kgSearchSettings *KGSearchSettings) (*SearchResponse, error) {
	data := map[string]interface{}{
		"query": query,
	}

	if vectorSearchSettings != nil {
		data["vector_search_settings"] = vectorSearchSettings
	}
	if kgSearchSettings != nil {
		data["kg_search_settings"] = kgSearchSettings
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling search data: %w", err)
	}

	result, err := r.client.makeRequest("POST", "search", bytes.NewReader(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	var searchResponse SearchResponse
	resultJSON, err := json.Marshal(result)
	if err != nil {
		return nil, fmt.Errorf("error marshaling result to JSON: %w", err)
	}
	if err := json.Unmarshal(resultJSON, &searchResponse); err != nil {
		return nil, fmt.Errorf("error unmarshaling search response: %w", err)
	}

	return &searchResponse, nil
}

// RAG conducts a Retrieval Augmented Generation (RAG) search with the given query.
//
// Parameters:
//
//	query: The query to search for.
//	ragGenerationConfig: RAG generation configuration.
//	vectorSearchSettings: Vector search settings.
//	kgSearchSettings: KG search settings.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (r *Retrieval) RAG(query string, ragGenerationConfig GenerationConfig, vectorSearchSettings *VectorSearchSettings, kgSearchSettings *KGSearchSettings) (*RAGResponse, error) {
	data := map[string]interface{}{
		"query":                 query,
		"rag_generation_config": ragGenerationConfig,
	}

	if vectorSearchSettings != nil {
		data["vector_search_settings"] = vectorSearchSettings
	}
	if kgSearchSettings != nil {
		data["kg_search_settings"] = kgSearchSettings
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling RAG data: %w", err)
	}

	if ragGenerationConfig.Stream {
		return nil, fmt.Errorf("use RAGStream for streaming responses")
	}

	result, err := r.client.makeRequest("POST", "rag", bytes.NewReader(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	var ragResponse RAGResponse
	resultJSON, err := json.Marshal(result)
	if err != nil {
		return nil, fmt.Errorf("error marshaling result to JSON: %w", err)
	}
	if err := json.Unmarshal(resultJSON, &ragResponse); err != nil {
		return nil, fmt.Errorf("error unmarshaling RAG response: %w", err)
	}

	return &ragResponse, nil
}

// RAGStream conducts a streaming Retrieval Augmented Generation (RAG) search with the given query.
func (r *Retrieval) RAGStream(query string, ragGenerationConfig GenerationConfig, vectorSearchSettings *VectorSearchSettings, kgSearchSettings *KGSearchSettings) (<-chan RAGResponse, <-chan error) {
	responseChan := make(chan RAGResponse)
	errChan := make(chan error, 1)

	go func() {
		defer close(responseChan)
		defer close(errChan)

		data := map[string]interface{}{
			"query":                 query,
			"rag_generation_config": ragGenerationConfig,
		}

		if vectorSearchSettings != nil {
			data["vector_search_settings"] = vectorSearchSettings
		}
		if kgSearchSettings != nil {
			data["kg_search_settings"] = kgSearchSettings
		}

		jsonData, err := json.Marshal(data)
		if err != nil {
			errChan <- fmt.Errorf("error marshaling RAG data: %w", err)
			return
		}

		result, err := r.client.makeRequest("POST", "rag", bytes.NewReader(jsonData), "application/json")
		if err != nil {
			errChan <- err
			return
		}

		reader, ok := result.(io.Reader)
		if !ok {
			errChan <- fmt.Errorf("unexpected response type")
			return
		}

		scanner := bufio.NewScanner(reader)
		for scanner.Scan() {
			var ragResponse RAGResponse
			if err := json.Unmarshal(scanner.Bytes(), &ragResponse); err != nil {
				errChan <- fmt.Errorf("error unmarshaling RAG response: %w", err)
				return
			}
			responseChan <- ragResponse
		}
		if err := scanner.Err(); err != nil {
			errChan <- fmt.Errorf("error reading stream: %w", err)
		}
	}()

	return responseChan, errChan
}

// Agent performs a single turn in a conversation with a RAG agent.
//
// Parameters:
//
//	messages: The messages exchanged in the conversation so far.
//	ragGenerationConfig: RAG generation configuration.
//	vectorSearchSettings: Vector search settings.
//	kgSearchSettings: KG search settings.
//	taskPromptOverride: Task prompt override.
//	includeTitleIfAvailable: Include title if available.
//
// Returns:
//
//	    A list of messages exchanged in the conversation.
//		 An error if the request fails, nil otherwise.
func (r *Retrieval) Agent(messages []Message, ragGenerationConfig GenerationConfig, vectorSearchSettings *VectorSearchSettings, kgSearchSettings *KGSearchSettings, taskPromptOverride *string, includeTitleIfAvailable *bool) ([]Message, error) {
	data := map[string]interface{}{
		"messages":              messages,
		"rag_generation_config": ragGenerationConfig,
	}

	if vectorSearchSettings != nil {
		data["vector_search_settings"] = vectorSearchSettings
	}
	if kgSearchSettings != nil {
		data["kg_search_settings"] = kgSearchSettings
	}
	if taskPromptOverride != nil {
		data["task_prompt_override"] = *taskPromptOverride
	}
	if includeTitleIfAvailable != nil {
		data["include_title_if_available"] = *includeTitleIfAvailable
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return nil, fmt.Errorf("error marshaling Agent data: %w", err)
	}

	if ragGenerationConfig.Stream {
		return nil, fmt.Errorf("use AgentStream for streaming responses")
	}

	result, err := r.client.makeRequest("POST", "agent", bytes.NewReader(jsonData), "application/json")
	if err != nil {
		return nil, err
	}

	var agentResponse []Message
	resultJSON, err := json.Marshal(result)
	if err != nil {
		return nil, fmt.Errorf("error marshaling result to JSON: %w", err)
	}
	if err := json.Unmarshal(resultJSON, &agentResponse); err != nil {
		return nil, fmt.Errorf("error unmarshaling Agent response: %w", err)
	}

	return agentResponse, nil
}

// AgentStream performs a streaming conversation turn with a RAG agent.
func (r *Retrieval) AgentStream(messages []Message, ragGenerationConfig GenerationConfig, vectorSearchSettings *VectorSearchSettings, kgSearchSettings *KGSearchSettings, taskPromptOverride *string, includeTitleIfAvailable *bool) (<-chan Message, <-chan error) {
	responseChan := make(chan Message)
	errChan := make(chan error, 1)

	go func() {
		defer close(responseChan)
		defer close(errChan)

		data := map[string]interface{}{
			"messages":              messages,
			"rag_generation_config": ragGenerationConfig,
		}

		if vectorSearchSettings != nil {
			data["vector_search_settings"] = vectorSearchSettings
		}
		if kgSearchSettings != nil {
			data["kg_search_settings"] = kgSearchSettings
		}
		if taskPromptOverride != nil {
			data["task_prompt_override"] = *taskPromptOverride
		}
		if includeTitleIfAvailable != nil {
			data["include_title_if_available"] = *includeTitleIfAvailable
		}

		jsonData, err := json.Marshal(data)
		if err != nil {
			errChan <- fmt.Errorf("error marshaling Agent data: %w", err)
			return
		}

		result, err := r.client.makeRequest("POST", "agent", bytes.NewReader(jsonData), "application/json")
		if err != nil {
			errChan <- err
			return
		}

		reader, ok := result.(io.Reader)
		if !ok {
			errChan <- fmt.Errorf("unexpected response type")
			return
		}

		scanner := bufio.NewScanner(reader)
		for scanner.Scan() {
			var message Message
			if err := json.Unmarshal(scanner.Bytes(), &message); err != nil {
				errChan <- fmt.Errorf("error unmarshaling Agent response: %w", err)
				return
			}
			responseChan <- message
		}
		if err := scanner.Err(); err != nil {
			errChan <- fmt.Errorf("error reading stream: %w", err)
		}
	}()

	return responseChan, errChan
}
