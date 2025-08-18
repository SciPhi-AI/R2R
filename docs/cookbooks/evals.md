This guide demonstrates how to evaluate your R2R RAG outputs using the Ragas evaluation framework.

In this tutorial, you will:

- Prepare a sample dataset in R2R
- Use R2R's `/rag` endpoint to perform Retrieval-Augmented Generation
- Install and configure Ragas for evaluation
- Evaluate the generated responses using multiple metrics
- Analyze evaluation traces for deeper insights

## Setting Up Ragas for R2R Evaluation

### Installing Ragas
First, install Ragas and its dependencies:

```python
%pip install ragas langchain-openai -q
```

### Configuring Ragas with OpenAI
Ragas uses an LLM to perform evaluations. Set up an OpenAI model as the evaluator:

```python
from langchain_openai import ChatOpenAI
from ragas.llms import LangchainLLMWrapper

# Make sure your OPENAI_API_KEY environment variable is set
llm = ChatOpenAI(model="gpt-4o-mini")
evaluator_llm = LangchainLLMWrapper(llm)

# If you'll be using embeddings for certain metrics
from langchain_openai import OpenAIEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper
evaluator_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings())
```

## Sample Dataset and R2R RAG Implementation

For this guide, we assume you have:
1. An initialized R2R client
2. A dataset about AI companies already ingested into R2R
3. Basic knowledge of R2R's RAG capabilities

Here's a quick example of using R2R's `/rag` endpoint to generate an answer:

```python
from r2r import R2RClient

client = R2RClient()  # Assuming R2R_API_KEY is set in your environment

query = "What makes Meta AI's LLaMA models stand out?"

search_settings = {
    "limit": 2,
    "graph_settings": {"enabled": False, "limit": 2},
}

response = client.retrieval.rag(
    query=query,
    search_settings=search_settings
)

print(response.results.generated_answer)
```

The output might look like:
```
Meta AI's LLaMA models stand out due to their open-source nature, which supports innovation and experimentation by making high-quality models accessible to researchers and developers [1]. This approach democratizes AI development, fostering collaboration across industries and enabling researchers without access to expensive resources to work with advanced AI models [2].
```

## Evaluating R2R with Ragas

Ragas provides a comprehensive evaluation framework specifically designed for RAG systems. The R2R-Ragas integration makes it easy to assess the quality of your R2R implementation.

### Creating a Test Dataset

First, prepare a set of test questions and reference answers:

```python
questions = [
    "Who are the major players in the large language model space?",
    "What is Microsoft's Azure AI platform known for?",
    "What kind of models does Cohere provide?",
]

references = [
    "The major players include OpenAI (GPT Series), Anthropic (Claude Series), Google DeepMind (Gemini Models), Meta AI (LLaMA Series), Microsoft Azure AI (integrating GPT Models), Amazon AWS (Bedrock with Claude and Jurassic), Cohere (business-focused models), and AI21 Labs (Jurassic Series).",
    "Microsoft's Azure AI platform is known for integrating OpenAI's GPT models, enabling businesses to use these models in a scalable and secure cloud environment.",
    "Cohere provides language models tailored for business use, excelling in tasks like search, summarization, and customer support.",
]
```

### Collecting R2R Responses

Generate responses using your R2R implementation:

```python
r2r_responses = []

search_settings = {
    "limit": 2,
    "graph_settings": {"enabled": False, "limit": 2},
}

for que in questions:
    response = client.retrieval.rag(query=que, search_settings=search_settings)
    r2r_responses.append(response)
```

### The R2R-Ragas Integration

Ragas includes a dedicated integration for R2R that handles the conversion of R2R's response format to Ragas's evaluation dataset format:

```python
from ragas.integrations.r2r import transform_to_ragas_dataset

# Convert R2R responses to Ragas format
ragas_eval_dataset = transform_to_ragas_dataset(
    user_inputs=questions,
    r2r_responses=r2r_responses,
    references=references
)

print(ragas_eval_dataset)
# Output: EvaluationDataset(features=['user_input', 'retrieved_contexts', 'response', 'reference'], len=3)
```

The `transform_to_ragas_dataset` function extracts the necessary components from R2R responses, including:
- The generated answer
- The retrieved context chunks
- Citation information

### Key Evaluation Metrics for R2R

Ragas offers several metrics that are particularly useful for evaluating R2R implementations:

```python
from ragas.metrics import AnswerRelevancy, ContextPrecision, Faithfulness
from ragas import evaluate

# Define the metrics to use
ragas_metrics = [
    AnswerRelevancy(llm=evaluator_llm),  # How relevant is the answer to the query?
    ContextPrecision(llm=evaluator_llm),  # How precisely were the right documents retrieved?
    Faithfulness(llm=evaluator_llm)       # Does the answer stick to facts in the context?
]

# Run the evaluation
results = evaluate(dataset=ragas_eval_dataset, metrics=ragas_metrics)
```

Each metric provides valuable insights:

- **Answer Relevancy**: Measures how well the R2R-generated response addresses the user's query
- **Context Precision**: Evaluates if R2R's retrieval mechanism is bringing back the most relevant documents
- **Faithfulness**: Checks if R2R's generated answers accurately reflect the information in the retrieved documents

### Interpreting Evaluation Results

The evaluation results show detailed scores for each sample and metric:

```python
# View results as a dataframe
df = results.to_pandas()
print(df)
```

Example output:
```
   user_input                                    retrieved_contexts                                           response                                          reference  answer_relevancy  context_precision  faithfulness
0  Who are the major players...                  [In the rapidly advancing field of...]                      The major players in the large language...         The major players include OpenAI...         1.000000              1.0     1.000000
1  What is Microsoft's Azure AI...              [Microsoft's Azure AI platform is famous for...]            Microsoft's Azure AI platform is known for...      Microsoft's Azure AI platform is...         0.948908              1.0     0.833333
2  What kind of models does Cohere provide?     [Cohere is well-known for its language models...]          Cohere provides language models tailored for...    Cohere provides language models...         0.903765              1.0     1.000000
```

### Advanced Visualization with Ragas App

For a more interactive analysis, upload results to the Ragas app:

```python
# Make sure RAGAS_APP_TOKEN is set in your environment
results.upload()
```

This generates a shareable dashboard with:
- Detailed scores per metric and sample
- Visual comparisons across metrics
- Trace information showing why scores were assigned
- Suggestions for improvement

You can examine:
- Which queries R2R handled well
- Where retrieval or generation could be improved
- Patterns in your RAG system's performance

## Advanced Evaluation Features

### Non-LLM Metrics for Fast Evaluation

In addition to LLM-based metrics, you can use non-LLM metrics for faster evaluations:

```python
from ragas.metrics import BleuScore

# Create a BLEU score metric
bleu_metric = BleuScore()

# Add it to your evaluation
quick_metrics = [bleu_metric]
quick_results = evaluate(dataset=ragas_eval_dataset, metrics=quick_metrics)
```

### Custom Evaluation Criteria with AspectCritic

For tailored evaluations specific to your use case, AspectCritic allows you to define custom evaluation criteria:

```python
from ragas.metrics import AspectCritic

# Define a custom evaluation aspect
custom_metric = AspectCritic(
    name="factual_accuracy",
    llm=evaluator_llm,
    definition="Verify if the answer accurately states company names, model names, and specific capabilities without any factual errors."
)

# Evaluate with your custom criteria
custom_results = evaluate(dataset=ragas_eval_dataset, metrics=[custom_metric])
```

### Training Your Own Metric

If you want to fine-tune metrics to your specific requirements:

1. Use the Ragas app to annotate evaluation results
2. Download the annotations as JSON
3. Train your custom metric:

```python
from ragas.config import InstructionConfig, DemonstrationConfig

demo_config = DemonstrationConfig(embedding=evaluator_embeddings)
inst_config = InstructionConfig(llm=evaluator_llm)

# Train your metric with your annotations
metric.train(
    path="your-annotations.json",
    demonstration_config=demo_config,
    instruction_config=inst_config
)
```

## Conclusion

This guide demonstrated how to use Ragas to thoroughly evaluate your R2R RAG implementation. By leveraging these evaluation tools, you can:

1. Measure the quality of your R2R system across multiple dimensions
2. Identify specific areas for improvement in retrieval and generation
3. Track performance improvements as you refine your implementation
4. Establish benchmarks for consistent quality

Through regular evaluation with Ragas, you can optimize your R2R configuration to deliver the most accurate, relevant, and helpful responses to your users.

For more information on R2R features, refer to the [R2R documentation](https://r2r-docs.sciphi.ai/). To explore additional evaluation metrics and techniques with Ragas, visit the [Ragas documentation](https://docs.ragas.io/).
