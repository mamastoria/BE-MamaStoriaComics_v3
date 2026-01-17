# Deploy Backend to Cloud Run
Write-Host "Starting deployment..." -ForegroundColor Cyan

# Set variables
$PROJECT = "nanobananacomic-482111"
$REGION = "us-central1"
$SERVICE = "nanobanana-backend"

Write-Host "Project: $PROJECT"
Write-Host "Region: $REGION"
Write-Host "Service: $SERVICE"
Write-Host ""

# Deploy from source
Write-Host "Deploying from source..." -ForegroundColor Yellow
gcloud run deploy $SERVICE --source . --region $REGION --project $PROJECT --allow-unauthenticated --quiet

Write-Host ""
Write-Host "Deployment complete!" -ForegroundColor Green

# Get service URL
Write-Host "Getting service URL..."
gcloud run services describe $SERVICE --region $REGION --project $PROJECT --format="value(status.url)"
