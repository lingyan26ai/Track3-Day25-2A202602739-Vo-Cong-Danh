# Lab 25B — Report

**Họ tên / nhóm:** Võ Công Danh — MSV 2A202602739  **Commit:** `3e4fa37fe924fb6f4b7c10be6ada49e83e3e4016`  **Điểm tự động (`make grade`):** 84 / 88 (4 điểm còn lại là dữ liệu SLO ẩn do giảng viên chấm; bản public đã PASS)

> Số liệu lấy từ `reports/gameday/*.json`, `reports/cache/*.json`, `reports/workflows.json`, `reports/slo.json`, `reports/scoreboard.json`
> (seed mặc định của `make`, tức `seed: 25` trong config). Điểm tự động `make grade --seeds 25,26,27` và thêm 10 seed khác (1–10) đều PASS cả 6 băng + C1.

## 1. Kết quả Game Day (naive vs của bạn)

| Băng | Client | availability | p95 (s) | amplification | retry_ratio | cost/turn | recovery (s) | PASS? |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| G1 | naive | 0,7194 | 7,16 | 7,74 | 6,738 | 2,163 | 4,0 | ❌ (availability, retry-after: 36 027 vi phạm, amplification) |
| G1 | yours | 1,0000 | 4,78 | 1,06 | 0,002 | 2,130 | 0,0 | ✅ (0 vi phạm retry-after) |
| G2 | naive | 0,4560 | 15,03 | 9,90 | 8,904 | 4,627 | 155,0 | ❌ (availability, amplification, recovery) |
| G2 | yours | 1,0000 | 11,02 | 1,04 | 0,004 | 2,128 | 0,0 | ✅ (primary share sau restore = 1,0) |
| G3 | naive | 1,0000 | 4,77 | 1,16 | 0,164 | 2,328 | 0,0 | ❌ (retry_ratio 0,164 > 0,10) |
| G3 | yours | 1,0000 | 4,74 | 1,05 | 0,033 | 2,131 | 0,0 | ✅ |
| G4 | naive | 1,0000 | 13,76 | 1,00 | 0,004 | 2,008 | 0,0 | ❌ (p95 13,76 > 10) |
| G4 | yours | 1,0000 | 5,58 | 1,01 | 0,002 | 2,082 | 0,0 | ✅ |
| G5 | naive | 0,3699 | 5,36 | 17,03 | 16,03 | 2,124 | – | ❌ (9 149 retry trên lỗi 400, availability) |
| G5 | yours | 0,8179 | 5,48 | 1,00 | 0,002 | 2,504 | – | ✅ (0 retry lỗi 400, 0 failover thừa) |
| G6 | naive | 0,5170 | 4,84 | 12,34 | 11,344 | 2,009 | 0,0 | ❌ (availability) |
| G6 | yours | 1,0000 | 5,95 | 1,06 | 0,023 | 2,141 | 0,0 | ✅ (0 incompatible route) |

Naive 0/6 băng, của tôi 6/6 băng (cũng 6/6 trên seed 25, 26, 27 và 1–10). Điểm mỏng nhất: G5 availability 0,818 so với ngưỡng 0,78 — gần như toàn bộ phần thiếu là 60% request malformed trong 2 phút mà không client nào cứu được.

## 2. Cấu hình client và lý do

