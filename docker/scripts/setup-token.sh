#!/bin/bash

set -e
echo 'Starting token creation process...'

# Attempt to create token and capture both stdout and stderr
TOKEN_OUTPUT=$(/hatchet/hatchet-admin token create --config /hatchet/config --tenant-id 707d0855-80ab-4e1f-a156-f1c4546cbf52 2>&1)

# Extract the token (assuming it's the only part that looks like a JWT)
TOKEN=$(echo "$TOKEN_OUTPUT" | grep -Eo 'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*')

if [ -z "$TOKEN" ]; then
    echo 'Error: Failed to extract token. Full command output:' >&2
    echo "$TOKEN_OUTPUT" >&2
    exit 1
fi

echo "$TOKEN" > /tmp/hatchet_api_key
echo 'Token created and saved to /tmp/hatchet_api_key'

# Copy token to final destination
echo -n "$TOKEN" > /hatchet_api_key/api_key.txt
echo 'Token copied to /hatchet_api_key/api_key.txt'

# Verify token was copied correctly
if [ "$(cat /tmp/hatchet_api_key)" != "$(cat /hatchet_api_key/api_key.txt)" ]; then
    echo 'Error: Token copy failed, files do not match' >&2
    echo 'Content of /tmp/hatchet_api_key:'
    cat /tmp/hatchet_api_key
    echo 'Content of /hatchet_api_key/api_key.txt:'
    cat /hatchet_api_key/api_key.txt
    exit 1
fi

echo 'Hatchet API key has been saved successfully'
echo 'Token length:' ${#TOKEN}
echo 'Token (first 20 chars):' ${TOKEN:0:20}
echo 'Token structure:' $(echo $TOKEN | awk -F. '{print NF-1}') 'parts'

# Check each part of the token
for i in 1 2 3; do
    PART=$(echo $TOKEN | cut -d. -f$i)
    echo 'Part' $i 'length:' ${#PART}
    echo 'Part' $i 'base64 check:' $(echo $PART | base64 -d >/dev/null 2>&1 && echo 'Valid' || echo 'Invalid')
done

# Final validation attempt
if ! echo $TOKEN | awk -F. '{print $2}' | base64 -d 2>/dev/null | jq . >/dev/null 2>&1; then
    echo 'Warning: Token payload is not valid JSON when base64 decoded' >&2
else
    echo 'Token payload appears to be valid JSON'
fi
