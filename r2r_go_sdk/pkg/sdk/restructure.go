package sdk

import "fmt"

type Restructure struct {
	client *Client
}

func (rs *Restructure) EnrichGraph() (map[string]interface{}, error) {

	result, err := rs.client.makeRequest("POST", "enrich_graph", nil, "application/json")
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}
