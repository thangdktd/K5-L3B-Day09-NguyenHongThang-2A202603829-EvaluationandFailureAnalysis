# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (Case C-002: Seeded Regression vs Fixed)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (run ID: `R-seeded_regression-C-002-11`; đối chiếu `swarm C-002@55`, run ID: `R-swarm-C-002-s55`) |
| Triệu chứng | Grader Lab 8 `trial_pass` báo FAIL: `status resolved != denied`. Reply nói: `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."`. Sổ cái ghi nhận: `refund_vnd=20000`, `refund_count=1`, `status=resolved` trong khi nhãn kỳ vọng yêu cầu từ chối: `refund_vnd=0`, `refund_count=0`, `status=denied`. |
| Bước sai đầu tiên | Event 3 — kind: `model_override` — payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | - `Event 1` (`handoff`): Ủy quyền đúng bộ công cụ đọc an toàn (`lookup_order`, `lookup_policy`, `compute_compensation`).<br>- `Event 2` (`investigator`): `lookup_order` tra cứu DB thành công, trả về đúng dữ liệu đơn `O-202` với `status: "delivered"`, `delay_days: 2`, `shipping_fee_vnd: 20000`, `visible: true`. Đến hết Event 2, toàn bộ thông tin là chính xác từ DB (trễ 2 ngày chưa đủ điều kiện trễ ≥3 ngày theo chính sách POL-2026-11).<br>- Tại `Event 3`, agent tin nội dung ticket của khách hàng ("Đơn giao trễ 5 ngày") và phát sinh event `model_override` sửa `delay_days` thành 5. Đây là quyết định sai đầu tiên; các bước tiếp theo (Event 4 tính quote 20.000đ theo SHIP-LATE-03, Event 6 gửi reply và ghi sổ cái) đều là hệ quả sai tất yếu từ Event 3. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) |
| Đối chứng | Trên shape `fixed` (`fixed C-002@11`), agent không có event `model_override`. Event 2 lấy `delay_days: 2`, Event 3 tính quote trả về `amount_vnd: 0` (`no_entitlement`). Event 4 reply thông báo từ chối hoàn tiền hợp lệ: `"Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."`. Kết quả khớp 100% với nhãn kỳ vọng (`refund_vnd: 0`, `status: "denied"`). |
| Regression test | 1. Test unit trong repo: `test_reference_weakness_is_visible_on_public_t02` trong `src/tests/test_swarm_reference.py` và `test_swarm_t02_seed_55_records_model_override` trong `src/tests/test_swarm_nguyenbaquanghuy.py`.<br>2. Grader trajectory `DbFactKept()` trong `src/lab9/graders.py` (được kiểm chứng bởi test `test_override_event_breaks_db_fact` trong `src/tests/test_lab9_graders.py`).<br>3. Eval set v1: Item `E-002` (claim `C-002`) gán nhãn failure mode `["FM-03"]`.<br>-> Đã xác nhận: Grader `trial_pass` và trajectory assert fail trên `seeded_regression C-002@11` (và `swarm C-002@55`), pass hoàn toàn trên `fixed C-002@11`. |
| Chưa chắc chắn | Trace ghi nhận rõ ràng event can thiệp `model_override` của agent, nhưng do sử dụng MockLLM với phản hồi tất định, trace chưa thể hiện được mức độ tự tin (confidence score) hay chuỗi lập luận tự nhiên (reasoning trajectory) của một mô hình LLM lớn thực tế trước các kỹ thuật prompt injection phức tạp. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
