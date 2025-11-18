#!/bin/bash
#
# PodX API Client Examples - curl
#
# This script demonstrates how to interact with the PodX API Server using curl.
#
# Features demonstrated:
# - Health checks
# - File upload
# - Job creation
# - Job status checking
# - Real-time progress streaming (SSE)
# - Listing jobs
#
# Usage:
#     bash examples/curl_examples.sh

set -e  # Exit on error

# Configuration
BASE_URL="${PODX_API_URL:-http://localhost:8000}"
API_KEY="${PODX_API_KEY:-}"  # Set if API key authentication is enabled

# Helper function for curl with optional API key
api_curl() {
    if [ -n "$API_KEY" ]; then
        curl -H "X-API-Key: $API_KEY" "$@"
    else
        curl "$@"
    fi
}

echo "PodX API Examples - curl"
echo "========================"
echo ""

# 1. Health Check
echo "1. Health Check"
echo "   GET /health"
echo ""
api_curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""

# 2. Detailed Health Check
echo "2. Detailed Health Check"
echo "   GET /health/ready"
echo ""
api_curl -s "$BASE_URL/health/ready" | python3 -m json.tool
echo ""

# 3. Upload Audio File
echo "3. Upload Audio File"
echo "   POST /upload"
echo ""
# Uncomment and modify path to your audio file:
# UPLOAD_RESPONSE=$(api_curl -s -X POST \
#     -F "file=@/path/to/your/audio.mp3" \
#     "$BASE_URL/upload")
# echo "$UPLOAD_RESPONSE" | python3 -m json.tool
# UPLOAD_ID=$(echo "$UPLOAD_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['upload_id'])")
# echo ""
# echo "Upload ID: $UPLOAD_ID"
# echo ""

# 4. Create Job from URL
echo "4. Create Job from URL"
echo "   POST /jobs"
echo ""
JOB_RESPONSE=$(api_curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{
        "url": "https://example.com/podcast.mp3",
        "profile": "quick"
    }' \
    "$BASE_URL/jobs")
echo "$JOB_RESPONSE" | python3 -m json.tool
JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
echo ""
echo "Job ID: $JOB_ID"
echo ""

# 4b. Create Job from Upload (alternative)
# echo "4b. Create Job from Upload"
# echo "   POST /jobs"
# echo ""
# JOB_RESPONSE=$(api_curl -s -X POST \
#     -H "Content-Type: application/json" \
#     -d "{
#         \"upload_id\": \"$UPLOAD_ID\",
#         \"profile\": \"quick\"
#     }" \
#     "$BASE_URL/jobs")
# echo "$JOB_RESPONSE" | python3 -m json.tool
# JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])")
# echo ""

# 5. Get Job Status
echo "5. Get Job Status"
echo "   GET /jobs/$JOB_ID"
echo ""
api_curl -s "$BASE_URL/jobs/$JOB_ID" | python3 -m json.tool
echo ""

# 6. Stream Real-Time Progress (SSE)
echo "6. Stream Real-Time Progress (SSE)"
echo "   GET /jobs/$JOB_ID/stream"
echo ""
echo "Streaming progress updates..."
echo ""

# Stream SSE events and parse them
# Note: This will continue until the job completes or fails
api_curl -s -N "$BASE_URL/jobs/$JOB_ID/stream" | while IFS= read -r line; do
    # Skip empty lines and comments
    if [[ -z "$line" || "$line" =~ ^: ]]; then
        continue
    fi

    # Parse SSE data
    if [[ "$line" =~ ^data:\ (.+)$ ]]; then
        data="${BASH_REMATCH[1]}"
        echo "  $data" | python3 -m json.tool

        # Check if job is done
        status=$(echo "$data" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))")
        if [[ "$status" == "completed" || "$status" == "failed" ]]; then
            break
        fi
    fi
done
echo ""

# 7. Get Final Job Details
echo "7. Get Final Job Details"
echo "   GET /jobs/$JOB_ID"
echo ""
api_curl -s "$BASE_URL/jobs/$JOB_ID" | python3 -m json.tool
echo ""

# 8. List Recent Jobs
echo "8. List Recent Jobs"
echo "   GET /jobs?limit=5"
echo ""
api_curl -s "$BASE_URL/jobs?limit=5" | python3 -m json.tool
echo ""

# 9. API Documentation
echo "9. API Documentation"
echo "   GET /docs (Swagger UI)"
echo "   GET /redoc (ReDoc)"
echo "   GET /openapi.json (OpenAPI spec)"
echo ""
echo "   Visit in browser:"
echo "   - $BASE_URL/docs"
echo "   - $BASE_URL/redoc"
echo ""

# 10. Metrics (if enabled)
echo "10. Metrics Endpoint (if PODX_METRICS_ENABLED=true)"
echo "    GET /metrics"
echo ""
# api_curl -s "$BASE_URL/metrics"
echo "    (Uncomment to fetch Prometheus metrics)"
echo ""

echo "✓ Examples completed!"
echo ""
echo "Tips:"
echo "  - Set PODX_API_KEY environment variable for API key authentication"
echo "  - Set PODX_API_URL to use a different server (default: http://localhost:8000)"
echo "  - Use -v flag with curl for verbose output: curl -v ..."
echo "  - Use jq for better JSON formatting: curl ... | jq ."
echo ""