| Tham số | Giá trị | Vì sao (dựa trên băng nào, số liệu nào) |
|---|---:|---|
| attempt_timeout_s | 8,0 | **G6**: `alpha-eu` treo. Timeout 30 → availability 0,9488 (FAIL, 106 lượt `deadline`); 8 → 1,000. Timeout phải ≥ đuôi bình thường (p95 cả lượt 2 call + tool ≈ 4,7 s) và đủ ngắn để ≥ 2–3 bước fail over lọt trong deadline 30 s của user. 8 s cũng để `slow_call_s = 5` kịp phát hiện call chậm *trước* khi timeout. (Thử 4 s: G2 p95 còn 4,9 s nhưng G6 rớt 1 call — xem mục 7.) |
| max_attempts_per_provider | 2 | **G3**: lỗi 500 ngẫu nhiên 30%. 1 lần thử: retry_ratio 0,000; 2 lần: 0,033; 3 lần: 0,037 — đều PASS. Chọn 2 (1 retry): rẻ nhất để vượt lỗi tạm thời trên *cùng model* (cost 1,0) thay vì sang `beta` (cost 1,4); retry thứ 3 chỉ tăng tải lên provider đang yếu. |
| backoff_base_s / cap_s | 0,25 / 4,0 | Full jitter `U(0, min(cap, base·2^(n-1)))`: retry đầu chỉ chờ ≤ 0,25 s vì user chỉ chờ 30 s; cap 4 s chặn khi tăng `max_attempts`. Khi có `retry_after`: `retry_after + U(0, 0,25)` → **G1: 0 vi phạm retry-after** (naive: 36 027) và 429 không bị "đồng bộ lại" cùng một giây. |
| retry_budget_ratio | 0,1 | **G3**: retry_ratio 0,033 ≤ 0,10. Thí nghiệm 1: khi breaker hỏng, tắt budget làm G3 retry_ratio 0,068 → 0,158 (FAIL). 10% = trần retry theo tổng traffic, bất kể sự cố. |
| retry_budget_min_per_s / max_tokens | 0,5 / 20 | Hồi 0,5 token/s để lúc vắng traffic vẫn retry được; trần 20 token ≈ một đợt lỗi ngắn (~3 s ở 7,5 call/s) rồi bị kẹp về tỷ lệ 10%. |
| breaker.window_size / min_calls | 20 / 10 | Mỗi provider nhận ~7,5 call/s ⇒ cửa sổ 20 đầy trong ~3 s, `min_calls=10` cho phép trip sau ≈ 1,5 s lỗi dày đặc (**G2**: recovery 0,0 s) nhưng không trip vì 2–3 lỗi lẻ. |
| breaker.failure_rate_threshold | 0,5 | **G3** (30% lỗi 500) *không được* trip: breaker đóng, `alpha` vẫn gánh 70% request thành công, primary share 1,0, cost/turn 2,131 (so 2,0 bình thường). **G2/G6** (≥ 75–100% lỗi) vượt xa 0,5 → trip. |
| breaker.slow_call_s | 5,0 | **G4**: `alpha` chậm thêm 5 s, không có lỗi (~6,2 s/call). `slow_call_s = 8` → p95 13,77 (FAIL, y hệt naive 13,76); `= 5` → p95 5,58 vì breaker coi call chậm là xấu và chuyển sang `alpha-eu`. |
| breaker.open_duration_s | 10 | Cân bằng hai phía: quá ngắn → đập vào provider đang hồi phục; quá dài → chậm quay về primary. Đo: 10 s → primary share sau restore 1,0 ở G2/G3/G4/G6, 0,916 ở G1; 30 s cũng PASS G2/G6 (chưa đo primary share) nhưng theo cơ chế sẽ quay về primary muộn hơn. Mỗi lần mở lại chỉ tốn tối đa 2 probe nên chi phí thăm dò không đáng kể. |
| breaker.half_open_max_probes / successes | 2 / 2 | Tối đa 2 request đang bay khi HALF-OPEN (không có thundering herd; xem `test_half_open_limits_concurrent_probes`: 50 request đồng thời chỉ 2 được qua); cần 2 probe tốt liên tiếp để đóng, tránh "đóng nhầm" sau một probe may mắn. |
| quota_cooldown_s | 300 | **G5**: `insufficient_quota` không tự hết sau vài giây. Cooldown 300 s chia sẻ cho mọi call ⇒ 0 failover thừa, availability 0,818. |

Sơ đồ quyết định của `on_error`:

