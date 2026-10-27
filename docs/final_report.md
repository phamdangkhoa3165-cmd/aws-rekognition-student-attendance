# BÁO CÁO TỔNG KẾT ĐỒ ÁN MÔN HỌC ĐIỆN TOÁN ĐÁM MÂY
- **Trường:** Đại học Công nghệ Kỹ thuật TP. Hồ Chí Minh (HCM-UTE)
- **Đề tài:** Nhận diện khuôn mặt điểm danh sinh viên với Amazon Rekognition (Nhóm: AI/ML)
- **Giảng viên hướng dẫn:** ThS. Huỳnh Xuân Phụng
- **Sinh viên thực hiện:**
  1. Phạm Đăng Khoa – MSSV: 24110256
  2. Huỳnh Quảng Tín – MSSV: 24110353
- **Thời gian thực hiện:** 05/10/2026 – 01/11/2026 (4 Tuần)

---

## 1. Tổng quan Kiến trúc Hệ thống
Hệ thống được xây dựng hoàn toàn theo kiến trúc phi máy chủ (Serverless) tại Region `us-east-1`, sử dụng `LabRole` có sẵn của AWS Learner Lab:
1. **Frontend (`frontend/index.html`):** Giao diện Web cho phép giảng viên tra cứu danh sách điểm danh, duyệt tay các bản ghi Fallback và tải ảnh lên S3 thông qua Pre-signed URL.
2. **Amazon API Gateway (`student-attendance-api` - ID: `x6b3w242ib`):** REST API triển khai ở stage `prod`, bật CORS và giới hạn tần suất gọi (Throttling: Rate 10 req/s, Burst 20).
3. **Amazon S3 (`student-attendance-rekognition-24110256`):** Bật `Block All Public Access: ON`, chia thành 3 thư mục `/registered-faces/`, `/class-photos/` và `/failed-uploads/`.
4. **AWS Lambda (Runtime Python 3.12, Timeout 30s, Memory 256MB):**
   - `RegisterFaceFunction`: Trích xuất vector khuôn mặt qua `IndexFaces` và lưu thông tin vào bảng `Students`.
   - `AttendanceCheckFunction`: Đối chiếu khuôn mặt qua `SearchFacesByImage` (ngưỡng >= 85%) và xử lý cơ chế Fallback 2 tầng.
   - `GetAttendanceAPI`: Xử lý truy vấn điểm danh, duyệt tay Fallback, kiểm tra điều kiện quyền riêng tư (`privacy_consent`) và hạn mức khuôn mặt (`FaceCount`) trước khi cấp S3 Pre-signed URL.
5. **Amazon Rekognition (`student-face-collection`):** Lưu trữ vector đặc trưng khuôn mặt (hiện lưu 2 vector của 2 thành viên nhóm, không lưu ảnh gốc).
6. **Amazon DynamoDB (On-Demand):** Gồm 3 bảng `Students`, `AttendanceRecords`, `AttendanceManualReview`.
7. **Amazon CloudWatch:** Thiết lập Log Retention 14 ngày cho 3 hàm Lambda, cảnh báo `FaceAttendance-Lambda-Errors-Alarm` và bảng theo dõi `FaceAttendance-Monitoring-Dashboard`.

---

## 2. Kết quả Kiểm thử Tổng thể Toàn trình (End-to-End Testing)

