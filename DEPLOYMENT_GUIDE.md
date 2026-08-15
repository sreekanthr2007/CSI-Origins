# TRACE Deployment & Operations Guide

This guide provides operational instructions for deploying and running the **TRACE** (*Targeted Routing & Account Cluster Extraction*) system across local containers, bare-metal servers, and cloud infrastructure.

---

## 1. Prerequisites

- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+
- **Node.js**: Version 18+ (for local frontend development)
- **Python**: Version 3.11+ (for local backend development)

---

## 2. One-Command Local Deployment

To run the complete system (Backend, Frontend, and Nginx proxy) via Docker Compose:

```bash
# 1. Clone the repository
git clone https://github.com/your-org/csi-origins-trace.git
cd csi-origins-trace

# 2. Build and launch all services in detached mode
docker-compose up -d --build

# 3. Verify health status of running services
docker-compose ps
```

Once running, access:
- **Central Intelligence Dashboard**: `http://localhost/central`
- **Bank Compliance Portal (SBI)**: `http://localhost/bank/bank_sbi`
- **Backend API & Swagger UI**: `http://localhost:8000/docs`
- **Health Check Endpoint**: `http://localhost:8000/health`

---

## 3. Production Cloud Deployment (AWS / Azure / GCP)

### AWS Architecture (ECS / Fargate + ALB)
1. **Application Load Balancer (ALB)**:
   - Terminate SSL/TLS with ACM certificate (`https://trace.bank-consortium.org`).
   - Route `/api/*` traffic to the Backend Target Group (Port 8000).
   - Route `/*` traffic to Frontend Nginx Target Group (Port 80).
2. **Backend Service (ECS Fargate)**:
   - Minimum 2 tasks (2 vCPU, 4GB RAM) with horizontal auto-scaling based on CPU utilization (>70%).
   - Store `HMAC_STANDING_KEY` and `EPHEMERAL_KEY_SECRET` in **AWS Secrets Manager**.
3. **Database (Amazon Aurora PostgreSQL)**:
   - Configure Multi-AZ replication for automated failover.
   - Point `DATABASE_URL` in `.env.production` to the Aurora Cluster endpoint.

---

## 4. Environment Configuration

Copy the production template:
```bash
cp backend/.env.production backend/.env
```

Ensure the following critical environment variables are set:
- `HMAC_STANDING_KEY`: 64-character hex cryptographic key
- `EPHEMERAL_KEY_SECRET`: 64-character hex KDF master key
- `DATABASE_URL`: Production PostgreSQL or SQLite connection string
- `CORS_ORIGINS`: Array of allowed domain origins

---

## 5. Verification & Monitoring

Run the automated deployment verification suite:
```bash
python backend/scripts/verify_deployment.py
```

### Monitoring & Telemetry:
- **Health Endpoint**: `GET /health` polled every 15 seconds.
- **Log Aggregation**: Structured JSON logs stream to stdout for ingestion by Datadog, Prometheus, or CloudWatch.
- **Privacy Auditing**: Periodic execution of `test_privacy_audit.py` to confirm zero PII leaks.
