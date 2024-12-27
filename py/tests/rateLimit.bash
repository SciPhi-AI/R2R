#!/usr/bin/env bash

# Configuration
URL="https://api.cloud.sciphi.ai/v3/health"
TOTAL_REQUESTS=60
SLEEP_INTERVAL=0.05
REQUIRED_429_COUNT=20

# Initialize counters
count_429=0
count_total=0

# Function to handle exit codes
check_exit_status() {
    if [ $count_429 -ge $REQUIRED_429_COUNT ]; then
        echo "✅ Test passed: Got $count_429 rate limits (429s), which meets the minimum requirement of $REQUIRED_429_COUNT"
        exit 0
    else
        echo "❌ Test failed: Only got $count_429 rate limits (429s), which is less than the required $REQUIRED_429_COUNT"
        exit 1
    fi
}

# Trap Ctrl+C and call check_exit_status
trap check_exit_status INT

echo "Starting rate limit test for $URL"
echo "Target: At least $REQUIRED_429_COUNT rate limits (HTTP 429)"

for ((i=1; i<=TOTAL_REQUESTS; i++)); do
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$URL")
    count_total=$((count_total + 1))

    # Color coding for different responses
    if [ "$RESPONSE" = "429" ]; then
        count_429=$((count_429 + 1))
        echo -e "\033[33mRequest $i: HTTP $RESPONSE (Rate limit) - Total 429s: $count_429\033[0m"
    elif [ "$RESPONSE" = "200" ]; then
        echo -e "\033[32mRequest $i: HTTP $RESPONSE (Success)\033[0m"
    else
        echo -e "\033[31mRequest $i: HTTP $RESPONSE (Error)\033[0m"
    fi

    sleep $SLEEP_INTERVAL
done

# Check final results
check_exit_status
