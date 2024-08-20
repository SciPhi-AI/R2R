package sdk

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
)

type LogConfig struct {
	Verbose   bool
	LogWriter io.Writer
}

type Client struct {
	BaseURL      string
	HTTPClient   *http.Client
	LogConfig    LogConfig
	logger       *log.Logger
	AccessToken  string
	RefreshToken string
	*Auth
	*Ingestion
	*Management
	*Restructure
	*Retrieval
}

func (c *Client) log(level string, format string, v ...interface{}) {
	if !c.LogConfig.Verbose {
		return
	}

	message := fmt.Sprintf(format, v...)
	c.logger.Printf("[%s] %s", level, message)
}

func NewClient(baseURL string, logConfig LogConfig) *Client {
	if logConfig.LogWriter == nil {
		logConfig.LogWriter = os.Stdout
	}

	c := &Client{
		BaseURL:    baseURL,
		HTTPClient: &http.Client{},
		LogConfig:  logConfig,
		logger:     log.New(logConfig.LogWriter, "", log.Ldate|log.Ltime),
	}
	c.Auth = &Auth{client: c}
	c.Ingestion = &Ingestion{client: c}
	c.Management = &Management{client: c}
	c.Restructure = &Restructure{client: c}
	c.Retrieval = &Retrieval{client: c}
	return c
}

func (c *Client) makeRequest(method, endpoint string, body io.Reader, contentType string) (interface{}, error) {
	c.log("INFO", "Making request: %s %s", method, endpoint)
	url := fmt.Sprintf("%s/%s", c.BaseURL, endpoint)

	req, err := http.NewRequest(method, url, body)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", contentType)

	if c.AccessToken != "" {
		req.Header.Set("Authorization", "Bearer "+c.AccessToken)
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		c.log("ERROR", "API request failed with status code: %d", resp.StatusCode)
		return nil, fmt.Errorf("API request failed with status code: %d", resp.StatusCode)
	}

	if strings.HasPrefix(resp.Header.Get("Content-Type"), "application/json") {
		var result interface{}
		err = json.NewDecoder(resp.Body).Decode(&result)
		if err != nil {
			return nil, err
		}
		return result, nil
	} else {
		// For streaming responses or non-JSON content
		return resp.Body, nil
	}
}

func (c *Client) SetAccessToken(token string) {
	c.AccessToken = token
}

func (c *Client) SetRefreshToken(token string) {
	c.RefreshToken = token
}

func (c *Client) ClearTokens() {
	c.AccessToken = ""
	c.RefreshToken = ""
}