```
loại lỗi          ghi breaker?        retry cùng provider?              failover?          cooldown?
----------------  ------------------  --------------------------------  -----------------  ----------------------------
CLIENT_ERROR 4xx  release (không ghi) KHÔNG                             KHÔNG -> GiveUp    không
QUOTA_EXHAUSTED   release             KHÔNG                             CÓ, ngay (delay 0) quota_cooldown_s (300 s)
RATE_LIMITED 429  release             KHÔNG                             CÓ, ngay (delay 0) retry_after + jitter, dùng chung
OVERLOADED 503/529 on_failure         CÓ nếu tries<max, budget cho phép, CÓ khi hết lượt   không (breaker lo)
SERVER_ERROR 5xx  on_failure          và vừa deadline, breaker chưa OPEN hoặc budget cạn
TIMEOUT           on_failure
(hết ladder)      –                   chờ cooldown rate-limit ngắn (<= 5 s) nếu còn deadline, nếu không GiveUp
```

## 3. Ba thí nghiệm

1. **Retry budget là lớp phòng thủ cuối.** Cấu hình breaker sai (`min_calls: 1e9`, `max_attempts_per_provider: 5`).
   Giữ budget: G2 availability 0,9987, amplification 1,381, retry_ratio 0,058, recovery 0,0 s; G3 retry_ratio 0,068 (PASS cả hai).
   Tắt budget: G2 availability **0,9776**, amplification **1,570**, retry_ratio **0,355**, recovery **25 s**, 53 lượt `deadline`; G3 retry_ratio **0,158** → FAIL (> 0,10).
   Khi breaker *hoạt động đúng* thì hai cấu hình gần như giống nhau (G2 amplification 1,038 cả hai; G3 retry_ratio 0,033 vs 0,024) — breaker đã cắt tải vào provider hỏng. Vẫn nên có cả hai vì chúng bảo vệ khác nhau: breaker là trạng thái *theo provider*, cần đủ `min_calls` để biết và có thể cấu hình sai/chưa kịp trip (G3 chỉ 30% lỗi nên breaker cố tình không trip), còn budget là trần *toàn cục, không trạng thái* trên tổng retry, đúng cho mọi nguyên nhân. Một lớp bắt sự cố đã biết, lớp kia bắt cái không ai lường trước.
2. **`attempt_timeout_s: 30`.** G6: availability tụt từ **1,0000 → 0,9488** (FAIL; `give_up_reasons`: `deadline` 106, `no_provider_available` 16) vì mỗi lượt gặp `alpha-eu` treo phải đợi 30 s mới dám fail over, trong khi user chỉ chờ 30 s. Trong lúc đó p95 lại *giảm* 5,95 → 5,36 s: đó là survivorship bias — `latency_p95_s` chỉ tính lượt thành công, các lượt treo rồi hết hạn biến mất khỏi mẫu. G4 gần như không đổi (availability 1,0; p95 5,58 → 5,64) vì G4 không có lỗi nào và mọi call xong sau ~6,2 s < 8 s nên timeout không bao giờ kích hoạt, việc xử lý do `slow_call_s` của breaker. Timeout "đúng" dựa trên **deadline của user chia cho số bước fail over cần có** (ở đây 30 s / ≥ 3 provider cho tool call), rồi kiểm tra rằng nó cao hơn p99 lúc bình thường để không cắt call khỏe — không phải một con số "cho an toàn".
3. **Bỏ lọc tool calling khỏi `ladder()`.** G6: `incompatible_routes` = **247**, availability 1,0000 → **0,8964**, FAIL (`give_up_reasons: incompatible_model_output` = 247). Nói với PM: "247 khách (10,4% lượt hôm đó) bấm yêu cầu hoàn tiền và không có gì xảy ra, vì hệ thống đã giao việc 'gọi công cụ' cho một model rẻ (0,2 so với 1,0) *không biết gọi công cụ*. Dashboard của nhà cung cấp vẫn xanh — 200 OK, nhanh, rẻ — nhưng sản phẩm hỏng." Tiết kiệm chi phí mà không kiểm tra năng lực là tiết kiệm sai chỗ.

