# 📊 Monitoring & Alerting Setup Guide

Panduan lengkap untuk setup monitoring, uptime checks, dan Slack alerts.

---

## 🔧 Step 1: Akses Console

Buka link berikut:
- **Monitoring Dashboard**: https://console.cloud.google.com/monitoring?project=nanobananacomic-482111
- **Alerting**: https://console.cloud.google.com/monitoring/alerting?project=nanobananacomic-482111
- **Uptime Checks**: https://console.cloud.google.com/monitoring/uptime?project=nanobananacomic-482111

---

## 📡 Step 2: Buat Uptime Checks

### 2.1 API Backend Health Check

1. Buka: https://console.cloud.google.com/monitoring/uptime/create?project=nanobananacomic-482111
2. Isi form:
   - **Title**: `API Backend Health Check`
   - **Protocol**: HTTPS
   - **Resource Type**: URL
   - **Hostname**: `nanobanana-backend-1089713441636.asia-southeast2.run.app`
   - **Path**: `/health`
   - **Check Frequency**: 5 minutes
   - **Regions**: Asia Pacific, USA
3. Klik **Create**

### 2.2 Worker Service Health Check

1. Buat uptime check baru
2. Isi form:
   - **Title**: `Worker Service Health Check`
   - **Protocol**: HTTPS
   - **Resource Type**: URL
   - **Hostname**: `nanobanana-worker-1089713441636.asia-southeast2.run.app`
   - **Path**: `/health`
   - **Check Frequency**: 5 minutes
3. Klik **Create**

---

## 🔔 Step 3: Setup Slack Notification Channel

### 3.1 Buat Slack Webhook

1. Buka: https://api.slack.com/messaging/webhooks
2. Klik **Create your Slack app** → **From scratch**
3. Nama: `NanoBanana Alerts`, Workspace: [pilih workspace Anda]
4. Di sidebar, klik **Incoming Webhooks** → Toggle **ON**
5. Klik **Add New Webhook to Workspace**
6. Pilih channel (misal: `#alerts` atau `#nanobanana-alerts`)
7. **Copy Webhook URL** (simpan, akan digunakan nanti)

### 3.2 Tambahkan Notification Channel di GCP

1. Buka: https://console.cloud.google.com/monitoring/alerting/notifications?project=nanobananacomic-482111
2. Klik **Edit Notification Channels**
3. Scroll ke **Slack** → Klik **Add New**
4. Masukkan:
   - **Display Name**: `NanoBanana Alerts Slack`
   - **Auth Token**: (paste Webhook URL dari Slack)
   - **Channel Name**: `#alerts` (atau channel yang Anda pilih)
5. Klik **Test** untuk verifikasi → Klik **Save**

---

## 🚨 Step 4: Buat Alert Policies

### 4.1 Uptime Check Failed Alert

1. Buka: https://console.cloud.google.com/monitoring/alerting/policies/create?project=nanobananacomic-482111
2. Klik **Add Condition**
3. Pilih metric:
   - **Resource Type**: Uptime Check URL
   - **Metric**: Check passed
   - **Filter**: `check_id = "api-backend-health-check"` (atau sesuai ID)
4. Configure trigger:
   - **Condition**: Is absent for 5 minutes
5. Add notification channel → Pilih Slack channel
6. **Alert Name**: `API Backend Down Alert`
7. Klik **Create Policy**

### 4.2 High Error Rate Alert

1. Buat policy baru
2. Add Condition:
   - **Resource Type**: Cloud Run Revision
   - **Metric**: Request count
   - **Filter**: `response_code_class != "2xx"`
   - **Aggregation**: Rate, per 5 minutes
3. Trigger: **Above 5%**
4. Add Slack notification channel
5. **Alert Name**: `High Error Rate Alert`
6. Klik **Create Policy**

### 4.3 High Latency Alert

