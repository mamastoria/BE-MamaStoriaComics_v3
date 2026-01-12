#!/bin/bash
# =============================================================================
# Cloud Scheduler Setup Script
# Creates Cloud Scheduler jobs to trigger job processing every minute
# =============================================================================

PROJECT_ID="nanobananacomic-482111"
REGION="asia-southeast2"
BACKEND_URL="https://nanobanana-backend-1089713441636.asia-southeast2.run.app"

# Service account for invoking Cloud Run
SERVICE_ACCOUNT="cloud-tasks-invoker@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=============================================="
echo "Setting up Cloud Scheduler for Job Queue"
echo "=============================================="

# Create scheduler job for processing all jobs (every 1 minute)
echo "Creating scheduler job: job-queue-processor"

gcloud scheduler jobs create http job-queue-processor \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --schedule="* * * * *" \
    --uri="${BACKEND_URL}/api/v1/jobs/process/all" \
    --http-method=POST \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --oidc-token-audience="${BACKEND_URL}" \
    --attempt-deadline="540s" \
    --description="Triggers job queue processing every minute" \
    2>/dev/null || \
gcloud scheduler jobs update http job-queue-processor \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --schedule="* * * * *" \
    --uri="${BACKEND_URL}/api/v1/jobs/process/all" \
    --http-method=POST \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --oidc-token-audience="${BACKEND_URL}" \
    --attempt-deadline="540s" \
    --description="Triggers job queue processing every minute"

echo ""
echo "=============================================="
echo "Scheduler setup complete!"
echo ""
echo "Jobs created:"
echo "  - job-queue-processor (every 1 minute)"
echo ""
echo "To test manually:"
echo "  curl -X POST ${BACKEND_URL}/api/v1/jobs/process/all"
echo ""
echo "To check queue status:"
echo "  curl ${BACKEND_URL}/api/v1/jobs/status"
echo "=============================================="
