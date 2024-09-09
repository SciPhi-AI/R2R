package integration

import (
	"os"
	"testing"

	"github.com/yourusername/r2r_go_sdk/pkg/sdk"
)

func TestServerStatsIntegration(t *testing.T) {
	logConfig := sdk.LogConfig{
		Verbose:   true,
		LogWriter: os.Stderr, // or any io.Writer
	}

	client := sdk.NewClient("http://localhost:7272/v2", logConfig)

	// Call Health
	health, err := client.Health()
	if err != nil {
		t.Fatalf("Health returned an error: %v", err)
	}

	// Check if we received a response
	if health == nil {
		t.Fatalf("Health returned nil")
	}

	// Call ServerStats
	stats, err := client.ServerStats()
	if err != nil {
		t.Fatalf("ServerStats returned an error: %v", err)
	}

	// Check if we received a response
	if stats == nil {
		t.Fatalf("ServerStats returned nil")
	}

	// Print the received stats for debugging
	t.Logf("Received server stats: %+v", stats)

	// Check app settings
	settings, err := client.AppSettings()

	if err != nil {
		t.Fatalf("AppSettings returned an error: %v", err)
	}

	// Check if we received a response
	if settings == nil {
		t.Fatalf("AppSettings returned nil")
	}

}
