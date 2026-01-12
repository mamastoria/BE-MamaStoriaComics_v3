# Render Worker Implementation Plan

## 🎯 Objective

Memisahkan proses rendering gambar komik ke Cloud Run service terpisah dengan resource dedicated, mirip dengan Video Worker.

## 📊 Current Architecture (Masalah)

```
User Request → Main API (4GB RAM, 4 CPU, concurrency=80)
                 ↓
            Render Comic (in-process background thread)
                 ↓
            OOM/Resource Contention when multiple concurrent renders
```

**Problem**: 5+ concurrent renders compete for the same 4GB RAM instance.

## 🏗️ New Architecture (Solusi)

```
User Request → Main API → Create DB Record → Queue to Cloud Tasks
                                                    ↓
                                          Cloud Tasks Queue
                                            (render-queue)
                                                    ↓
                                          Render Worker Service
                                          (8GB RAM, 4 CPU, concurrency=1)
                                                    ↓
                                          Generate Images → GCS
                                                    ↓
                                          Update DB → Queue Video
```

## 📦 New Components

### 1. Render Worker Service (`render_worker/`)

- **File**: `render_worker/main.py`
- **Dockerfile**: `Dockerfile.render-worker`
- **Cloud Run Service**: `render-worker`
- **Specs**:
  - Memory: 8GB
  - CPU: 4
  - Concurrency: 1 (isolated processing)
  - Timeout: 900s (15 min)
  - Min instances: 0
  - Max instances: 25

### 2. Cloud Tasks Queue

- **Name**: `render-queue`
- **Location**: `asia-southeast2`
- **Rate**: 25 dispatches/second

### 3. Render Queue Service (`app/services/render_queue.py`)

- Function to queue render jobs to Cloud Tasks
- Similar to `video_queue.py`

## 📋 Implementation Steps

### Step 1: Create Render Worker Service

```
render_worker/
├── main.py           # FastAPI app with /generate endpoint
├── requirements.txt  # Dependencies
└── Dockerfile        # Python + dependencies
```

### Step 2: Create Dockerfile.render-worker

```dockerfile
FROM python:3.11-slim
# Install system deps (for image processing)
RUN apt-get update && apt-get install -y ...
# Copy code and install dependencies
...
CMD ["python", "render_worker/main.py"]
```

### Step 3: Create app/services/render_queue.py

```python
def queue_render_job(comic_id: int, script_data: dict) -> Optional[str]:
    """Queue render job to Cloud Tasks"""
    ...
```

### Step 4: Modify comics.py

- After script generation, queue to Cloud Tasks instead of background thread
- Fallback to in-process if Cloud Tasks fails

### Step 5: Create Cloud Tasks Queue

```bash
gcloud tasks queues create render-queue \
    --location=asia-southeast2 \
    --max-concurrent-dispatches=25 \
    --max-dispatches-per-second=25
```

### Step 6: Deploy Render Worker

```bash
gcloud run deploy render-worker \
    --source=. \
    --dockerfile=Dockerfile.render-worker \
    --memory=8Gi \
    --cpu=4 \
    --concurrency=1 \
    --timeout=900 \
    --min-instances=0 \
    --max-instances=25 \
    --region=asia-southeast2 \
    --no-allow-unauthenticated
```

### Step 7: Grant IAM Permissions

```bash
gcloud run services add-iam-policy-binding render-worker \
    --member="serviceAccount:cloud-tasks-invoker@PROJECT.iam.gserviceaccount.com" \
    --role="roles/run.invoker"
```

### Step 8: Update Main API & Deploy

## 🔄 New Flow Detail

### A. Script Generation (Main API - unchanged)

1. User calls `/comics/story-idea`
2. Main API generates script via AI
3. Creates comic record with status `SCRIPT_READY`
4. **NEW**: Queue render job → Cloud Tasks

### B. Image Rendering (Render Worker - new)

1. Cloud Tasks calls `render-worker/generate`
2. Worker receives `{comic_id, script_data}`
3. Updates status to `RENDERING`
4. Calls `core.render_part_payload()` for Part 1 & 2 (parallel)
5. Uploads images to GCS
6. Updates panel image_url in DB
7. Updates status to `COMPLETED` or queues video

### C. Video Generation (Video Worker - existing)

- Triggered after render completes
- Already isolated with dedicated resources

## 📊 Resource Comparison

| Service       | Memory | CPU | Concurrency | Max Instances |
| ------------- | ------ | --- | ----------- | ------------- |
| Main API      | 4GB    | 4   | 80          | 100           |
| Render Worker | 8GB    | 4   | 1           | 25            |
| Video Worker  | 8GB    | 4   | 1           | 25            |

## ⏱️ Expected Performance

| Scenario      | Before   | After                           |
| ------------- | -------- | ------------------------------- |
| 1 comic       | ~3 min   | ~3 min                          |
| 5 concurrent  | OOM/slow | 5 × ~3 min = ~3 min (parallel)  |
| 25 concurrent | Crash    | 25 × ~3 min = ~3 min (parallel) |

## 🚀 Rollout Plan

1. **Phase 1**: Deploy render-worker (no traffic yet)
2. **Phase 2**: Create queue and test with single comic
3. **Phase 3**: Update main API with queue integration + fallback
4. **Phase 4**: Deploy main API with new code
5. **Phase 5**: Monitor and tune

## ✅ Success Criteria

- [ ] 5+ concurrent comic generation without OOM
- [ ] Each comic completes in ~3-5 minutes
- [ ] Main API remains responsive during heavy load
- [ ] Fallback works if Cloud Tasks unavailable
