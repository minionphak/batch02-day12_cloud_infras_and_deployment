# Day 12 Lab - Câu Trả Lời

> **Khóa học:** AICB-P1 · VinUniversity 2026 — Day 12: Cloud Infra & Production Deployment

---

## Part 1: Localhost vs Production

### Exercise 1.1: Các anti-pattern tìm được

1. **Hardcode API key (`OPENAI_API_KEY`)** — lưu credentials trực tiếp trong source code khiến bất kỳ ai có access vào repo đều đọc được, đồng thời không thể xoay vòng key mà không cần commit code mới.
2. **Hardcode database credentials (`DATABASE_URL`)** — nhúng password DB vào code vi phạm nguyên tắc cấu hình theo môi trường và có nguy cơ lộ quyền truy cập production ngay khi chia sẻ repo.
3. **In secret ra stdout (`print(f"... Using key: {OPENAI_API_KEY}")`)** — việc in secret tạo ra văn bản thuần trong mọi hệ thống thu thập log, ai có quyền xem log đều thấy được.
4. **Không có health/readiness endpoint** — thiếu `/health` và `/ready` khiến platform không thể phát hiện agent bị crash để restart, hoặc không biết khi nào an toàn để route traffic vào.
5. **Binding vào localhost (`host="localhost"`)** — chỉ lắng nghe trên loopback interface; bên trong container, không có gì bên ngoài (kể cả proxy của platform) có thể kết nối được. Production cần `0.0.0.0`.
6. **Port cố định (`port=8000` trong code)** — Railway/Render inject port qua env var `PORT`; hardcode port làm deployment thất bại.
7. **`reload=True` trong production** — debug auto-reload lãng phí tài nguyên, theo dõi filesystem và là lỗ hổng bảo mật.
8. **`print()` thay vì structured logging** — log không có cấu trúc không thể lọc, phân tích hay cảnh báo bằng công cụ log.
9. **Không có graceful shutdown** — thiếu lifespan/SIGTERM handler khiến các request đang xử lý bị ngắt đột ngột mỗi khi deploy hoặc restart.

### Exercise 1.3: Bảng so sánh

| Tính năng | Develop | Production | Tại sao quan trọng? |
| :--- | :--- | :--- | :--- |
| Config | Hardcode | Env vars (Settings) | Tách biệt code khỏi môi trường; cùng một image chạy được ở mọi nơi |
| Secrets | Hardcode | Env vars, kiểm tra khi khởi động | Ngăn lộ credentials; fail-fast nếu thiếu |
| Health check | Không có | `GET /health` | Platform restart container khi bị crash |
| Readiness check | Không có | `GET /ready` | Load balancer chỉ route traffic khi dependencies đã sẵn sàng |
| Logging | `print()` | Structured JSON | Có thể phân tích bằng Datadog/Loki; không log secret |
| Shutdown | Đột ngột | Graceful (SIGTERM + lifespan) | Các request đang xử lý hoàn thành trước khi tắt |
| Host binding | `localhost` | `0.0.0.0` | Có thể truy cập từ ngoài container |
| Port | Cố định 8000 | Env var `PORT` | Platform inject port động |
| CORS | Không/mở | Restricted origins | Chặn cross-origin access không được phép |
| Debug/reload | Luôn bật | Chỉ khi `DEBUG=true` | Tối ưu hiệu năng và bảo mật trong production |

Những cải tiến này tuân theo phương pháp **12-Factor App** — đặc biệt là **Config** (lưu cấu hình trong môi trường), **Disposability** (khởi động nhanh, shutdown có kiểm soát), và **Logs** (coi log là event stream). Tách code khỏi cấu hình và làm cho ứng dụng có thể quan sát được là điều kiện để deploy lên cloud.

---

## Part 2: Docker

### Exercise 2.1: Câu hỏi về Dockerfile

