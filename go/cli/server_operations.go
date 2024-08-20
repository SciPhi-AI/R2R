package main

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"runtime"
	"runtime/debug"

	"github.com/spf13/cobra"
	"github.com/yourusername/r2r_go_sdk/pkg/sdk"
)

func init() {
	rootCmd.AddCommand(dockerDownCmd)
	rootCmd.AddCommand(healthCmd)
	rootCmd.AddCommand(generateReportCmd)

	dockerDownCmd.Flags().Bool("volumes", false, "Remove named volumes")
	dockerDownCmd.Flags().Bool("remove-orphans", false, "Remove containers for services not defined in the Compose file")
	dockerDownCmd.Flags().String("project-name", "r2r", "Project name for Docker")
}

// TODO: Implement the actual Docker Compose down logic
var dockerDownCmd = &cobra.Command{
	Use:   "docker-down",
	Short: "Bring down the Docker Compose setup",
	Run: func(cmd *cobra.Command, args []string) {
		volumes, _ := cmd.Flags().GetBool("volumes")
		removeOrphans, _ := cmd.Flags().GetBool("remove-orphans")
		projectName, _ := cmd.Flags().GetString("project-name")

		fmt.Printf("Bringing down Docker Compose setup (Project: %s, Volumes: %v, Remove Orphans: %v)\n", projectName, volumes, removeOrphans)
	},
}

// TODO: Implement the actual system report generation logic
var generateReportCmd = &cobra.Command{
	Use:   "generate-report",
	Short: "Generate a system report",
	Run: func(cmd *cobra.Command, args []string) {
		report := make(map[string]interface{})

		// Get R2R version
		// TODO: Implement the actual version retrieval logic
		report["r2r_version"] = "1.0.0"

		// Get Docker info
		dockerVerison, _ := exec.Command("docker", "--version").Output()
		report["docker_version"] = string(dockerVerison)

		dockerPs, _ := exec.Command("docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}").Output()
		report["docker_info"] = string(dockerPs)

		dockerNetworks, _ := exec.Command("docker", "network", "ls", "--format", "{{.ID}}\t{{.Name}}\t{{.Driver}}").Output()
		report["docker_networks"] = string(dockerNetworks)

		dockerSubnets, _ := exec.Command("docker", "network", "inspect", "bridge", "--format", "{{.IPAM.Config}}").Output()
		report["docker_subnets"] = string(dockerSubnets)

		// Get OS information
		report["os_info"] = map[string]string{
			"system":    runtime.GOOS,
			"version":   runtime.Version(),
			"machine":   runtime.GOARCH,
			"processor": runtime.GOARCH,
		}

		jsonReport, _ := json.MarshalIndent(report, "", "  ")
		fmt.Println(string(jsonReport))
	},
}

var healthCmd = &cobra.Command{
	Use:   "health",
	Short: "Check the health of the server",
	Run: withTimer(func(cmd *cobra.Command, args []string) {
		client := sdk.NewClient("http://localhost:8000/v1", sdk.LogConfig{Verbose: true})
		response, err := client.Health()
		if err != nil {
			fmt.Printf("Error checking health: %v\n", err)
			return
		}
		fmt.Println(response)
	}),
}

// TODO: r2r serve command

// TODO: update

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print the version of R2R",
	Run: func(cmd *cobra.Command, args []string) {
		info, ok := debug.ReadBuildInfo()
		if !ok {
			fmt.Println("No version information available")
			return
		}

		for _, dep := range info.Deps {
			if dep.Path == "github.com/yourusername/r2r_go_sdk" {
				fmt.Printf("R2R version: %s\n", dep.Version)
				return
			}
		}

		fmt.Println("R2R version information not found")
	},
}