## 4. Workflow hoàn tiền

| Executor | completion | crashes | duplicate refunds | duplicate emails | lost refunds | overpaid | wasted LLM / crash |
|---|---:|---:|---:|---:|---:|---:|---:|
| naive | 1,000 | 81 | 128 | 81 | 0 | 14 967,00 $ (1 496 700 cent) | 1,123 |
| yours | 1,000 | 66 | 0 | 0 | 0 | 0 | 0,303 |

Yours: 500 phiên → đúng 500 lần payment thực thi, 2 500 lần ghi checkpoint (5 step × 500).

**Vì sao chỉ idempotency key là chưa đủ?** Key chỉ chặn tác dụng phụ bị lặp ở *service*; worker mới sinh ra sau crash không có trí nhớ nên vẫn chạy lại từ đầu: tính lại `classify`/`lookup` và gọi lại LLM tốn tiền (naive: 1,123 call LLM lãng phí mỗi crash, chỉ key thì vẫn lãng phí), và phụ thuộc vào việc mọi step đều có endpoint idempotent còn lưu kết quả. **Vì sao chỉ checkpoint là chưa đủ?** Khi tiền đã đi nhưng phản hồi mất (`ServiceTimeout`) hoặc worker chết ngay sau đó (`WorkerCrash`), chưa kịp ghi checkpoint thì worker mới thấy "chưa làm" và gọi payment lần nữa *không có key* → hoàn tiền hai lần (naive: 128 lần trùng, 81 email trùng, thừa 14 967 $). **Ghi checkpoint *trước* khi gọi payment** thì ngược lại: crash giữa checkpoint và lời gọi → worker mới thấy step "đã xong", bỏ qua → khách **không bao giờ được hoàn tiền** (lost refund) trong khi hệ thống tin là xong. Vì vậy thứ tự đúng là: thực hiện với key ổn định `refund-agent/<session>/<step>` → *sau đó* mới ghi checkpoint; at-least-once + idempotent = exactly-once effect.

## 5. Alerting & error budget

| Sự cố | Mong đợi | Naive alerter (5 phút > 5%) | Burn-rate alerter | Độ trễ phát hiện |
|---|---|---|---|---:|
| checkout_bug | page | page (trễ 1 phút) | page — `fast_burn_2pct_1h` | 27 phút (hạn 35) |
| provider_outage | page | page (0 phút) | page — `fast_burn_2pct_1h` | 4 phút (hạn 8) |
| deploy_blip | none | **page oan** | không page | – |
| slow_leak | ticket | **không phát hiện** | ticket — `budget_leak_10pct_3d`, không page | 1 337 phút ≈ 22,3 h (hạn 30 h) |
| degraded_evening | page | page (trễ 214 phút) | page — `slow_burn_5pct_6h` | 291 phút (hạn 330) |
| night_spike | none | **page oan** | không page | – |
| small_bump | none | **page oan** | không page | – |

Naive: 7 page, 3 false page, bỏ sót slow_leak → FAIL. Burn-rate: 3 page + 1 ticket, 0 false page → PASS.

Error budget 30 ngày (SLO 99,5%): 25 901 755 request, cho phép 129 508,8 lỗi, thực tế 55 618 lỗi (availability 0,997853) → đã tiêu **42,95%**, còn **57,05%**. **Không** đóng băng release (`freeze_releases = False`), nhưng đã gần nửa ngân sách nên phải theo dõi sát (checkout_bug 3,67% + provider_outage 2,32% + slow_leak + degraded_evening là các khoản lớn).

`small_bump` (20 phút ở 12% lỗi) chỉ tốn 1 794 request lỗi = **1,39%** ngân sách tháng. Burn-rate: cửa sổ 1 h chỉ đạt 8,2× (cần 14,4× cùng 5 phút) và cửa sổ 6 h chỉ 1,9× (cần 6×) nên không page. Với ngân sách còn gần 60%, đánh thức một người lúc 11 giờ trưa cho 1,4% ngân sách là cái giá lớn hơn cái bị mất; ngưỡng 5 phút cố định không biết điều đó nên page oan. Nếu 12% lỗi kéo dài thì ngân sách sẽ cạn sau ~30 giờ — và khi đó rule `fast_burn` sẽ page (burn 24× > 14,4×).