1. **Base image là gì?** `python:3.11` — bản phân phối Python đầy đủ, khoảng 1 GB, bao gồm build tools, headers và các thành phần khác.
2. **Working directory là gì?** `/app` — thư mục gốc cho tất cả các lệnh COPY/RUN/CMD tiếp theo.
3. **Tại sao COPY requirements.txt trước?** Docker cache từng layer. Nếu chỉ source code thay đổi, layer `pip install` tốn kém sẽ được dùng lại từ cache; dependencies chỉ được cài lại khi `requirements.txt` thực sự thay đổi. Cách này giảm đáng kể thời gian build lại.
4. **CMD vs ENTRYPOINT khác nhau thế nào?** `CMD` cung cấp lệnh/tham số mặc định có thể dễ dàng override khi chạy `docker run`. `ENTRYPOINT` cố định executable để container hoạt động như một binary; tham số runtime được nối vào sau. Dùng `CMD` cho lệnh mặc định mà người dùng có thể thay, dùng `ENTRYPOINT` khi container phải luôn chạy một chương trình cụ thể (có thể kết hợp `CMD` làm tham số mặc định).

### Exercise 2.3: Multi-stage build

- **Stage 1 (builder):** dựa trên `python:3.11-slim`, cài build dependencies (`gcc`, `libpq-dev`) và chạy `pip install --user` để toàn bộ packages nằm trong `/root/.local`, dễ dàng copy sang stage sau.
- **Stage 2 (runtime):** bắt đầu từ `python:3.11-slim` sạch, chỉ copy `/root/.local` (các packages đã cài) và source code, tạo user `appuser` không phải root, và chạy ứng dụng.

Tại sao image nhỏ hơn và an toàn hơn:
1. **Slim base** — không có docs, không có utilities thừa.
2. **Không có build tools trong image cuối** — `gcc` và dev headers chỉ tồn tại trong builder stage bị loại bỏ, giảm kích thước và bề mặt tấn công.
3. **User không phải root** — least privilege; nếu process bị compromise thì không phải root trong container.

### So sánh kích thước image (đo bằng `docker images`)

- Develop (single-stage, `python:3.11` đầy đủ): **1660 MB (1.66 GB)**
- Production (multi-stage, `python:3.12-slim`, image final project): **291 MB**
- Chênh lệch: **~82% nhỏ hơn**

### Exercise 2.4: Kiến trúc Docker Compose

Stack chạy trên private bridge network (`internal`); các services giao tiếp với nhau qua Docker service-name DNS. Nginx là điểm vào công khai duy nhất (ports 80/443): nó terminate HTTP, áp dụng IP rate limit (10 r/s, burst 20 → 429 JSON), thêm security headers, và proxy đến upstream `agent`. FastAPI `agent` không publish host port — chỉ có thể truy cập qua nginx — và khai báo healthcheck cùng `depends_on: condition: service_healthy` để chỉ khởi động sau khi Redis/Qdrant đã sẵn sàng. Redis (256 MB, `allkeys-lru`) lưu sessions và rate-limit state; Qdrant là vector DB cho RAG. Secrets đến từ `env_file` được gitignore, và named volumes giữ dữ liệu Redis/Qdrant qua các lần restart.

```text
                ┌──────────┐
   client ───▶  │  nginx   │  :80 (rate limit, security headers)
                └────┬─────┘
                     ▼  round-robin (Docker DNS)
                ┌──────────┐
                │  agent   │  FastAPI (không publish port)
                └──┬───┬───┘
                   ▼   ▼
             ┌───────┐ ┌────────┐
             │ redis │ │ qdrant │
             └───────┘ └────────┘
              (internal bridge network, named volumes)
```

---

## Part 3: Cloud Deployment

### Exercise 3.1/3.2: Deploy

- Platform: **Render** (Blueprint deploy qua `render.yaml` — web service từ Dockerfile + managed Key Value/Redis instance)
- URL: _xem [DEPLOYMENT.md](DEPLOYMENT.md)_
- Screenshot: [screenshots/](screenshots/)

