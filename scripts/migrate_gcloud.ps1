# ==========================================
# MAMASTORIA TO NANOBANANA MIGRATION SCRIPT (FIXED)
# ==========================================
# Prerequisites:
# 1. You must be logged in: gcloud auth login
# 2. Your account must have access to BOTH projects

$SOURCE_PROJECT = "mamastoria101"
$DEST_PROJECT = "nanobananacomic-482111"

$SOURCE_INSTANCE = "cloudsql-mamastoria-dev"
$DEST_INSTANCE = "cloudsql-nanobanana-dev"

$SOURCE_DB = "mamastoria_db"
$DEST_DB = "nanobanana_db"

$SOURCE_BUCKET = "mamastoria-storage"
$DEST_BUCKET = "nanobanana-storage"

# IAM Permission has been granted separately.

Write-Host "--- Starting Migration (Attempt 2) ---"

# 1. Transfer Images (Styles Folder) - Fixed Path Case (Styles vs styles)
Write-Host "1. Copying Images from $SOURCE_BUCKET to $DEST_BUCKET..."
# Try both 'Styles' (as seen in ls) AND 'styles' just in case, or match case insensitive? 
# gcloud storage cp doesn't do case insensitive. content listing showed 'Styles'.
# Copy to destination 'styles' (lowercase) to match code expectation if any? Or keep as Styles?
# The code usually assumes lowercase in URL? Let's check user's DB URL. 
# If DB has '.../Styles/foo.jpg', we should copy to 'Styles'. 
# We'll copy 'Styles' to 'Styles'.
gcloud storage cp -r "gs://$SOURCE_BUCKET/Styles" "gs://$DEST_BUCKET/" --project=$DEST_PROJECT

# 2. Export Data to CSV (with URL replacement and Schema Fix)
# Removing 'description' column from SELECT source, using empty string.
Write-Host "2. Exporting Styles Data..."
gcloud sql export csv $SOURCE_INSTANCE "gs://$SOURCE_BUCKET/temp_migrate/styles_v2.csv" `
    --database=$SOURCE_DB `
    --query="SELECT name, '' as description, REPLACE(image_url, '$SOURCE_BUCKET', '$DEST_BUCKET'), prompt_modifier FROM public.styles" `
    --project=$SOURCE_PROJECT

Write-Host "3. Exporting Genres Data..."
gcloud sql export csv $SOURCE_INSTANCE "gs://$SOURCE_BUCKET/temp_migrate/genres_v2.csv" `
    --database=$SOURCE_DB `
    --query="SELECT name, '' as description FROM public.genres" `
    --project=$SOURCE_PROJECT

# 3. Move CSV to Destination Bucket
Write-Host "4. Moving CSV files to Destination Bucket..."
gcloud storage cp "gs://$SOURCE_BUCKET/temp_migrate/*_v2.csv" "gs://$DEST_BUCKET/migration/" --project=$DEST_PROJECT

# 4. Import Data
Write-Host "5. Importing Styles..."
# Note: Ensure validation is loose just in case
gcloud sql import csv $DEST_INSTANCE "gs://$DEST_BUCKET/migration/styles_v2.csv" `
    --database=$DEST_DB `
    --table="public.styles" `
    --columns="name,description,image_url,prompt_modifier" `
    --user="postgres" `
    --project=$DEST_PROJECT

Write-Host "6. Importing Genres..."
gcloud sql import csv $DEST_INSTANCE "gs://$DEST_BUCKET/migration/genres_v2.csv" `
    --database=$DEST_DB `
    --table="public.genres" `
    --columns="name,description" `
    --user="postgres" `
    --project=$DEST_PROJECT

Write-Host "--- Migration Finished ---"