## 6. Postmortem — Băng G2 với client naive (blameless)

*Dữ liệu: `reports/gameday/naive_G2_overload_storm_timeseries.csv`, hình `reports/gameday/G2_overload_storm.png`.*

**Tóm tắt (3 câu):** Lúc t=120 s deployment `alpha` mất 75% GPU trong 3 phút; client v1 phản ứng bằng tối đa 36 lần thử cho mỗi call (3 tầng retry 4×3×3, delay cố định 0,2 s, không jitter, không breaker, không fallback, bỏ qua `retry-after` và deadline) nên tải thực tế lên `alpha` tăng 20–34 lần. Provider hồi phục hoàn toàn lúc t=300 s nhưng hệ thống chỉ bắt đầu trả lời được từ t=453 s, trễ 153 s, vì hàng đợi vẫn đầy request của những client đã bỏ đi và các vòng retry cũ vẫn đang chạy. Kết quả: 54,4% lượt user thất bại, cost/lượt thành công gấp 2,3 lần bình thường.

**Ảnh hưởng:** 1 285 / 2 362 lượt thất bại (availability 0,456; chỉ 1 077 lượt thành công). Người dùng thấy sập hoàn toàn từ khoảng t≈140 s đến t=453 s, ≈ **313 s (5 phút 13 giây)** cho một sự cố gốc dài 180 s. Chi phí 4,627 / lượt thành công so với 2,0 bình thường. Với giả định tháng chỉ có sự cố này và lưu lượng 4 lượt/s (10,37 triệu lượt/tháng, ngân sách 99,5% = 51 840 lượt lỗi), sự cố tiêu **≈ 2,5%** ngân sách tháng (1 285 / 51 840); cùng sự cố, client mới tiêu 0.

**Timeline** (giây ảo — từ CSV; baseline 7,5 attempts/s và 100% thành công trong t=0–120):

| t | Sự kiện | Bằng chứng (số) |
|---:|---|---|
| 120 | `alpha` mất 75% năng lực (18 → ~4,5 slot, ≈ 3,8 req/s so với tải ~7,5 call/s) | t=120–130: 6,2 attempts/s, 100% thành công — hàng đợi bắt đầu dài |
| 130–150 | Retry storm bắt đầu: đỉnh **254 attempts/s tại t=144** (34× baseline) | t=130–150: 133 attempts/s, tỷ lệ thành công tụt còn 28,8%; từ t=140: **0 thành công** |
| 150–300 | Sập hoàn toàn khi sự cố còn đang diễn ra | 127–159 attempts/s (17–21× baseline), `calls_ok` = 0/s, ~4 call thất bại/s |
| 300 | `alpha` hồi phục hoàn toàn (capacity 100%) | attempts/s vẫn 27 rồi 15–16 (t=320–360), `calls_ok` = **0** — hệ thống chưa phục hồi |
| 360–420 | Đợt retry thứ hai (nhiều khả năng đồng pha do delay cố định 0,2 s + timeout 8 s) | 120 → 74 attempts/s, `calls_ok` = 0 |
| 440–460 | Thành công đầu tiên: **t=453**; ≥ 95% thành công từ **t=461** | t=440–460: 2,25 ok/s (46%); t=460–480: 12,7 ok/s (97%); `recovery_s` = **155 s** sau t=300 |

