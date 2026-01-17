# MamaStoria Cloud Infrastructure Configuration

## Overview

This document contains the current cloud infrastructure configuration for MamaStoria application deployed on Google Cloud Platform.

---

## 1. Cloud Run Services

### 1.1 nanobanana-backend (Main API)

| Parameter             | Value                                                            |
| --------------------- | ---------------------------------------------------------------- |
| **Service Name**      | nanobanana-backend                                               |
| **Region**            | us-central1 (Iowa)                                               |
| **URL**               | https://nanobanana-backend-1089713441636.us-central1.run.app     |
| **CPU**               | 4 vCPU                                                           |
| **Memory**            | 4 GB                                                             |
| **Concurrency**       | 100 requests/instance                                            |
| **Min Instances**     | 2 (always warm)                                                  |
| **Max Instances**     | 50                                                               |
| **Timeout**           | 300 seconds                                                      |
| **CPU Throttling**    | Disabled                                                         |
| **Startup CPU Boost** | Enabled                                                          |

**Capacity:** 50 × 100 = **5,000 concurrent requests**

---

### 1.2 nanobanana-worker (Background Jobs)

| Parameter         | Value                     |
| ----------------- | ------------------------- |
| **Service Name**  | nanobanana-worker         |
| **Region**        | asia-southeast2 (Jakarta) |
| **CPU**           | 2 vCPU                    |
| **Memory**        | 4 GB                      |
| **Concurrency**   | 1 request/instance        |
| **Min Instances** | 0                         |
| **Max Instances** | 50                        |
| **Timeout**       | 300 seconds               |

**Purpose:** Handles long-running comic generation tasks

---

### 1.3 smart-crop-worker (OpenCV Panel Cropping)

| Parameter         | Value                                                                               |
| ----------------- | ----------------------------------------------------------------------------------- |
| **Service Name**  | smart-crop-worker                                                                   |
| **Type**          | Cloud Functions Gen2                                                                |
| **Region**        | asia-southeast2 (Jakarta)                                                           |
| **URL**           | https://asia-southeast2-nanobananacomic-482111.cloudfunctions.net/smart-crop-worker |
| **CPU**           | 1 vCPU                                                                              |
| **Memory**        | 2 GB                                                                                |
| **Concurrency**   | 10 requests/instance                                                                |
| **Min Instances** | 0                                                                                   |
| **Max Instances** | 100                                                                                 |
| **Timeout**       | 300 seconds                                                                         |

**Capacity:** 100 × 10 = **1,000 concurrent cropping operations**

---

## 2. Database Configuration

### Cloud SQL (PostgreSQL)

| Parameter         | Value                                                          |
| ----------------- | -------------------------------------------------------------- |
| **Instance Name** | cloudsql-nanobanana-us                                         |
| **Connection**    | nanobananacomic-482111:us-central1:cloudsql-nanobanana-us      |
| **Region**        | us-central1                                                    |
| **Type**          | PostgreSQL                                                     |

---

## 3. Storage Configuration

### Google Cloud Storage

| Parameter       | Value                     |
| --------------- | ------------------------- |
| **Bucket Name** | mamastoria-storage        |
| **Region**      | asia-southeast2           |
| **Access**      | Public (for comic assets) |

**Storage Paths:**

- `comics/panels/{comic_id}/` - Panel images
- `comics/videos/{comic_id}/` - Generated videos
- `comics/grids/{comic_id}/` - Full grid images
- `users/avatars/` - User profile pictures

---

## 4. External Services

### Google Cloud Text-to-Speech

| Parameter         | Value              |
| ----------------- | ------------------ |
| **Voice**         | id-ID-Wavenet-A    |
| **Language**      | Indonesian (id-ID) |
| **Gender**        | Female             |
| **Speaking Rate** | 0.9                |

### Vertex AI (Image Generation)

| Parameter    | Value                   |
| ------------ | ----------------------- |
| **Location** | us-central1             |
| **Model**    | gemini-3-pro-image-preview |

---

## 5. Capacity Summary

### For 1,000 Concurrent Users

| Service          | Capacity         | Status        |
| ---------------- | ---------------- | ------------- |
| API Requests     | 5,000 concurrent | ✅ Sufficient |
| Panel Cropping   | 1,000 concurrent | ✅ Sufficient |
| Comic Generation | 50 concurrent    | ✅ Sufficient |

### Response Times (Warm)

| Endpoint     | P95 Latency |
| ------------ | ----------- |
| List Comics  | < 150ms     |
| Comic Detail | < 130ms     |
| Comic Panels | < 120ms     |
| List Styles  | < 250ms     |
| List Genres  | < 125ms     |

---

## 6. Cost Estimation

### Monthly Costs (Estimated)

| Service             | Configuration   | Est. Cost  |
| ------------------- | --------------- | ---------- |
| Cloud Run (backend) | 2 min instances | ~$50/month |
| Cloud Run (worker)  | Pay per use     | ~$20/month |
| Cloud Functions     | Pay per use     | ~$10/month |
| Cloud SQL           | db-f1-micro     | ~$10/month |
| Cloud Storage       | ~50GB           | ~$5/month  |
| Vertex AI           | Per image       | Variable   |
| Text-to-Speech      | Per character   | Variable   |

**Base Infrastructure:** ~$95/month (excluding AI usage)

---

## 7. Security Configuration

### Authentication

- JWT-based authentication
- Google OAuth integration
- Token expiry: 24 hours

### Network

- HTTPS only
- CORS enabled for app.mamastoria.com

---

## 8. Environment Variables

### nanobanana-backend

| Variable                   | Description                      |
| -------------------------- | -------------------------------- |
| USE_CLOUD_SQL_CONNECTOR    | Enable Cloud SQL connector       |
| CLOUD_SQL_CONNECTION_NAME  | Cloud SQL instance connection    |
| DB_USER                    | Database user                    |
| DB_PASS                    | Database password                |
| DB_NAME                    | Database name                    |
| SECRET_KEY                 | JWT signing key                  |
| SMART_CROP_SERVICE_URL     | Smart crop function URL          |
| VERTEX_LOCATION            | Vertex AI region                 |
| GCS_BUCKET_NAME            | Storage bucket name              |


