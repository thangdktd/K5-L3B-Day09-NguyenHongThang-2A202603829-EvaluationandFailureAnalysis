# Judge audit (Đánh giá & Hiệu chuẩn LLM Judge)

Lệnh thực thi:
```bash
cd src
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

## Bảng tổng hợp hiệu chuẩn (Calibration Summary)

| Tiêu chí | n | κ (Cohen's Kappa) | Precision (P) | Recall (R) | Observed Fail Rate | Corrected Fail Rate (Rogan–Gladen) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| **tone_ok** | 100 | 0.757 | 0.857 | 0.800 | 0.280 | 0.300 | **ĐẠT (PASS)** | **Dùng** |
| **helpful** | 100 | 0.375 | 1.000 | 0.300 | 0.090 | 0.300 | **KHÔNG ĐẠT (FAIL)** | **Loại** |

*Ngưỡng tối thiểu (FLOORS):* $\kappa \ge 0.6$, $\text{Precision} \ge 0.8$, $\text{Recall} \ge 0.7$.

---

## Chi tiết ma trận nhầm lẫn (Confusion Matrix)

Với quy ước lớp dương tính **POS = "FAIL"** (mục tiêu của Judge là phát hiện lỗi/thất bại):
- **Tone Judge**: $\text{TP} = 24, \text{FP} = 4, \text{FN} = 6, \text{TN} = 66$ (Tổng: 100).
  + $\text{Precision} = \frac{24}{24 + 4} = 0.857 \ge 0.8$
  + $\text{Recall} = \frac{24}{24 + 6} = 0.800 \ge 0.7$
  + $\text{Specificity} = \frac{66}{66 + 4} = 0.943$
  + $\kappa = \frac{0.900 - 0.588}{1 - 0.588} = 0.757 \ge 0.6$
  + Tỷ lệ lỗi quan sát: $0.280 \xrightarrow{\text{Rogan–Gladen}} 0.300$ (rất sát với ground-truth human $30/100 = 0.300$).
- **Helpful Judge**: $\text{TP} = 9, \text{FP} = 0, \text{FN} = 21, \text{TN} = 70$ (Tổng: 100).
  + $\text{Precision} = \frac{9}{9 + 0} = 1.000 \ge 0.8$
  + $\text{Recall} = \frac{9}{9 + 21} = 0.300 < 0.7$ (**Trượt sàn nghiêm trọng**)
  + $\text{Specificity} = \frac{70}{70 + 0} = 1.000$
  + $\kappa = \frac{0.790 - 0.664}{1 - 0.664} = 0.375 < 0.6$ (**Đồng thuận kém**)
  + Tỷ lệ lỗi quan sát: $0.090 \xrightarrow{\text{Rogan–Gladen}} 0.300$ (Judge quan sát 9% nhưng thực tế lỗi là 30%).

---

## Bảng audit thủ công các ca bất đồng (Disagreements Audit)

Dưới đây là 6 ca bất đồng tiêu biểu từ dữ liệu thực tế giữa Human và Judge:

| # | Case ID | Reply | Nhãn Judge | Nhãn Người | Ai đúng? | Nguyên nhân bất đồng | Hành động sửa Rubric / Khắc phục |
|---|---|---|---|---|---|---|---|
| 1 | `H-008` (Tone) | *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* | PASS | FAIL | **Người** | Judge coi lời văn xưng "em... nha" là thân thiện; tuy nhiên trong dịch vụ khách hàng B2C LogiX, cách xưng hô này quá suồng sã, thiếu tính chuyên nghiệp. | Bổ sung quy định rõ ràng trong rubric: cấm đại từ xưng hô thân mật tự phát (`anh/em/nha/check`), yêu cầu đại từ chuẩn mực (`LogiX`, `anh/chị`, `quý khách`). |
| 2 | `H-029` (Tone) | *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* | PASS | FAIL | **Người** | Judge bị đánh lừa bởi từ ngữ lịch sự bề mặt (*"Dạ, vui lòng"*), bỏ qua vế sau có thái độ ra lệnh, gạt bỏ khách hàng (*"không cần nhắn thêm"*). | Cập nhật rubric: bổ sung tiêu chí cấm thái độ mệnh lệnh, áp đặt hoặc từ chối hỗ trợ (dismissive/commanding tone), không chỉ dựa vào từ khóa lịch sự mở đầu. |
| 3 | `H-051` (Tone) | *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* | FAIL | PASS | **Người** | Judge quá khắt khe, coi từ mượn tiếng Anh *"refund"* là vi phạm chuẩn ngôn ngữ, trong khi cẩm nang CS LogiX cho phép dùng từ này. | Thêm danh sách ngoại lệ (allowlist) các từ mượn phổ biến trong TMĐT/Logistics (`refund`, `order`, `tracking`, `status`) vào prompt rubric để Judge không phạt oan. |
| 4 | `H-081` (Tone) | *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* | FAIL | PASS | **Judge** | Lỗi gán nhãn của con người (label noise / human fatigue): người chấm đọc nhầm ticket; câu trả lời của agent rất nhã nhặn, đúng chính sách và chuẩn mực. | Sửa lại nhãn người trong bộ dữ liệu (`re-labeling`). Thiết lập quy trình dual-annotation cho các ca nghi ngờ để đảm bảo chất lượng ground-truth. |
| 5 | `HL-016` (Helpful) | *"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này... LogiX đã hoàn 55.000đ cho đơn O-404..."* | PASS | FAIL | **Người** | Câu trả lời rất lịch sự, xin lỗi chân thành nên Judge đánh giá hữu ích (PASS). Nhưng trên thực tế, số tiền 55.000đ là **sai lệch hoàn toàn** so với chính sách DB. | **Loại Judge helpful khỏi CI gate.** Tách bạch rõ: Judge chỉ đánh giá văn phong; tính chính xác của số tiền và điều khoản bắt buộc phải do code grader đối chiếu trực tiếp với sổ cái DB. |
| 6 | `HL-047` (Helpful) | *"Ok bạn, đơn O-515 xử lý rồi nhé."* | PASS | FAIL | **Người** | Judge cho rằng yêu cầu đã được đáp ứng ngắn gọn. Người chấm đánh FAIL vì câu trả lời cộc lốc, không nêu rõ đã hoàn bao nhiêu tiền, khi nào nhận được. | Định lượng tiêu chí Helpfulness trong rubric: một câu trả lời chỉ đạt yêu cầu khi cung cấp đủ các thông tin then chốt (mã đơn, kết quả xử lý, số tiền/thời gian cụ thể). |

---

## Phân tích chuyên sâu phương pháp luận

### 1. Ý nghĩa của Cohen's Kappa trong đánh giá Judge
- **Cohen's Kappa ($\kappa$)** đo lường mức độ đồng thuận giữa hai người đánh giá (ở đây là LLM Judge và chuyên gia con người), sau khi đã loại trừ xác suất đồng thuận ngẫu nhiên ($p_e$):
  $$\kappa = \frac{p_o - p_e}{1 - p_e}$$
- Nếu chỉ dùng độ chính xác thô (raw accuracy / $p_o$), khi tập dữ liệu mất cân bằng (ví dụ 90% PASS), một Judge "lười biếng" luôn đoán PASS vẫn đạt độ chính xác 90%. Nhưng khi đó $p_e \approx 0.90$, dẫn tới $\kappa \approx 0$, phơi bày việc Judge không hề có tín hiệu phân loại thực sự.
- Khi Judge đưa ra nhãn hằng số (constant judge, $p_e = 1$), $\kappa$ không xác định $\Rightarrow$ code phải `raise ValueError` để hệ thống đánh FAIL calibration ngay lập tức, không cho phép lọt qua vì lý do kỹ thuật.
- Ngưỡng $\kappa = 0.757 \ge 0.6$ của `judge_tone` khẳng định mức độ đồng thuận đáng tin cậy (substantial agreement).

### 2. Ý nghĩa của Precision và Recall đối với Positive Class ("FAIL")
- Trong bài toán kiểm thử phần mềm và an toàn Agent, mục tiêu tối thượng là **tìm ra lỗi** (failure detection). Vì vậy, lớp dương tính (Positive) bắt buộc phải là **`FAIL`**.
- **Precision ($P = \frac{\text{TP}}{\text{TP} + \text{FP}}$)**: Đo lường mức độ tin cậy khi Judge cảnh báo lỗi. Precision thấp đồng nghĩa với việc Judge báo động giả (False Alarm) nhiều, khiến CI pipeline liên tục bị chặn oan đối với các Pull Request tốt, gây mệt mỏi và mất lòng tin của kỹ sư phát triển.
- **Recall ($R = \frac{\text{TP}}{\text{TP} + \text{FN}}$)**: Đo lường tỷ lệ lỗi thực tế được phát hiện. Recall thấp đồng nghĩa với việc Judge bỏ sót lỗi nghiêm trọng (False Negative), để lọt các câu trả lời sai lệch, khiếm nhã tới tay người dùng cuối.

### 3. Hiệu chỉnh Rogan–Gladen và các giới hạn
- **Công thức Rogan–Gladen**:
  $$p_{\text{true}} = \frac{p_{\text{obs}} + \text{specificity} - 1}{\text{sensitivity} + \text{specificity} - 1}$$
- **Mục đích**: Khi triển khai Judge vào production, ta chỉ quan sát được tỷ lệ lỗi mà Judge báo về ($p_{\text{obs}}$). Bằng cách sử dụng độ nhạy (Recall) và độ đặc hiệu (Specificity) đã được hiệu chuẩn trước đó, công thức Rogan–Gladen giúp khôi phục ước lượng không chệch của tỷ lệ lỗi thực tế trong quần thể mà không cần con người chấm lại toàn bộ.
- **Giới hạn**:
  1. *Giới hạn tính toán*: Nếu $\text{sensitivity} + \text{specificity} \approx 1$ (Judge hoạt động không hơn gì phép tung đồng xu ngẫu nhiên), mẫu số tiến về 0 khiến công thức mất ổn định.
  2. *Giới hạn cấp độ*: Rogan–Gladen chỉ hiệu chỉnh được tỷ lệ lỗi vĩ mô (prevalence) của cả quần thể, không thể cho biết cụ thể mẫu nào bị Judge dán nhãn sai ở cấp độ từng dòng.
  3. *Hiện tượng ngoài khoảng*: Với mẫu nhỏ hoặc tỷ lệ quan sát cực đoan, công thức có thể cho ra giá trị $< 0$ hoặc $> 1$, bắt buộc phải cắt tỉa (clipping) về đoạn $[0, 1]$.

### 4. Vì sao `judge_tone` được chấp nhận làm Gate, còn `judge_helpful` bị loại?
- **`judge_tone` ĐƯỢC CHẤP NHẬN**:
  + Tone là một thuộc tính ngôn ngữ thuần túy (văn phong, độ lịch thiệp, thái độ giao tiếp). Đây là nhiệm vụ mà các mô hình ngôn ngữ lớn (LLM) có năng lực biểu diễn và phân tích ngữ cảnh rất mạnh.
  + Đạt toàn diện cả 3 tiêu chí: $\kappa = 0.757 \ge 0.6$, $P = 0.857 \ge 0.8$, $R = 0.800 \ge 0.7$. Tỷ lệ bỏ sót lỗi thấp ($FN = 6$), tỷ lệ báo nhầm thấp ($FP = 4$).
- **`judge_helpful` BẮT BUỘC BỊ LOẠI**:
  + Rơi vào bẫy **"Thiên kiến trôi chảy" (Fluency Bias)**: Một LLM Judge không được nối với cơ sở dữ liệu (ungrounded) chỉ nhìn vào bề mặt câu chữ. Khi agent bịa ra một số tiền bồi thường sai (như hoàn 55.000đ thay vì 35.000đ) nhưng văn phong vô cùng lễ phép và xin lỗi tha thiết, Judge vẫn chấm PASS vì thấy "rất hữu ích và đầy đủ".
  + Hậu quả thực nghiệm: Recall chỉ đạt **$0.300$** (bỏ lọt tới 70% số lỗi thực tế, tương ứng 21/30 ca sai phạm lọt lưới). $\kappa = 0.375$ thể hiện sự đồng thuận rất yếu.
  + Nếu đưa `judge_helpful` vào CI gate, gate sẽ tạo ra "cảm giác an toàn giả tạo" (false sense of security), bỏ lọt hàng loạt lỗi nghiệp vụ tài chính vào hệ thống production.

### 5. Những trường hợp bắt buộc phải có Human Review
1. **Kiểm tra nghiệp vụ tiền tệ và thẩm quyền (Money Movement & Policy Guardrails)**: Tuyệt đối không giao phó việc kiểm tra số tiền hoàn cho LLM judge; phải dùng code assertion đối soát trực tiếp với `refund_ledger`.
2. **Ngữ cảnh văn hóa và xưng hô bản địa**: Tiếng Việt có hệ thống đại từ nhân xưng phức tạp dựa theo tuổi tác, vị thế. Các trường hợp nhạy cảm về xưng hô cần con người rà soát định kỳ.
3. **Các ca bất đồng (Disagreements)** giữa Judge và bộ quy tắc từ khóa hoặc khi độ tin cậy của Judge thấp.
4. **Hiệu chuẩn định kỳ trên dữ liệu mới (Held-out drift)**: Dữ liệu hiện tại là replay tĩnh; khi hành vi người dùng hoặc phiên bản model thay đổi, bắt buộc phải có con người dán nhãn một tập kiểm thử mới (fresh held-out test set) để hiệu chuẩn lại Judge.
