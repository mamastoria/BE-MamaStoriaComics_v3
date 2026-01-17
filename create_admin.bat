@echo off
echo Creating initial admin user...
echo.

curl -X POST "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/setup/create-initial-admin?phone_number=%%2B6281234567890&password=admin123&full_name=Admin%%20Dashboard"

echo.
echo.
echo ========================================
echo Admin credentials:
echo Phone: +6281234567890
echo Password: admin123
echo ========================================
echo.
echo You can now login to:
echo https://nanobanana-backend-1089713441636.us-central1.run.app/static/admin-dashboard.html
echo.
pause
