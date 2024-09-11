# Troubleshooting Guide: Unstructured.io Setup Difficulties with R2R

Unstructured.io is a crucial component in R2R for handling file ingestion. This guide addresses common issues and their solutions when setting up and using Unstructured.io within the R2R ecosystem.

## 1. Installation Issues

### 1.1 Missing Dependencies

**Problem:** Unstructured.io fails to install due to missing system dependencies.

**Solution:**
1. Ensure you have the required system libraries:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-dev libxml2-dev libxslt1-dev antiword unrtf poppler-utils pstotext tesseract-ocr flac ffmpeg lame libmad0 libsox-fmt-mp3 sox libjpeg-dev swig
   ```
2. If using pip, install with extras:
   ```bash
   pip install "unstructured[all-deps]"
   ```

### 1.2 Version Compatibility

**Problem:** Incompatibility between Unstructured.io and R2R versions.

**Solution:**
1. Check the R2R documentation for the recommended Unstructured.io version.
2. Install the specific version:
   ```bash
   pip install unstructured==X.Y.Z
   ```

## 2. Configuration Issues

### 2.1 API Key Not Recognized

**Problem:** R2R fails to connect to Unstructured.io due to API key issues.

**Solution:**
1. Verify your API key is correctly set in the R2R configuration:
   ```toml
   [unstructured]
   api_key = "your-api-key-here"
   ```
2. Ensure the environment variable is set:
   ```bash
   export UNSTRUCTURED_API_KEY=your-api-key-here
   ```

### 2.2 Incorrect API Endpoint

**Problem:** R2R can't reach the Unstructured.io API.

**Solution:**
1. Check the API endpoint in your R2R configuration:
   ```toml
   [unstructured]
   api_url = "https://api.unstructured.io/general/v0/general"
   ```
2. If using a self-hosted version, ensure the URL is correct.

## 3. Runtime Errors

### 3.1 File Processing Failures

**Problem:** Unstructured.io fails to process certain file types.

**Solution:**
1. Verify the file type is supported by Unstructured.io.
2. Check file permissions and ensure R2R has access to the files.
3. For specific file types, install additional dependencies:
   ```bash
   pip install "unstructured[pdf]"  # For enhanced PDF support
   ```

### 3.2 Memory Issues

**Problem:** Unstructured.io crashes due to insufficient memory when processing large files.

**Solution:**
1. Increase the available memory for the R2R process.
2. If using Docker, adjust the container's memory limit:
   ```yaml
   services:
     r2r:
       deploy:
         resources:
           limits:
             memory: 4G
   ```

### 3.3 Slow Processing

**Problem:** File processing is exceptionally slow.

**Solution:**
1. Check system resources (CPU, RAM) and ensure they meet minimum requirements.
2. Consider using Unstructured.io's async API for large batch processing.
3. Implement a caching mechanism in R2R to store processed results.

## 4. Integration Issues

### 4.1 Data Format Mismatch

**Problem:** R2R fails to interpret the output from Unstructured.io correctly.

**Solution:**
1. Verify that R2R's parsing logic matches Unstructured.io's output format.
2. Check for any recent changes in Unstructured.io's API responses and update R2R accordingly.

### 4.2 Rate Limiting

**Problem:** Hitting API rate limits when using Unstructured.io's cloud service.

**Solution:**
1. Implement rate limiting in your R2R application.
2. Consider upgrading your Unstructured.io plan for higher limits.
3. Use local deployment of Unstructured.io for unlimited processing.

## 5. Local Deployment Issues

### 5.1 Docker Container Failures

**Problem:** Unstructured.io Docker container fails to start or crashes.

**Solution:**
1. Check Docker logs:
   ```bash
   docker logs [container_name]
   ```
2. Ensure all required environment variables are set.
3. Verify that the Docker image version is compatible with your R2R version.

### 5.2 Network Connectivity

**Problem:** R2R can't connect to locally deployed Unstructured.io.

**Solution:**
1. Ensure the Unstructured.io container is on the same Docker network as R2R.
2. Check firewall settings and ensure necessary ports are open.
3. Verify the URL in R2R configuration points to the correct local address.

## 6. Debugging Tips

1. Enable verbose logging in both R2R and Unstructured.io.
2. Use tools like `curl` to test API endpoints directly.
3. Implement proper error handling in R2R to capture and log Unstructured.io-related issues.

## 7. Seeking Help

If issues persist:
1. Check the [Unstructured.io documentation](https://unstructured-io.github.io/unstructured/).
2. Visit the [R2R GitHub repository](https://github.com/SciPhi-AI/R2R) for specific integration issues.
3. Reach out to the R2R community on Discord or other support channels.

Remember to provide detailed information when seeking help, including:
- R2R and Unstructured.io versions
- Deployment method (cloud, local, Docker)
- Specific error messages and logs
- Steps to reproduce the issue

By following this guide, you should be able to troubleshoot and resolve most Unstructured.io setup and integration issues within your R2R deployment.