package sdk

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"os"
	"path/filepath"
)

type Ingestion struct {
	client *Client
}

// IngestFiles ingests files into your R2R deployment.
//
// Parameters:
//
//	filePaths: List of file paths to ingest.
//	metadatas: List of metadata dictionaries for each file.
//	documentIDs: List of document IDs.
//	versions: List of version strings for each file.
//	chunkingConfigOverride: Custom chunking configuration.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (i *Ingestion) IngestFiles(
	filePaths []string,
	metadatas []map[string]interface{},
	documentIDs []string,
	versions []string,
	chunkingConfigOverride map[string]interface{},
) (map[string]interface{}, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	for _, path := range filePaths {
		file, err := os.Open(path)
		if err != nil {
			return nil, fmt.Errorf("error opening file %s: %w", path, err)
		}
		defer file.Close()

		part, err := writer.CreateFormFile("files", filepath.Base(path))
		if err != nil {
			return nil, fmt.Errorf("error creating form file: %w", err)
		}
		_, err = io.Copy(part, file)
		if err != nil {
			return nil, fmt.Errorf("error copying file content: %w", err)
		}
	}

	if metadatas != nil {
		metadatasJSON, err := json.Marshal(metadatas)
		if err != nil {
			return nil, fmt.Errorf("error marshaling metadatas: %w", err)
		}
		writer.WriteField("metadatas", string(metadatasJSON))
	}

	if documentIDs != nil {
		documentIDsJSON, err := json.Marshal(documentIDs)
		if err != nil {
			return nil, fmt.Errorf("error marshaling document IDs: %w", err)
		}
		writer.WriteField("document_ids", string(documentIDsJSON))
	}

	if versions != nil {
		versionsJSON, err := json.Marshal(versions)
		if err != nil {
			return nil, fmt.Errorf("error marshaling versions: %w", err)
		}
		writer.WriteField("versions", string(versionsJSON))
	}

	if chunkingConfigOverride != nil {
		chunkingConfigJSON, err := json.Marshal(chunkingConfigOverride)
		if err != nil {
			return nil, fmt.Errorf("error marshaling chunking config: %w", err)
		}
		writer.WriteField("chunking_settings", string(chunkingConfigJSON))
	}

	err := writer.Close()
	if err != nil {
		return nil, fmt.Errorf("error closing multipart writer: %w", err)
	}

	result, err := i.client.makeRequest("POST", "ingest_files", body, writer.FormDataContentType())
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}

// UpdateFiles updates existing files in your R2R deployment.
//
// Parameters:
//
//	filePaths: List of file paths to update.
//	documentIDs: List of document IDs.
//	metadatas: List of metadata dictionaries for each file.
//	chunkingConfigOverride: Custom chunking configuration.
//
// Returns:
//
//	    A map containing the response from the server.
//		 An error if the request fails, nil otherwise.
func (i *Ingestion) UpdateFiles(
	filePaths []string,
	documentIDs []string,
	metadatas []map[string]interface{},
	chunkingConfigOverride map[string]interface{},
) (map[string]interface{}, error) {
	if len(filePaths) != len(documentIDs) {
		return nil, fmt.Errorf("number of file paths must match number of document IDs")
	}

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	for _, path := range filePaths {
		file, err := os.Open(path)
		if err != nil {
			return nil, fmt.Errorf("error opening file %s: %w", path, err)
		}
		defer file.Close()

		part, err := writer.CreateFormFile("files", filepath.Base(path))
		if err != nil {
			return nil, fmt.Errorf("error creating form file: %w", err)
		}
		_, err = io.Copy(part, file)
		if err != nil {
			return nil, fmt.Errorf("error copying file content: %w", err)
		}
	}

	documentIDsJSON, err := json.Marshal(documentIDs)
	if err != nil {
		return nil, fmt.Errorf("error marshaling document IDs: %w", err)
	}
	writer.WriteField("document_ids", string(documentIDsJSON))

	if metadatas != nil {
		metadatasJSON, err := json.Marshal(metadatas)
		if err != nil {
			return nil, fmt.Errorf("error marshaling metadatas: %w", err)
		}
		writer.WriteField("metadatas", string(metadatasJSON))
	}

	if chunkingConfigOverride != nil {
		chunkingConfigJSON, err := json.Marshal(chunkingConfigOverride)
		if err != nil {
			return nil, fmt.Errorf("error marshaling chunking config: %w", err)
		}
		writer.WriteField("chunking_settings", string(chunkingConfigJSON))
	}

	err = writer.Close()
	if err != nil {
		return nil, fmt.Errorf("error closing multipart writer: %w", err)
	}

	result, err := i.client.makeRequest("POST", "update_files", body, writer.FormDataContentType())
	if err != nil {
		return nil, err
	}

	stats, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: expected map[string]interface{}, got %T", result)
	}

	return stats, nil
}
