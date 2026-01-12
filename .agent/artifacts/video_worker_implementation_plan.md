# Implementation Plan: Video Worker Architecture

## Objective

Memisahkan video generation ke dedicated Cloud Run service dengan arsitektur queue untuk maksimalkan performa dan reliability.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   USER REQUEST                                                  │
│        │                                                        │
│        ▼                                                        │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │         nanobanana-backend (MAIN API)                   │   │
│   │         Memory: 4GB | CPU: 4 | Concurrency: 80          │   │
│   │                                                         │   │
│   │   ✓ Authentication                                      │   │
│   │   ✓ Script Generation (Gemini API)                      │   │
│   │   ✓ Image Rendering (Flux API)                          │   │
│   │   ✓ Panel Clipping (OpenCV)                             │   │
│   │   ✓ Queue video job → Cloud Tasks                       │   │
│   │                                                         │   │
│   │   Response: "Video is being generated..."               │   │
│   └────────────────────────┬────────────────────────────────┘   │
│                            │                                    │
│                            ▼ Cloud Tasks Queue                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │         video-worker (DEDICATED SERVICE)                │   │
│   │         Memory: 8GB | CPU: 4 | Concurrency: 1           │   │
│   │         Min: 0 | Max: 25                                │   │
│   │                                                         │   │
│   │   ✓ Download panels from GCS                            │   │
│   │   ✓ Generate TTS audio                                  │   │
│   │   ✓ FFmpeg video encoding                               │   │
│   │   ✓ Upload to GCS                                       │   │
│   │   ✓ Update DB status → COMPLETED                        │   │
│   │   ✓ Push notification to user (optional)               │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### Phase 1: Infrastructure Setup

#### 1.1 Update Main API Config

```bash
gcloud run services update nanobanana-backend \
  --memory=4Gi \
  --cpu=4 \
  --concurrency=80 \
  --min-instances=1 \
  --max-instances=100 \
  --timeout=600 \
  --region=asia-southeast2 \
  --project=nanobananacomic-482111
```

#### 1.2 Create Cloud Tasks Queue

```bash
gcloud tasks queues create video-generation-queue \
  --location=asia-southeast2 \
  --project=nanobananacomic-482111 \
  --max-dispatches-per-second=5 \
  --max-concurrent-dispatches=25 \
  --max-attempts=3 \
  --min-backoff=60s \
  --max-backoff=3600s
```

### Phase 2: Create Video Worker Service

#### 2.1 Create video_worker/ directory structure

```
BE_MamaStoria_v3/
├── video_worker/
│   ├── main.py              # FastAPI app for video worker
│   ├── Dockerfile           # Container build
│   ├── requirements.txt     # Dependencies
│   └── cloudbuild.yaml      # Build config
```

#### 2.2 Video Worker main.py

- Endpoint: POST /generate
- Accepts: comic_id, panel_data (from Cloud Tasks)
- Process: Download panels → TTS → FFmpeg → Upload → Update DB

#### 2.3 Deploy Video Worker

```bash
gcloud run deploy video-worker \
  --source=./video_worker \
  --memory=8Gi \
  --cpu=4 \
  --concurrency=1 \
  --timeout=3600 \
  --min-instances=0 \
  --max-instances=25 \
  --region=asia-southeast2 \
  --project=nanobananacomic-482111 \
  --no-allow-unauthenticated
```

### Phase 3: Modify Backend to Use Queue

#### 3.1 Add Cloud Tasks client

```python
# app/services/video_queue.py
from google.cloud import tasks_v2
import json

def queue_video_generation(comic_id: int, panels_data: list) -> str:
    """Queue video generation job to Cloud Tasks"""
    client = tasks_v2.CloudTasksClient()

    project = "nanobananacomic-482111"
    location = "asia-southeast2"
    queue = "video-generation-queue"

    parent = client.queue_path(project, location, queue)

    # Get video-worker URL
    video_worker_url = "https://video-worker-xxxxx.asia-southeast2.run.app/generate"

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": video_worker_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "comic_id": comic_id,
                "panels": panels_data
            }).encode(),
            "oidc_token": {
                "service_account_email": "cloud-tasks-invoker@nanobananacomic-482111.iam.gserviceaccount.com"
            }
        }
    }

    response = client.create_task(parent=parent, task=task)
    return response.name
```

#### 3.2 Update generate-video endpoint

```python
# In comics.py - replace background task with queue
@router.post("/comics/{id}/generate-video", response_model=dict)
async def generate_comic_video(id: int, ...):
    # ... validation code ...

    # Queue to Cloud Tasks instead of background task
    from app.services.video_queue import queue_video_generation

    task_name = queue_video_generation(comic.id, panel_data)

    # Update status
    comic.video_status = "QUEUED"
    db.commit()

    return {
        "ok": True,
        "message": "Video generation queued",
        "data": {
            "comic_id": id,
            "status": "QUEUED",
            "task_id": task_name.split("/")[-1]
        }
    }
```

### Phase 4: Service Account & IAM

#### 4.1 Create service account for Cloud Tasks

```bash
gcloud iam service-accounts create cloud-tasks-invoker \
  --display-name="Cloud Tasks Video Worker Invoker" \
  --project=nanobananacomic-482111
```

#### 4.2 Grant permissions

```bash
# Allow service account to invoke video-worker
gcloud run services add-iam-policy-binding video-worker \
  --member="serviceAccount:cloud-tasks-invoker@nanobananacomic-482111.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=asia-southeast2 \
  --project=nanobananacomic-482111
```

### Phase 5: Testing & Monitoring

#### 5.1 Test queue manually

```bash
curl -X POST https://video-worker-xxx.run.app/generate \
  -H "Content-Type: application/json" \
  -d '{"comic_id": 123, "panels": [...]}'
```

#### 5.2 Monitor in Cloud Console

- Cloud Tasks: https://console.cloud.google.com/cloudtasks
- Video Worker Logs: https://console.cloud.google.com/run/detail/asia-southeast2/video-worker/logs

## Files to Create/Modify

### New Files:

1. `video_worker/main.py` - FastAPI video worker service
2. `video_worker/Dockerfile` - Container build
3. `video_worker/requirements.txt` - Dependencies
4. `app/services/video_queue.py` - Cloud Tasks integration

### Modified Files:

1. `app/api/comics.py` - Update generate-video endpoint to use queue

## Timeline

- Phase 1: 30 minutes
- Phase 2: 2-3 hours
- Phase 3: 1-2 hours
- Phase 4: 30 minutes
- Phase 5: 1 hour

**Total: 5-7 hours**

## Rollback Plan

If issues occur, revert to current architecture:

1. Remove Cloud Tasks queue call
2. Restore background task in comics.py
3. Update main API to 8GB/4CPU/concurrency=2