**Sự khác nhau giữa `render.yaml` và `railway.toml`:** Blueprint của Render là declarative infrastructure — nó định nghĩa *tất cả* services (web + Redis), plans, env vars, và cross-service references (`fromService` inject Redis connection string); deploy được kích hoạt bằng cách kết nối GitHub repo. `railway.toml` của Railway chỉ cấu hình build/deploy behavior (builder, healthcheck, restart policy) cho một service; services và variables được tạo qua CLI (`railway init`, `railway variables set`, `railway up`).

---

## Part 4: API Security

### Exercise 4.1: API Key authentication

Key được validate trong FastAPI dependency `verify_api_key`, đọc header `X-API-Key` qua `APIKeyHeader`. Thiếu header trả về **401 Unauthorized**; sai key trả về **403 Forbidden** (so sánh dùng `secrets.compare_digest` để tránh timing attack). Xoay vòng key trong production: cập nhật env var `AGENT_API_KEY` và rolling restart; để tránh downtime phía client, có thể chấp nhận cả key cũ lẫn mới trong giai đoạn chuyển đổi. Key không bao giờ được commit — chỉ có `.env.example` với placeholder.

### Exercise 4.2: JWT flow

1. Client gửi credentials đến `POST /token`.
2. Server xác minh username/password.
3. Server ký JWT (HS256) với payload `sub` (user), `role`, `iat`, và `exp` (hết hạn sau 60 phút).
4. Client gửi `Authorization: Bearer <token>` trong mỗi request tiếp theo.
5. Server xác minh signature và thời hạn **stateless** — không cần truy vấn DB cho mỗi request.

Auth stateless có thể scale vì bất kỳ instance nào giữ `JWT_SECRET` dùng chung đều có thể verify bất kỳ token nào. `ExpiredSignatureError` → 401 "Token expired"; `InvalidTokenError` → 403 "Invalid token".

### Exercise 4.3: Rate limiting

Cài đặt trong course là **Sliding Window Counter**: một `deque` lưu timestamps theo từng user; timestamps cũ hơn cửa sổ 60 giây được xóa mỗi lần kiểm tra; nếu đếm đạt limit thì raise **429** với headers `Retry-After`, `X-RateLimit-Limit/Remaining/Reset`. Limit là **10 requests/phút** cho user; admin bypass qua một `RateLimiter` instance riêng cho phép 100 req/phút, được chọn theo JWT role. Lưu ý với production: limiter in-memory không hoạt động khi có nhiều instances (mỗi instance có counter riêng), nên final project chuyển sliding window sang **Redis ZSET** được chia sẻ bởi tất cả replicas.

### Exercise 4.1–4.3: Kết quả test (final project, qua nginx)

```text
# không có key
POST /ask                          → HTTP 401 {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# key hợp lệ
POST /ask {"user_id":"u1", ...}    → HTTP 200 {"answer": "...", "served_by": "instance-40e63b",
                                                "rate_limit": {"limit": 10, "remaining": 9}, ...}

# 12 request liên tiếp, cùng user (limit = 10/phút)
200,200,200,200,200,200,200,200,200,200,429,429
```

### Exercise 4.4: Cài đặt cost guard

Mỗi request ước tính chi phí LLM từ số lượng token (≈4 ký tự/token) theo giá tham chiếu GPT-4o-mini ($0.15/1M input, $0.60/1M output). Chi tiêu được theo dõi **theo user theo tháng** trong Redis tại key `budget:{user_id}:{YYYY-MM}` dùng `INCRBYFLOAT`, với TTL 32 ngày để key tự hết hạn sau tháng. Trước khi gọi LLM, guard kiểm tra `hiện_tại + ước_tính > $10` và raise **402 Payment Required**; khi đạt 80% budget thì log warning có cấu trúc. Sau khi gọi, usage thực tế được ghi lại.

Kết quả test:

```text
# Redis: SET budget:budget-test:2026-06 10.5
POST /ask → HTTP 402 {"detail":{"error":"Monthly budget exceeded","used_usd":10.5,
                                 "budget_usd":10.0,"resets_at":"first day of next month (UTC)"}}
```

So với `CostGuard` in-memory trong course (daily $1/user + $10 global → 503): Redis là bắt buộc để đúng với nhiều instance (tất cả replicas thấy cùng một mức chi tiêu) và bền vững qua các lần restart/redeploy — counter in-memory reset về $0 mỗi khi container bị thay thế.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health & readiness checks