**Trigger vs root cause.** *Trigger* là mất 75% GPU của `alpha` — một sự kiện bên ngoài, tạm thời, không tránh được. *Root cause* là thiết kế retry của client v1: ba tầng retry chồng nhau (app × gateway × SDK = 36 attempt/call), delay cố định 0,2 s không jitter nên các client đồng pha, bỏ qua `retry-after` (28 381 vi phạm), không có retry budget, không breaker, không fallback sang `alpha-eu`/`beta` (3 provider còn lại gần như nhàn rỗi suốt sự cố), và không biết deadline: user bỏ đi sau 30 s nhưng call vẫn được thử tiếp tới ~295 s (36 × 8,2 s). Amplification trung bình 9,90× (retry_ratio 8,904), biến một sự cố thiếu năng lực thành quá tải 20–34 lần.

**Vì sao không tự hồi phục sau t=300?** Đây là **metastable failure**. Vòng lặp tự duy trì: hàng đợi dài → request chờ quá 10 s bị 529, hoặc client hết 8 s timeout → mỗi lần thất bại sinh thêm một attempt → hàng đợi càng dài. Khi client timeout, **server vẫn xử lý tiếp** request đó nên công suất bị đốt cho những kết quả không ai nhận. Tại t=300 năng lực trở lại (~15 req/s) nhưng tải chào vào vẫn 15–120 attempts/s, gồm retry của hàng nghìn call đã bị user bỏ rơi và hàng đợi vẫn đầy request chết ⇒ goodput ≈ 0 dù provider khỏe. Hệ thống chỉ thoát ra khi các vòng retry hết 36 lần thử và hàng đợi rỗng dần, tức t≈453. Nguyên nhân kéo dài là *tải do chính client tạo ra*, không phải nguyên nhân gốc đã được sửa.

**Điều gì giúp / điều gì làm tệ hơn.** Giúp: timeout 8 s trên mỗi attempt giới hạn thời gian giữ slot; `alpha` thật sự hồi phục đúng hẹn; các provider khác còn trống. Làm tệ hơn: 36 attempt/call; delay cố định gây đợt retry đồng pha (đỉnh 254/s lúc t=144 và đợt hai lúc t=360–420); không có đường thoát sang provider khác; không dừng retry khi user đã đi; không phân biệt `retry-after`.

**Action items** (cụ thể, có owner, đo được):

| # | Hành động | Loại | Owner | Cách kiểm chứng |
|---|---|---|---|---|
| 1 | Gỡ các tầng retry chồng nhau (app/gateway/SDK) — chỉ còn **một** tầng retry trong client, các tầng khác đặt `max_retries=0`. Retry dùng full jitter, tôn trọng `retry-after`, kèm retry budget 10% | prevent | Nhóm Platform / LLM gateway | CI chạy G2 với client mới: **amplification ≤ 1,2** (hiện 1,04) và G1 `retry_after_violations = 0` |
| 2 | Circuit breaker sliding-window (theo tỷ lệ lỗi + call chậm) và fallback ladder `alpha → alpha-eu → beta` lọc theo khả năng tool calling | mitigate | Nhóm Reliability | CI chạy G2/G6: availability ≥ 95%, recovery ≤ 30 s, ≥ 80% traffic quay lại `alpha`, `incompatible_routes = 0` |
| 3 | Truyền deadline của user xuống client; không gửi/không retry attempt khi quá deadline; huỷ request đang chờ khi client đã bỏ | prevent | Nhóm Platform | Unit test `test_never_sends_past_the_deadline` + chỉ số mới "attempt sau deadline" = 0 trên G2 |
| 4 | Cảnh báo burn-rate đa cửa sổ (14,4× 1 h/5 m) và thêm alert trực tiếp trên **amplification** (attempts / logical call > 2 trong 2 phút) | detect | On-call lead + SRE | Replay dữ liệu G2: page đến trong ≤ 5 phút sau t=120; không page oan trên blip (`make slo`: 0 false page) |
| 5 | Runbook "retry storm": thao tác bật breaker thủ công / tắt retry tại gateway, và game day G2 định kỳ hằng quý | mitigate | On-call lead | Diễn tập: thời gian từ page đến khi amplification < 1,5 ≤ 10 phút |