1. Buat policy baru
2. Add Condition:
   - **Resource Type**: Cloud Run Revision
   - **Metric**: Request latencies
   - **Aggregation**: 95th percentile
3. Trigger: **Above 10,000 ms** (10 seconds)
4. Add Slack notification channel
5. **Alert Name**: `High Latency Alert`
6. Klik **Create Policy**

### 4.4 High Memory Usage Alert

1. Buat policy baru
2. Add Condition:
   - **Resource Type**: Cloud Run Revision
   - **Metric**: Container memory utilization
3. Trigger: **Above 90%** for 5 minutes
4. Add Slack notification channel
5. **Alert Name**: `High Memory Usage Alert`
6. Klik **Create Policy**

---

## 📊 Step 5: Buat Custom Dashboard

1. Buka: https://console.cloud.google.com/monitoring/dashboards?project=nanobananacomic-482111
2. Klik **Create Dashboard**
3. Beri nama: `NanoBanana Overview`
4. Tambahkan charts:

### Chart 1: Request Count
- **Widget Type**: Line Chart
- **Resource**: Cloud Run Revision
- **Metric**: Request count
- **Group By**: service_name

### Chart 2: Error Rate
- **Widget Type**: Line Chart
- **Resource**: Cloud Run Revision
- **Metric**: Request count
- **Filter**: response_code_class != "2xx"
- **Aggregation**: Rate

### Chart 3: Latency P95
- **Widget Type**: Line Chart
- **Resource**: Cloud Run Revision
- **Metric**: Request latencies
- **Aggregation**: 95th percentile

### Chart 4: Active Instances
- **Widget Type**: Line Chart
- **Resource**: Cloud Run Revision
- **Metric**: Instance count

### Chart 5: Memory Usage
- **Widget Type**: Line Chart
- **Resource**: Cloud Run Revision
- **Metric**: Container memory utilization

### Chart 6: CPU Usage
- **Widget Type**: Line Chart
- **Resource**: Cloud Run Revision
- **Metric**: Container CPU utilization

---

## 📧 Step 5 (Alternatif): Setup Email Alerts

Jika tidak menggunakan Slack:

1. Buka Notification Channels
2. Klik **Email** → **Add New**
3. Masukkan email (bisa multiple, pisahkan dengan koma)
4. Verifikasi email
5. Gunakan channel ini di alert policies

---

## ✅ Checklist

- [ ] Uptime check API Backend created
- [ ] Uptime check Worker created
- [ ] Slack webhook created
- [ ] Slack notification channel added in GCP
- [ ] Alert: Uptime failed
- [ ] Alert: High error rate
- [ ] Alert: High latency
- [ ] Alert: High memory
- [ ] Dashboard created
- [ ] Test alert sent to Slack

---

## 🔗 Quick Links

| Resource | Link |
|----------|------|
| Monitoring Dashboard | https://console.cloud.google.com/monitoring?project=nanobananacomic-482111 |
| Alerting Policies | https://console.cloud.google.com/monitoring/alerting?project=nanobananacomic-482111 |
| Uptime Checks | https://console.cloud.google.com/monitoring/uptime?project=nanobananacomic-482111 |
| Cloud Logging | https://console.cloud.google.com/logs?project=nanobananacomic-482111 |
| Error Reporting | https://console.cloud.google.com/errors?project=nanobananacomic-482111 |
| Cloud Trace | https://console.cloud.google.com/traces?project=nanobananacomic-482111 |

---

## 🧪 Test Alerts

Untuk test apakah alert bekerja:

```bash
# Test dengan menghentikan service sementara (JANGAN DI PRODUCTION!)
# gcloud run services update nanobanana-backend --min-instances=0 --max-instances=0

# Atau generate error dengan request invalid
curl -X POST https://nanobanana-backend-1089713441636.asia-southeast2.run.app/api/v1/test-error

# Check Slack channel dalam 5-10 menit
```

---

*Last Updated: 2024-12-28*
