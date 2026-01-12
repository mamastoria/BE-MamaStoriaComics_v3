@echo off
echo ===================================================
echo  MamaStoria Backend Deployment Script
echo ===================================================
echo.
echo Deploying to Cloud Run (asia-southeast2)...

cd /d d:\laragon\www\BE_MamaStoria_v3

echo.
echo Deploying from source (Cloud Build auto-detect)...
call gcloud run deploy nanobanana-backend --source . --region asia-southeast2 --allow-unauthenticated --quiet

echo.
echo Waiting 10 seconds for service to stabilize...
timeout /t 10 /nobreak

echo.
echo Patching Database (Adding timing columns)...
curl -X POST "https://nanobanana-backend-1089713441636.asia-southeast2.run.app/api/v1/admin/db-patch-timing" -H "Content-Type: application/json"

echo.
echo ===================================================
echo  Deployment Complete!
echo  Dashboard: http://localhost/Admin-MamaStoria/monitoring.php
echo ===================================================
pause