Bài học nằm ở hệ thống và quy trình, không ở cá nhân: mặc định "mọi lỗi đều thử lại" và việc chưa kiểm thử kịch bản mất năng lực một phần là những khoảng trống mà bất kỳ ai làm theo thiết kế này đều có thể rơi vào.

## 7. Một điểm yếu còn lại

**G2 p95 = 11,0 s** (cao nhất cả 6 băng, tối đa 11,8 s qua 5 seed): trong những giây đầu của sự cố, mỗi lượt vẫn phải đợi hết timeout 8 s trên `alpha` đang quá tải trước khi breaker kịp mở (cần 10 kết quả), rồi mới fail over; lượt đó tốn thêm cả một lượt `chat`. Đã đo thử trên 6 băng × 5 seed: `attempt_timeout_s` = 5 → p95 G2 ≤ 8,8 s, = 4 → ≤ 6,8 s, và vẫn PASS cả 6 băng; tôi giữ 8 s vì 4 s chạm vào đuôi bình thường (G6 mất 1 lượt `no_provider_available`) và với ≤ 5 s thì `slow_call_s = 5` không còn phát hiện được call chậm riêng (timeout xảy ra trước). Cách sửa tốt hơn: **timeout thích ứng** theo p99 quan sát được (cộng hệ số) hoặc **hedged request** sang `alpha-eu` sau ~P95 độ trễ bình thường thay vì chờ đủ 8 s; đánh đổi là thêm vài % call. Điểm yếu thứ hai: khi `beta` (cost 1,4) gánh tải (G6) cost/lượt tăng 7% (2,141 so 2,0) mà không có giới hạn chi phí rõ ràng.

## 8. Cache (Part G)

Số từ `reports/cache/*.json` (`make cache`, seed 25).

| Client | availability | faq_availability | cache_hit_ratio | stale_served | wrong_answers | outdated_answers | cost/turn | PASS? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| resilient (không cache) | 0,8373 | 0,8424 | 0,000 | 0 | 0 | 0 | 1,386 | ❌ (faq_availability, hit ratio) |
| cached (của bạn) | 0,9124 | 0,9645 | 0,652 | 157 | 0 | 3 | 0,915 | ✅ |

Cache giảm chi phí mỗi lượt tốt 34% (1,386 → 0,915) và nâng faq_availability 0,842 → 0,965 mà không trả sai câu nào. `availability` tổng chỉ 0,912 vì lượt cá nhân và lượt cần tool không trả lời được từ cache trong 2 phút mọi provider sập.

| Tham số `cache:` | Giá trị | Vì sao (số liệu nào) |
|---|---:|---|
| similarity_threshold | 0,91 | Đo catalog FAQ: hai câu **cùng ý** có cosine ≥ **0,951**, hai câu **khác ý** (cặp "gần mà khác": `refund_policy`/`refund_time`, đổi size/màu, phí ship nội thành/ngoại tỉnh, thanh toán/COD) ≤ **0,862**. 0,91 nằm giữa hai cụm (biên 0,048 phía dưới và 0,041 phía trên). Quét 0,88–0,94 cho kết quả y hệt; 0,80 → 285 `other_question`; 0,97 → mất hit. |
| ttl_s | 60 | Chỉ TTL giới hạn được `outdated_answers` (đổi giá ship lúc t=480 không báo). TTL 30 → 2 outdated, hit 0,592; **60 → 3, hit 0,652**; 300 → **95** (FAIL, giới hạn 15). 60 s giữ hit ≥ 0,5 (có biên 15 điểm) và outdated xa giới hạn. |
| max_stale_s | 300 | Sự cố dài 120 s; entry cũ nhất lúc bắt đầu sự cố tuổi ≤ ttl, lúc kết thúc ≤ ttl + 120 s ⇒ cần `max_stale_s` > 120 s. 0 → faq_availability 0,8733 (FAIL); 60 → 0,923–0,938 (không ổn định qua seed); ≥ 120 → 0,956–0,964 (PASS). 300 s là biên an toàn gấp 2,5 lần cho băng ẩn có sự cố lệch/dài hơn. |
| max_entries | 500 | Catalog chỉ ~60 câu; 500 không bị LRU đuổi trên băng này. |