| Mã E2E | Kịch bản kiểm thử End-to-End | Các bước thực hiện trên giao diện Web & AWS | Kết quả thực tế | Trạng thái |
| :---: | :--- | :--- | :--- | :---: |
| **E2E-01** | **Kịch bản chặn 1: Chưa xác nhận đồng ý Quyền riêng tư** | Chọn tệp ảnh trên Web, bỏ trống ô checkbox `Xác nhận Quyền riêng tư`, bấm tải ảnh lên. | API Gateway & Lambda chặn yêu cầu, trả về mã `HTTP 400 Bad Request` (`PRIVACY_CONSENT_REQUIRED`), không sinh Pre-signed URL. | **PASS** |
| **E2E-02** | **Kịch bản chặn 2: Chạm/vượt ngưỡng Quota khuôn mặt** | Chọn tác vụ đăng ký khuôn mặt mới, bật chế độ kiểm thử chạm ngưỡng Quota (`Limit = 2` khi Collection đã có 2 khuôn mặt), tích chọn Consent và bấm tải ảnh. | Lambda kiểm tra `FaceCount (2) >= Limit (2)`, chặn yêu cầu và trả về mã `HTTP 403 Forbidden` (`FACE_QUOTA_EXCEEDED`). | **PASS** |
| **E2E-03** | **Luồng điểm danh tự động hoàn chỉnh (Happy Path)** | Chọn tác vụ điểm danh lớp học, tích chọn Consent, tải ảnh hợp lệ -> PUT lên S3 qua Pre-signed URL -> S3 kích hoạt Lambda 2 -> Rekognition đối soát -> DynamoDB. | Web nhận `HTTP 200 OK`, tải ảnh thành công; sau 5 giây bảng điểm danh cập nhật SV có mặt với `Confidence > 99%`, `AI_AUTOMATIC`. | **PASS** |
| **E2E-04** | **Luồng Fallback 1 & Giảng viên duyệt tay trên Web** | Tải ảnh khuôn mặt chưa đăng ký/độ khớp < 85% -> Vào bảng `AttendanceManualReview` -> Bấm nút `Duyệt tay MSSV` trên Web. | Bản ghi chuyển từ `PENDING_MANUAL_REVIEW` sang `RESOLVED_MANUAL_PRESENT`; SV được thêm vào bảng chính với cờ `MANUAL_FALLBACK_APPROVED`. | **PASS** |
| **E2E-05** | **Luồng Fallback 2 (Cách ly ảnh lỗi) & CloudWatch** | Tải tệp hỏng định dạng (`corrupted_image.jpg`) vào `/class-photos/`. | Lambda bắt ngoại lệ `ClientError`, di chuyển tệp sang `/failed-uploads/`, ghi trạng thái `SYSTEM_ERROR_ISOLATED` và cập nhật CloudWatch Metrics. | **PASS** |

---

## 3. Báo cáo Chi phí Sử dụng & Tối ưu Chi phí (Cost Report & Optimization)

### a. Thống kê chi phí sau 4 tuần triển khai trên AWS Learner Lab
Nhờ thiết kế 100% Serverless (chỉ tính phí khi có request thực thi, không dùng máy chủ EC2 hay NAT Gateway chạy ngầm), tổng chi phí phát sinh trong suốt 4 tuần của nhóm cực thấp (dưới **$0.05 USD**):
- **Amazon Rekognition:** Gọi dưới 50 lượt API `IndexFaces`, `SearchFacesByImage`, `DescribeCollection` và lưu trữ 2 vector khuôn mặt $\rightarrow$ Chi phí **~$0.03 USD**.
- **AWS Lambda:** Dưới 200 lượt gọi hàm (nằm trong hạn mức Free Tier 1 triệu requests/tháng) $\rightarrow$ Chi phí **$0.00 USD**.
- **Amazon S3:** Lưu trữ dưới 20 MB ảnh kiểm thử $\rightarrow$ Chi phí **<$0.01 USD**.
- **Amazon DynamoDB:** Chế độ `PAY_PER_REQUEST` (On-Demand) với dưới 500 lượt đọc/ghi $\rightarrow$ Chi phí **$0.00 USD**.
- **Amazon API Gateway & CloudWatch:** Dưới 200 requests, giới hạn Log Retention 14 ngày và 1 Alarm/Dashboard $\rightarrow$ Chi phí **<$0.01 USD**.

### b. Các biện pháp tối ưu chi phí & dọn dẹp tài nguyên đã áp dụng
1. Dùng DynamoDB chế độ **On-Demand** thay vì Provisioned để không tốn phí duy trì theo giờ khi không có tiết học.
2. Cấu hình **CloudWatch Log Retention = 14 ngày** cho cả 3 hàm Lambda.
3. Sử dụng **S3 Pre-signed URL** để tải ảnh trực tiếp từ trình duyệt lên S3, giảm tải băng thông qua Lambda/API Gateway.
4. Thực thi script `scripts/cleanup_resources.sh` sau mỗi buổi thực hành để xóa các tệp ảnh lỗi tạm trong `/failed-uploads/` và kiểm tra không có instance dư thừa.
