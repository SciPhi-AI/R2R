package main

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/yourusername/r2r_go_sdk/pkg/sdk"
)

func init() {
	rootCmd.AddCommand(ragCmd)
}

func init() {
	// rootCmd.AddCommand(inspectKnowledgeGraphCmd)
	rootCmd.AddCommand(ragCmd)
	rootCmd.AddCommand(searchCmd)
}

var inspectKnowledgeGraphCmd = &cobra.Command{
	Use:   "inspect-knowledge-graph",
	Short: "Print relationships from the knowledge graph",
	Run: withTimer(func(cmd *cobra.Command, args []string) {
		client := sdk.NewClient("http://localhost:7272/v2", sdk.LogConfig{Verbose: true})
		limit, _ := cmd.Flags().GetInt("limit")
		// printDescriptions, _ := cmd.Flags().GetBool("print-descriptions")

		response, err := client.InspectKnowledgeGraph()
		if err != nil {
			fmt.Printf("Error inspecting knowledge graph: %v\n", err)
			return
		}
		fmt.Println(response)
	}),
}

var ragCmd = &cobra.Command{
	Use:   "rag",
	Short: "Perform a RAG query",
	Run: withTimer(func(cmd *cobra.Command, args []string) {
		client := sdk.NewClient("http://localhost:7272/v2", sdk.LogConfig{Verbose: true})
		query, _ := cmd.Flags().GetString("query")
		useVectorSearch, _ := cmd.Flags().GetBool("use-vector-search")
		filtersStr, _ := cmd.Flags().GetString("filters")
		var filters map[string]interface{}
		if filtersStr != "" {
			json.Unmarshal([]byte(filtersStr), &filters)
		}
		searchLimit, _ := cmd.Flags().GetInt("search-limit")
		doHybridSearch, _ := cmd.Flags().GetBool("use-hybrid-search")
		useKgSearch, _ := cmd.Flags().GetBool("use-kg-search")
		kgSearchModel, _ := cmd.Flags().GetString("kg-search-model")
		stream, _ := cmd.Flags().GetBool("stream")
		ragModel, _ := cmd.Flags().GetString("rag-model")
		kgSearchType, _ := cmd.Flags().GetString("kg-search-type")
		kgSearchLevel, _ := cmd.Flags().GetString("kg-search-level")

		generationConfig := sdk.GenerationConfig{
			Stream: stream,
		}
		if ragModel != "" {
			generationConfig.Model = ragModel
		}

		vectorSearchSettings := &sdk.VectorSearchSettings{
			UseVectorSearch: useVectorSearch,
			Filters:         filters,
			SearchLimit:     searchLimit,
			DoHybridSearch:  doHybridSearch,
		}

		kgSearchSettings := &sdk.KGSearchSettings{
			UseKGSearch: useKgSearch,
			Model:       kgSearchModel,
			SearchType:  kgSearchType,
			SearchLevel: kgSearchLevel,
		}

		response, err := client.RAG(query, generationConfig, vectorSearchSettings, kgSearchSettings)
		if err != nil {
			fmt.Printf("Error performing RAG query: %v\n", err)
			return
		}

		if stream {
			for chunk := range response.StreamingChannel {
				fmt.Print(chunk)
			}
			fmt.Println()
		} else {
			fmt.Printf("Search Results:\n%s\n", response.SearchResults)
			fmt.Printf("Completion:\n%s\n", response.Completion)
		}
	}),
}

var searchCmd = &cobra.Command{
	Use:   "search",
	Short: "Perform a search query",
	Run: withTimer(func(cmd *cobra.Command, args []string) {
		client := sdk.NewClient("http://localhost:7272/v2", sdk.LogConfig{Verbose: true})
		query, _ := cmd.Flags().GetString("query")
		useVectorSearch, _ := cmd.Flags().GetBool("use-vector-search")
		filtersStr, _ := cmd.Flags().GetString("filters")
		var filters map[string]interface{}
		if filtersStr != "" {
			json.Unmarshal([]byte(filtersStr), &filters)
		}
		searchLimit, _ := cmd.Flags().GetInt("search-limit")
		doHybridSearch, _ := cmd.Flags().GetBool("use-hybrid-search")
		useKgSearch, _ := cmd.Flags().GetBool("use-kg-search")
		kgSearchModel, _ := cmd.Flags().GetString("kg-search-model")
		kgSearchType, _ := cmd.Flags().GetString("kg-search-type")
		kgSearchLevel, _ := cmd.Flags().GetString("kg-search-level")

		vectorSearchSettings := &sdk.VectorSearchSettings{
			UseVectorSearch: useVectorSearch,
			Filters:         filters,
			SearchLimit:     searchLimit,
			DoHybridSearch:  doHybridSearch,
		}

		kgSearchSettings := &sdk.KGSearchSettings{
			UseKGSearch: useKgSearch,
			Model:       kgSearchModel,
			SearchType:  kgSearchType,
			SearchLevel: kgSearchLevel,
		}

		results, err := client.Search(query, vectorSearchSettings, kgSearchSettings)
		if err != nil {
			fmt.Printf("Error performing search: %v\n", err)
			return
		}

		fmt.Printf("KG_Search Enabled: %v\n", useKgSearch)
		fmt.Printf("KG_Search Type: %s\n", kgSearchType)

		if len(results.VectorSearchResults) > 0 {
			fmt.Println("Vector search results:")
			for _, result := range results.VectorSearchResults {
				fmt.Println(result)
			}
		}

		if len(results.KGSearchResults) > 0 {
			fmt.Println("KG search results:")
			for _, result := range results.KGSearchResults {
				fmt.Println(result)
			}
		}
	}),
}

func init() {
	inspectKnowledgeGraphCmd.Flags().Int("limit", 100, "Limit the number of relationships returned")
	inspectKnowledgeGraphCmd.Flags().Bool("print-descriptions", false, "Print descriptions of entities and relationships")

	ragCmd.Flags().String("query", "", "The query for RAG")
	ragCmd.Flags().Bool("use-vector-search", true, "Use vector search")
	ragCmd.Flags().String("filters", "", "Search filters as JSON")
	ragCmd.Flags().Int("search-limit", 10, "Number of search results to return")
	ragCmd.Flags().Bool("use-hybrid-search", false, "Perform hybrid search")
	ragCmd.Flags().Bool("use-kg-search", false, "Use knowledge graph search")
	ragCmd.Flags().String("kg-search-model", "", "Model for KG agent")
	ragCmd.Flags().Bool("stream", false, "Stream the RAG response")
	ragCmd.Flags().String("rag-model", "", "Model for RAG")
	ragCmd.Flags().String("kg-search-type", "global", "Local or Global")
	ragCmd.Flags().String("kg-search-level", "", "Level of cluster to use for Global KG search")

	searchCmd.Flags().String("query", "", "The search query")
	searchCmd.Flags().Bool("use-vector-search", true, "Use vector search")
	searchCmd.Flags().String("filters", "", "Search filters as JSON")
	searchCmd.Flags().Int("search-limit", 10, "Number of search results to return")
	searchCmd.Flags().Bool("use-hybrid-search", false, "Perform hybrid search")
	searchCmd.Flags().Bool("use-kg-search", false, "Use knowledge graph search")
	searchCmd.Flags().String("kg-search-model", "", "Model for KG agent")
	searchCmd.Flags().String("kg-search-type", "global", "Local or Global")
	searchCmd.Flags().String("kg-search-level", "", "Level of KG search")
}
