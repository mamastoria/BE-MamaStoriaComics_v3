# Failed Job Recovery - Troubleshooting Guide

## Problem: Comics Stuck in FAILED Status

### Symptoms

- Comic has status "FAILED" in database
- Comic doesn't appear in Cloud Tasks queue
- Manual "Run Task" is required to process the comic
- Automatic job processor doesn't pick up the comic

### Root Cause

Comics with status `FAILED` are not included in any of the job processor queries:

- Script jobs only process: `PENDING`, `SCRIPT_FAILED`, `NULL`
- Image jobs only process: `SCRIPT_READY`
- Video jobs only process: `PROCESSING`
- **FAILED status is a dead-end** - comics never get retried automatically

### Solution Implemented

#### 1. Automatic Recovery Service

Created `app/services/failed_job_recovery.py` that:

- Finds comics with `FAILED` status
- Analyzes the failure point (script/image/video)
- Resets status to appropriate retry state
- Runs automatically with job processor

#### 2. Manual Recovery Endpoint

Added `/api/v1/worker/recover-failed-jobs` endpoint for manual intervention

### How to Use

#### Automatic Recovery (Recommended)

The recovery service runs automatically every time the job processor runs:

```bash
# Trigger via cron endpoint
curl -X POST https://YOUR-API/api/v1/jobs/process
```

#### Manual Recovery

```bash
# Recover all failed comics immediately
curl -X POST https://YOUR-API/api/v1/worker/recover-failed-jobs
```

### Recovery Logic

The service analyzes each failed comic:

1. **No panels exist** → Reset to `PENDING` (retry script generation)
2. **Panels exist, no images** → Reset to `SCRIPT_READY` (retry image generation)
3. **Some images missing** → Reset to `SCRIPT_READY` (retry image generation)
4. **All images exist, no video** → Reset to `PROCESSING` (retry video generation)
5. **All assets exist** → Mark as `COMPLETED` (false failure)

### Configuration

Edit `app/services/failed_job_recovery.py`:

```python
RECOVERY_CONFIG = {
    "min_retry_delay_minutes": 5,  # Wait time before retry
    "max_retries": 3,  # Maximum retry attempts
}
```

### Monitoring

Check recovery status:

```bash
# View job queue status
curl https://YOUR-API/api/v1/jobs/status

# Check logs for recovery activity
grep "RECOVERING COMIC" /var/log/app.log
```

### Example: Comic ID 323

Based on the screenshot, Comic ID 323 has:

- Status: `FAILED`
- Not in queue (0 tasks)

**Recovery steps:**

1. Run manual recovery: `POST /api/v1/worker/recover-failed-jobs`
2. System analyzes Comic 323
3. Determines failure point (likely video generation)
4. Resets to `PROCESSING` status
5. Next job processor run picks it up automatically
6. Video generation retries

### Prevention

To prevent comics from getting stuck in FAILED:

1. Ensure Cloud Tasks queues are configured correctly
2. Monitor error logs for recurring failures
3. Set up automatic recovery via cron job
4. Configure retry limits appropriately

### Related Files

- `app/services/failed_job_recovery.py` - Recovery logic
- `app/services/job_processor.py` - Main job processor
- `app/api/worker.py` - Worker endpoints
