# Troubleshooting Guide: Local LLM Integration Issues with R2R

When integrating local Language Models (LLMs) with R2R, you may encounter various issues. This guide will help you diagnose and resolve common problems.

## 1. Ollama Connection Issues

### Symptom: R2R can't connect to Ollama

1. **Check Ollama is running:**
   ```bash
   docker ps | grep ollama
   ```
   Ensure the Ollama container is up and running.

2. **Verify Ollama API accessibility:**
   ```bash
   curl http://localhost:11434/api/tags
   ```
   This should return a list of available models.

3. **Check R2R configuration:**
   Ensure the `OLLAMA_API_BASE` environment variable is set correctly in your R2R configuration:
   ```yaml
   OLLAMA_API_BASE: http://ollama:11434
   ```

4. **Network connectivity:**
   Ensure Ollama and R2R containers are on the same Docker network.

### Solution:
- If Ollama isn't running, start it with `docker-compose up -d ollama`
- If API is inaccessible, check Ollama logs: `docker logs ollama`
- Correct the `OLLAMA_API_BASE` if necessary
- Ensure both services are on the `r2r-network` in your Docker Compose file

## 2. Model Loading Issues

### Symptom: Specified model isn't available or fails to load

1. **List available models:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. **Attempt to pull the model:**
   ```bash
   docker exec -it ollama ollama pull <model_name>
   ```

3. **Check Ollama logs for pull errors:**
   ```bash
   docker logs ollama
   ```

### Solution:
- If the model isn't listed, pull it using the Ollama CLI
- If pull fails, check internet connectivity and Ollama's GitHub for known issues
- Ensure sufficient disk space for model storage

## 3. Performance Issues

### Symptom: Local LLM responses are slow or timeouts occur

1. **Check system resources:**
   ```bash
   docker stats
   ```
   Look for high CPU or memory usage.

2. **Verify GPU utilization** (if applicable):
   ```bash
   nvidia-smi
   ```

3. **Review Ollama configuration:**
   Check if Ollama is configured to use GPU acceleration.

### Solution:
- Increase resources allocated to the Ollama container
- Enable GPU acceleration if available
- Consider using a smaller or more efficient model

## 4. Inconsistent Responses

### Symptom: LLM responses are inconsistent or unexpected

1. **Verify model version:**
   ```bash
   docker exec -it ollama ollama list
   ```
   Ensure you're using the intended model version.

2. **Check prompt template:**
   Review the prompt template in your R2R configuration for any issues.

3. **Test model directly:**
   ```bash
   docker exec -it ollama ollama run <model_name> "Your test prompt here"
   ```
   Compare direct results with those from R2R.

### Solution:
- Update to the latest model version if necessary
- Adjust prompt templates in R2R configuration
- Ensure consistent tokenization and preprocessing in R2R

## 5. Integration Configuration Issues

### Symptom: R2R doesn't use the local LLM as expected

1. **Review R2R configuration:**
   Check your `r2r.toml` or environment variables to ensure local LLM is properly configured.

2. **Verify LLM provider settings:**
   Ensure the correct provider (e.g., 'ollama') is set in your configuration.

3. **Check R2R logs:**
   Look for any errors or warnings related to LLM initialization.

### Solution:
- Correct configuration settings in `r2r.toml` or environment variables
- Ensure the LLM provider is correctly specified
- Restart R2R after configuration changes

## 6. Memory Management Issues

### Symptom: Out of memory errors or crashes during LLM operations

1. **Monitor memory usage:**
   ```bash
   docker stats ollama
   ```

2. **Check Ollama logs for OOM errors:**
   ```bash
   docker logs ollama | grep "Out of memory"
   ```

3. **Review model specifications:**
   Ensure your hardware meets the minimum requirements for the chosen model.

### Solution:
- Increase memory allocation for the Ollama container
- Use a smaller model if hardware is limited
- Implement request queuing in R2R to manage concurrent LLM calls

## 7. API Compatibility Issues

### Symptom: R2R fails to communicate properly with Ollama

1. **Check Ollama version:**
   ```bash
   docker exec -it ollama ollama --version
   ```

2. **Review R2R documentation:**
   Ensure you're using a compatible version of Ollama for your R2R version.

3. **Test basic API calls:**
   ```bash
   curl -X POST http://localhost:11434/api/generate -d '{"model": "<model_name>", "prompt": "Hello, world!"}'
   ```

### Solution:
- Update Ollama to a compatible version
- Adjust R2R code if using custom integrations
- Check for any middleware or proxy issues affecting API calls

## Getting Further Help

If you're still experiencing issues after trying these troubleshooting steps:

1. Gather relevant logs from both R2R and Ollama
2. Note your system specifications and R2R configuration
3. Check the R2R GitHub issues for similar problems
4. Consider posting a detailed question on the R2R Discord community or GitHub discussions

Remember to provide:
- R2R version (`r2r --version`)
- Ollama version
- Docker and Docker Compose versions
- Host system specifications
- Detailed error messages and logs

By following this guide, you should be able to resolve most common issues with local LLM integration in R2R. If problems persist, don't hesitate to reach out to the R2R community for further assistance.