```python
@app.get("/health")
async def health():                       # liveness probe
    return {"status": "ok", "instance": INSTANCE_ID}

@app.get("/ready")
async def ready():                        # readiness probe
    if not redis_ping():
        raise HTTPException(status_code=503, detail="Not ready: Redis unavailable")
    return {"ready": True, "instance": INSTANCE_ID}
```

Liveness trả lời "process còn sống không?" — khi fail, platform **restart** container. Readiness trả lời "có thể phục vụ traffic ngay không?" — khi fail, load balancer **ngừng route** đến instance đó (không restart), ví dụ trong lúc khởi động hoặc Redis bị lỗi.

### Exercise 5.2: Graceful shutdown

Cloud platform gửi `SIGTERM` và chờ grace period (~10–30 giây) trước khi `SIGKILL`. uvicorn xử lý `SIGTERM` bằng cách từ chối kết nối mới trong khi drain các request đang xử lý; handler của chúng ta (đăng ký với `signal.signal(SIGTERM, ...)`) log sự kiện và chuyển tiếp đến handler của uvicorn, đồng thời lifespan shutdown block trong FastAPI chạy cleanup.

Hai lỗi thực tế gặp phải và đã sửa:
1. **Shell-form CMD**: với `CMD ["sh", "-c", "uvicorn ..."]`, `sh` là PID 1 và **không** forward SIGTERM — uvicorn bị kill thay vì drain. Sửa: dùng `exec uvicorn ...` để uvicorn trở thành PID 1.
2. **Ghi đè handler**: gọi `signal.signal(SIGTERM, mine)` trực tiếp sẽ *thay thế* handler của uvicorn; chúng ta lưu handler trước đó và chain đến nó.

**Kết quả test:** `docker stop` (gửi SIGTERM) hoàn thành trong ~1.3 giây với uvicorn log `Shutting down → Waiting for application shutdown → Application shutdown complete → Finished server process [1]` — drain sạch thay vì timeout 10 giây + SIGKILL.

### Exercise 5.3: Stateless design

```python
# ❌ anti-pattern: state nằm trong memory của một process
conversation_history = {}

# ✅ đúng: state nằm trong Redis, chia sẻ bởi tất cả instances
redis.setex(f"session:{session_id}", 3600, json.dumps(history))  # giới hạn 20 messages
```

Với N instances được scale sau load balancer, request thứ 2 của một conversation có thể đến một instance khác với request thứ 1. State in-memory vô hình với các instances khác và bị mất mỗi khi restart/redeploy. Redis tập trung hóa state để bất kỳ replica nào cũng có thể phục vụ bất kỳ request nào.

### Exercise 5.4: Load balancing

`docker compose up --scale agent=3` khởi động 3 replicas của service `agent`. Upstream `server agent:8000` của Nginx giải quyết qua DNS nội bộ của Docker, round-robin qua các replicas. Mỗi response mang `served_by: <instance_id>` chứng minh sự phân tán; nếu một instance chết, healthcheck của nó fail và traffic tiếp tục đến các instance còn lại trong khi restart policy đưa nó lên lại.

Phân phối đo được qua 6 requests:

```text
instance-7851b4, instance-25ee50, instance-40e63b, instance-7851b4, instance-25ee50, instance-40e63b
```

### Exercise 5.5: Test stateless

Test tạo một conversation (lượt 1), kill đúng instance đã phục vụ nó, sau đó tiếp tục session đó (lượt 2). Test pass nếu history vẫn còn và turn counter tăng lên — chứng minh state nằm trong Redis, không phải trong process đã bị kill.

**Kết quả (final project):**

```text
turn 1: served_by=instance-25ee50  session=fda867fb-...
docker kill day12-submission-agent-2        # instance đã phục vụ turn 1
turn 2: served_by=instance-40e63b  turn=2   # instance khác, cùng conversation
GET /chat/{session}/history → count=4       # full history còn nguyên trong Redis
```
