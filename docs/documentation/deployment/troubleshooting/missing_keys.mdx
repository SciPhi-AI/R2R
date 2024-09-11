# Troubleshooting Guide: Missing or Incorrect API Keys in R2R

API keys are crucial for authenticating and accessing various services integrated with R2R. Missing or incorrect API keys can lead to connection failures and service disruptions. This guide will help you identify and resolve API key issues.

## 1. Identifying API Key Issues

Common symptoms of API key problems include:

- Error messages mentioning "unauthorized," "authentication failed," or "invalid API key"
- Specific services or integrations not working while others function correctly
- Unexpected 401 or 403 HTTP status codes in logs

## 2. Checking API Key Configuration

### 2.1 Environment Variables

R2R uses environment variables to store API keys. Check if the required environment variables are set:

```bash
env | grep API_KEY
```

Look for variables like:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `AZURE_API_KEY`
- `UNSTRUCTURED_API_KEY`
- `HATCHET_CLIENT_TOKEN`

### 2.2 Configuration Files

If you're using configuration files (e.g., `r2r.toml`), verify that API keys are correctly set:

```bash
grep -i "api_key" /path/to/your/r2r.toml
```

## 3. Common API Key Issues and Solutions

### 3.1 OpenAI API Key

**Issue:** OpenAI services not working or returning authentication errors.

**Solution:**
1. Verify the `OPENAI_API_KEY` is set:
   ```bash
   echo $OPENAI_API_KEY
   ```
2. Ensure the key starts with "sk-".
3. Check the key's validity in the OpenAI dashboard.
4. Regenerate the key if necessary and update the environment variable.

### 3.2 Anthropic API Key

**Issue:** Claude or other Anthropic models not functioning.

**Solution:**
1. Confirm the `ANTHROPIC_API_KEY` is set:
   ```bash
   echo $ANTHROPIC_API_KEY
   ```
2. Verify the key format (typically starts with "sk-ant-").
3. Test the key using Anthropic's API documentation.

### 3.3 Azure API Key

**Issue:** Azure-based services failing to authenticate.

**Solution:**
1. Check the `AZURE_API_KEY` is set:
   ```bash
   echo $AZURE_API_KEY
   ```
2. Verify additional Azure-related variables:
   - `AZURE_API_BASE`
   - `AZURE_API_VERSION`
3. Ensure the key and endpoint match your Azure resource configuration.

### 3.4 Unstructured API Key

**Issue:** File ingestion or parsing failures.

**Solution:**
1. Verify the `UNSTRUCTURED_API_KEY` is set:
   ```bash
   echo $UNSTRUCTURED_API_KEY
   ```
2. Check if the Unstructured API URL is correctly configured:
   ```bash
   echo $UNSTRUCTURED_API_URL
   ```
3. Test the key using Unstructured's API documentation.

### 3.5 Hatchet Client Token

**Issue:** Workflow orchestration failures or Hatchet connectivity issues.

**Solution:**
1. Confirm the `HATCHET_CLIENT_TOKEN` is set:
   ```bash
   echo $HATCHET_CLIENT_TOKEN
   ```
2. Verify the token was correctly generated during the R2R setup process.
3. Check Hatchet logs for any token-related errors.

## 4. Updating API Keys

If you need to update an API key:

1. Stop the R2R service:
   ```bash
   docker-compose down
   ```

2. Update the key in your environment or configuration file:
   ```bash
   export NEW_API_KEY="your-new-key-here"
   ```
   Or update the `r2r.toml` file if you're using configuration files.

3. Restart the R2R service:
   ```bash
   docker-compose up -d
   ```

## 5. Security Best Practices

- Never commit API keys to version control.
- Use environment variables or secure secret management solutions.
- Regularly rotate API keys, especially if you suspect they've been compromised.
- Use the principle of least privilege when creating API keys.

## 6. Debugging API Key Issues

If you're still having trouble:

1. Check R2R logs for detailed error messages:
   ```bash
   docker-compose logs r2r
   ```

2. Verify network connectivity to the API endpoints.

3. Ensure your account has the necessary permissions for the API keys you're using.

4. Try using the API key in a simple curl command to isolate R2R-specific issues:
   ```bash
   curl -H "Authorization: Bearer $YOUR_API_KEY" https://api.example.com/v1/test
   ```

## 7. Getting Help

If you've tried these steps and are still experiencing issues:

1. Check the R2R documentation for any recent changes or known issues with API integrations.
2. Search the R2R GitHub issues for similar problems and solutions.
3. Reach out to the R2R community on Discord or other support channels, providing:
   - R2R version
   - Relevant logs (with sensitive information redacted)
   - Steps to reproduce the issue
   - Any error messages you're seeing

Remember, never share your actual API keys when seeking help. Use placeholders or redacted versions in any logs or code snippets you share publicly.