Thí nghiệm:

1. **Ngưỡng** (ttl 60, stale 300): 0,80 → hit 0,676, **wrong 285** (`other_question`), faq_availability 0,7983, cost 1,013, FAIL; **0,91 → hit 0,652, wrong 0, faq 0,9645, cost 0,915**; 0,97 → hit 0,585, wrong 0, cost 0,961. Ở 0,80, các cặp gần nhau (~0,86) bị gộp: ví dụ "Phí ship đi tỉnh bao nhiêu?" nhận câu trả lời của "Phí ship nội thành bao nhiêu?", hay "Bao lâu thì nhận được tiền hoàn?" nhận câu của "Chính sách hoàn tiền thế nào?" — câu trả lời nghe hợp lý nhưng sai, tệ hơn không trả lời. 0,97 an toàn nhưng loại cả những cách diễn đạt khác nhau hợp lệ (≥ 0,951) nên mất 6,7 điểm hit và tăng cost.
2. **TTL** (thr 0,91): 30 / 60 / 300 → outdated 2 / 3 / **95**, hit 0,592 / 0,652 / 0,731, cost 0,955 / 0,915 / 0,863. Webhook không giúp gì cho `outdated_answers` vì thay đổi giá ship (`policy/shipping`, t=480) *không được báo*: cache không có tín hiệu nào để invalidate, nên mọi câu trả lời cũ còn sống đến hết TTL vẫn được phục vụ như tươi; TTL là chặn duy nhất. Webhook chỉ xử lý thay đổi có báo (`policy/refund` lúc t=150 → `ignored_invalidation` = 0).
3. **Stale-if-error** (`max_stale_s: 0`): faq_availability **0,9645 → 0,8733** (FAIL, stale_served 157 → 0, hit 0,652 → 0,561) — trong 120 s mọi provider sập, không còn gì để trả; cửa sổ stale cứu 9,1 điểm availability.

Trả lời:

- **Vì sao câu hỏi cá nhân ("Đơn #48213 của tôi đang ở đâu?") không được cache, kể cả theo từng user?** Thứ nhất, câu trả lời phụ thuộc trạng thái *sống* (vị trí đơn, tiền hoàn đã về chưa) đổi trong vài phút, và nguồn dữ liệu là tài khoản của riêng user nên không có webhook nào để invalidate — stale là sai (loại `personal_cached`). Thứ hai, embedding của "#48213" và "#48214" giống nhau ~0,997 nên chỉ một lỗi scope là lộ đơn hàng người này cho người kia (`other_user`, rò rỉ dữ liệu cá nhân). Scope theo user chặn rò rỉ nhưng không chữa được stale, mà lại hầu như không có hit (một user hiếm khi hỏi lại đúng câu đó trong TTL), nên chi phí rủi ro lớn hơn lợi ích. Test `test_personal_answer_is_never_served_to_anyone` kiểm cả hai khía cạnh.
- **Dashboard vẫn xanh nhờ cache — alert theo số nào?** Alert trên *nguồn* thay vì trên trải nghiệm: (1) tỷ lệ `stale_served` / câu phục vụ từ cache (ở C1 là 157 lượt stale; page nếu stale liên tục > 1–2 phút hoặc > 20% FAQ); (2) availability **của provider phía sau cache** (client bên trong trả `GiveUp` — ở C1 faq_availability không cache chỉ 0,8424, chênh 12,2 điểm so với 0,9645 người dùng thấy); (3) số breaker ở trạng thái OPEN / tỷ lệ lỗi theo provider; (4) burn-rate của SLI "origin success" tách riêng khỏi SLI của user. Nếu chỉ nhìn availability của user, ta chỉ phát hiện sự cố khi stale hết cửa sổ (`ttl + max_stale` ≈ 6 phút) và cache cạn.
