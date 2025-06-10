Users deploying R2R into production settings benefit from robust, persistant logging. R2R supports this via [Victorialogs](https://docs.victoriametrics.com/victorialogs), open source user-friendly database for logs from [VictoriaMetrics](https://docs.victoriametrics.com).

Victorialogs ships by default with the [full version of R2R](/self-hosting/installation/full) and hosts a UI to view your logs at http://localhost:9428/select/vmui.

## Accessing Logs

### VictoriaLogs UI

The easiest way to view logs is through the VictoriaLogs UI:

<Steps>
  <Step>
  Navigate to http://localhost:9428/select/vmui.
  <img src="../images/cookbooks/logging/vmui.png" alt="The VictoriaLogs UI." />
  </Step>

  <Step>
    Use the query box to search for specific log entries.
    <img src="../images/cookbooks/logging/logging_query.png" alt="Querying logs." />
  </Step>

  <Step>
    Adjust the time range as needed using the time controls
    <img src="../images/cookbooks/logging/logging_filter_time.png" alt="Filtering logs by time." />
  </Step>
</Steps>

### Common Query Examples

Here are some useful queries for finding specific log information:

```json
# View all logs
*

# View logs with [ERROR] tag
{log=~"\\[ERROR\\].*"}

# View logs with error-related content
{log=~".*error.*"}
{log=~".*exception.*"}
{log=~".*traceback.*"}
{log=~".*failed.*"}

# View logs with warning content
{log=~".*WARNING.*"}

# View logs about a specific process
{log=~".*ingestion.*"}

# View specific error types
{log=~".*HTTPException.*"}
{log=~".*ValueError.*"}

# View Azure OpenAI-related errors
{log=~".*OpenAI.*"}
```

## Troubleshooting Common Issues

### No Logs Showing Up

If you don't see any logs:

1. Increase the time range - logs might be outside your current time window
2. Check if Fluent Bit is running: `docker ps | grep fluent-bit`
3. Check VictoriaLogs is running: `docker ps | grep victoria-logs`
4. Verify your R2R container is properly configured for logging

### Understanding Error Logs

When you see an error in the logs, it typically follows this pattern:

1. Error message with timestamp
2. A traceback showing the sequence of function calls
3. The specific error and its cause

Look for the actual error message at the bottom of a traceback to understand the root cause.

## Advanced Configuration

### Customizing Fluent Bit

If you need to customize how logs are collected and processed, you can modify the Fluent Bit configuration:

1. Create/edit the `fluent-bit.conf` file in your `./fluent-bit` directory
2. Restart the Fluent Bit container: `docker restart docker-fluent-bit-1`

### Setting Up Grafana for Log Visualization

For more advanced visualization, you can connect Grafana to VictoriaLogs:

1. Access Grafana at http://localhost:3001
2. Add a new VictoriaLogs data source:
   - Go to Configuration > Data Sources > Add data source
   - Select "VictoriaMetrics Logs"
   - Set URL to http://victoria-logs:9428
   - Save and test the connection

3. Create a new dashboard with a Logs panel
4. Configure the panel to query logs using the same query syntax as in the VictoriaLogs UI

## Retention Policy

By default, logs are retained for 60 days as configured in the Docker Compose file:

```yaml
victoria-logs:
  image: victoriametrics/victoria-logs:v1.10.1-victorialogs
  command: -storageDataPath=/data -retentionPeriod=60d
```

To change the retention period, modify the `-retentionPeriod` parameter and restart the container.

## Log Format

Each log entry contains:

- `_time`: Timestamp of the log
- `container_name`: Source container
- `log`: The actual log message
- Additional metadata

When searching logs, you'll typically want to search for content in the `log` field.
