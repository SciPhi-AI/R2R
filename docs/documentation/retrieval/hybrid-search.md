## Introduction

R2R's hybrid search blends keyword-based full-text search with semantic vector search, delivering results that are both contextually relevant and precise. By unifying these approaches, hybrid search excels at handling complex queries where both exact terms and overall meaning matter.

## How R2R Hybrid Search Works

<Steps>
  ### Full-Text Search
    Leverages Postgres's `ts_rank_cd` and `websearch_to_tsquery` to find documents containing your keywords.

  ### Semantic Search
    Uses vector embeddings to locate documents contextually related to your query, even if they don't share exact keywords.

  ### Reciprocal Rank Fusion (RRF)
    Merges results from both full-text and semantic searches using a formula like:

   $$\text{COALESCE}\left(\frac{1.0}{\text{rrf\_k} + \text{full\_text.rank\_ix}}, 0.0\right) \cdot \text{full\_text\_weight} + \text{COALESCE}\left(\frac{1.0}{\text{rrf\_k} + \text{semantic.rank\_ix}}, 0.0\right) \cdot \text{semantic\_weight}$$

   This ensures that documents relevant both semantically and by keyword ranking float to the top.

  ### Result Ranking
   Orders the final set of results based on the combined RRF score, providing balanced, meaningful search outcomes.
</Steps>

## Key Features
<Tabs>
  <Tab title="Full-Text Search">
    - Uses Postgres indexing and querying for quick, exact term matches.
    - Great for retrieving documents where specific terminology is critical.
  </Tab>
  <Tab title="Semantic Search">
    - Embeds queries and documents into vector representations.
    - Finds documents related to the query's meaning, not just its wording.
  </Tab>
  <Tab title="Hybrid Integration">
    - By enabling both `use_fulltext_search` and `use_semantic_search`, or choosing the `advanced` mode, you get the best of both worlds.
    - RRF blends these results, ensuring that documents align with the query's intent and exact terms where needed.
  </Tab>
</Tabs>

## Understanding Search Modes

R2R supports multiple search modes that can simplify or customize the configuration for you:

- **`basic`**: Primarily semantic search. Suitable for straightforward scenarios where semantic understanding is key, but you don't need the additional context of keyword matching.
- **`advanced`**: Combines semantic and full-text search by default, effectively enabling hybrid search with well-tuned default parameters. Ideal if you want the benefits of hybrid search without manual configuration.
- **`custom`**: Allows you full control over the search settings, including toggling semantic and full-text search independently. Choose this if you want to fine-tune weights, limits, and other search behaviors.

When using `advanced` mode, R2R automatically configures hybrid search for you. For `custom` mode, you can directly set `use_hybrid_search=True` or enable both `use_semantic_search` and `use_fulltext_search` to achieve a hybrid search setup.

## Configuration

**Choosing a Search Mode:**

- `basic`: Semantic-only.
  ```python
  search_mode = "basic"
  # Semantic search only, no full-text matching
  ```

- `advanced`: Hybrid by default.
  ```python
  search_mode = "advanced"
  # Hybrid search is automatically enabled with well-tuned defaults
  ```

- `custom`: Manually configure hybrid search.
  ```python
  search_mode = "custom"
  # Enable both semantic and full-text search and set weights as needed:
  search_settings = {
    "use_semantic_search": True,
    "use_fulltext_search": True,
    "use_hybrid_search": True,
    "hybrid_settings": {
      "full_text_weight": 1.0,
      "semantic_weight": 5.0,
      "full_text_limit": 200,
      "rrf_k": 50
    }
  }
  ```

For more details on runtime configuration and combining `search_mode` with custom `search_settings`, refer to the Search API documentation.

## Best Practices

1. **Optimize Database and Embeddings**:
   Ensure Postgres indexing and vector store configurations are optimal for performance.

2. **Adjust Weights and Limits**:
   Tweak `full_text_weight`, `semantic_weight`, and `rrf_k` values when using `custom` mode. If you're using `advanced` mode, the defaults are already tuned for general use cases.

3. **Regular Updates**:
   Keep embeddings and indexes up-to-date to maintain search quality.

4. **Choose Appropriate Embeddings**:
   Select an embedding model that fits your content domain for the best semantic results.

## Conclusion

R2R's hybrid search delivers robust, context-aware retrieval by merging semantic and keyword-driven approaches. Whether you pick `basic` mode for simplicity, `advanced` mode for out-of-the-box hybrid search, or `custom` mode for granular control, R2R ensures you can tailor the search experience to your unique needs.
