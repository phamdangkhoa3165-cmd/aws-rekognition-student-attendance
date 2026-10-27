# BÁO CÁO TỔNG KẾT ĐỒ ÁN MÔN HỌC ĐIỆN TOÁN ĐÁM MÂY (CLOUD COMPUTING)
- **Đơn vị đào tạo:** Trường Đại học Công nghệ Kỹ thuật TP. Hồ Chí Minh (HCM-UTE)
- **Đề tài:** Nhận diện khuôn mặt điểm danh sinh viên với Amazon Rekognition (Nhóm: AI/ML)
- **Giảng viên hướng dẫn:** ThS. Huỳnh Xuân Phụng
- **Sinh viên thực hiện:**
  1. Phạm Đăng Khoa – MSSV: 24110256
  2. Huỳnh Quảng Tín – MSSV: 24110353
- **Thời gian triển khai:** 05/10/2026 – 01/11/2026 (4 Tuần)
- **GitHub Repository:** https://github.com/phamdangkhoa3165-cmd/aws-rekognition-student-attendance
- **Video Demo chính thức (YouTube):** https://youtu.be/_ZaR-7ncBaw

---

## 1. Mục tiêu & Tổng quan Kiến trúc Hệ thống

### a. Mục tiêu đồ án
Xây dựng một hệ thống điểm danh tự động dựa trên ảnh chụp lớp học, áp dụng công nghệ nhận diện khuôn mặt của Amazon Rekognition. Hệ thống giải quyết triệt để các bài toán thực tế:
- Tự động hóa quá trình điểm danh, tiết kiệm thời gian trên lớp.
- Xử lý các tình huống biên (ảnh mờ, góc chụp nghiêng, lỗi tệp) thông qua cơ chế dự phòng 2 tầng (Fallback Mechanism).
- Tuân thủ nghiêm ngặt chính sách bảo mật, quyền riêng tư dữ liệu cá nhân và kiểm soát hạn mức chi phí trên môi trường đám mây.

### b. Kiến trúc Serverless 100% (Region `us-east-1`)
Hệ thống vận hành theo mô hình hướng sự kiện (Event-Driven Serverless), sử dụng `LabRole` có sẵn của AWS Learner Lab mà không cần duy trì bất kỳ máy chủ EC2 nào chạy ngầm:
- **Amazon S3 (`student-attendance-rekognition-24110256`):** Lưu trữ đối tượng tập trung với 3 thư mục độc lập: `/registered-faces/` (ảnh thẻ sinh viên), `/class-photos/` (ảnh lớp học), `/failed-uploads/` (ảnh lỗi cách ly). S3 kích hoạt trực tiếp các sự kiện `ObjectCreated` tới AWS Lambda.
- **AWS Lambda (Python 3.12):**
  - `RegisterFaceFunction`: Tự động nạp vector đặc trưng khuôn mặt vào Rekognition Collection qua API `IndexFaces` và lưu metadata vào DynamoDB.
  - `AttendanceCheckFunction`: Tự động quét và đối soát ảnh lớp học qua API `SearchFacesByImage` (ngưỡng tương đồng >= 85%), đồng thời đóng vai trò điều phối luồng Fallback 2 tầng.
  - `GetAttendanceAPI`: Tích hợp chuẩn Lambda Proxy với API Gateway để cấp S3 Pre-signed URL (kèm kiểm tra Privacy Consent & Quota), tra cứu kết quả và tiếp nhận lệnh duyệt tay thủ công.
- **Amazon API Gateway (`student-attendance-api` - ID: `x6b3w242ib`):** REST API chuẩn Regional tại `us-east-1`, hỗ trợ CORS, tích hợp bộ kiểm soát tần suất gọi (Throttling: Rate 10 req/s, Burst 20 req/s).
- **Amazon Rekognition (`student-face-collection`):** Lưu trữ vector đặc trưng toán học của khuôn mặt (Face Vectors), tuyệt đối không lưu ảnh gốc.
- **Amazon DynamoDB (On-Demand Mode):** Gồm 3 bảng NoSQL độc lập: `Students` (thông tin SV & FaceId), `AttendanceRecords` (kết quả điểm danh chính thức), `AttendanceManualReview` (hàng đợi rà soát dự phòng).
- **Amazon CloudWatch:** Quản lý Log Groups (retention 14 ngày), CloudWatch Alarm (`FaceAttendance-Lambda-Errors-Alarm`) và CloudWatch Dashboard trực quan theo dõi toàn diện hệ thống.

---

## 2. Kết quả Kiểm thử Toàn trình (End-to-End Testing)

Nhóm đã hoàn thành toàn bộ 5 kịch bản kiểm thử End-to-End từ giao diện Web Client, xuyên qua API Gateway tới hạ tầng backend AWS:

| Mã E2E | Tên kịch bản kiểm thử | Mô tả các bước thực hiện | Kết quả thực tế quan sát được | Kết luận |
| :---: | :--- | :--- | :--- | :---: |
| **E2E-01** | **Chặn thiếu Privacy Consent (HTTP 400)** | Tải ảnh lên nhưng không tích chọn ô "Xác nhận Quyền riêng tư" trên giao diện Web. | API Gateway và hàm `GetAttendanceAPI` lập tức chặn, trả về `HTTP 400 Bad Request` (`PRIVACY_CONSENT_REQUIRED`), không sinh Pre-signed URL. | **PASS** |
| **E2E-02** | **Chặn chạm/vượt Quota khuôn mặt (HTTP 403)** | Chọn tác vụ đăng ký, bật chế độ kiểm thử chạm ngưỡng Quota (`Limit = 2` khi Collection đã có 2 mặt), tích Consent và bấm tải ảnh. | Lambda kiểm tra `FaceCount (2) >= Limit (2)`, từ chối đăng ký và trả về `HTTP 403 Forbidden` (`FACE_QUOTA_EXCEEDED`). | **PASS** |
| **E2E-03** | **Điểm danh tự động toàn trình (HTTP 200)** | Tải ảnh lớp học hợp lệ qua S3 Pre-signed URL, S3 trigger Lambda 2 đối soát với Rekognition Collection. | Hệ thống trả về `HTTP 200 OK`, sau 5 giây bảng điểm danh hiển thị sinh viên có mặt với `Confidence > 99%` và `VerificationType = AI_AUTOMATIC`. | **PASS** |
| **E2E-04** | **Fallback 1 & Giảng viên duyệt tay trên Web** | Tải ảnh người chưa nạp vector hoặc ảnh chụp mờ, góc nghiêng khiến AI quét không tới 85%. | Bản ghi rơi vào bảng `AttendanceManualReview` (`PENDING_MANUAL_REVIEW`); giảng viên bấm Duyệt tay MSSV trên Web để chuyển sang bảng chính. | **PASS** |
| **E2E-05** | **Fallback 2 (Cách ly ảnh hỏng) & CloudWatch** | Tải tệp hỏng định dạng (`corrupted_image.jpg`) vào thư mục `/class-photos/`. | Lambda bắt lỗi `ClientError`, di chuyển tệp sang `/failed-uploads/`, bảng ghi `SYSTEM_ERROR_ISOLATED` và phát tín hiệu lên CloudWatch Dashboard. | **PASS** |

---

## 3. Chính sách Quyền riêng tư & Kỹ thuật Kiểm soát Giới hạn (Privacy & Quota Guardrails)
- **Tôn trọng Quyền riêng tư:** Hệ thống chỉ sử dụng hình ảnh của thành viên trong nhóm và người đã có thỏa thuận đồng ý. Tại tầng API, cổng `privacy_consent` bắt buộc phải là `true` mới được cấp quyền tải ảnh lên S3.
- **Bảo mật Lưu trữ:** S3 Bucket bật tuyệt đối `Block All Public Access: ON`. Mọi thao tác tải ảnh từ trình duyệt đều dùng Pre-signed URL có chữ ký bảo mật và tự động hủy sau 300 giây.
- **Kiểm soát Hạn mức Khuôn mặt:** Thực thi giới hạn an toàn thử nghiệm <= 50 khuôn mặt và giới hạn cứng toàn hệ thống là 1.000 khuôn mặt. Lambda tự động đếm số lượng vector trong Collection trước mỗi lần cấp URL nạp ảnh mới.
- **Chính sách Tagging:** Toàn bộ tài nguyên trên AWS đều được gắn thẻ quản trị: `Project: FaceAttendance` và `Owner: Khoa-Tin`.

---

## 4. Báo cáo Chi phí Sử dụng & Tối ưu Chi phí (Cost Optimization Report)

### a. Thống kê chi phí thực tế trên AWS Learner Lab
Nhờ kiến trúc 100% Serverless (không duy trì máy chủ EC2 hay NAT Gateway chạy ngầm), tổng chi phí phát sinh trong toàn bộ 4 tuần thực nghiệm của nhóm là **dưới $0.05 USD** (trong tổng ngân sách $50 USD được cấp):
- **Amazon Rekognition:** Thực hiện khoảng 40 lượt gọi API (`IndexFaces`, `SearchFacesByImage`, `DescribeCollection`) và duy trì lưu trữ 2 vector khuôn mặt, chi phí khoảng: **$0.03 USD**.
- **AWS Lambda:** Khoảng 150 lượt gọi hàm, thời gian chạy trung bình 800ms với 256MB RAM (hoàn toàn nằm trong Free Tier 1.000.000 requests/tháng), chi phí: **$0.00 USD**.
- **Amazon S3:** Dung lượng lưu trữ ảnh thử nghiệm dưới 20 MB, chi phí: **< $0.01 USD**.
- **Amazon DynamoDB:** Thiết lập chế độ `On-Demand (PAY_PER_REQUEST)` với dưới 400 lượt đọc/ghi, chi phí: **$0.00 USD**.
- **Amazon API Gateway & CloudWatch:** Dưới 150 requests, Log retention 14 ngày, chi phí: **< $0.01 USD**.

### b. Các biện pháp tối ưu chi phí đã áp dụng
1. Cấu hình DynamoDB ở chế độ **PAY_PER_REQUEST** (thay vì Provisioned) để không phát sinh chi phí duy trì theo giờ khi không diễn ra buổi điểm danh.
2. Giới hạn thời gian lưu trữ nhật ký CloudWatch Log Groups ở mức **14 ngày** (thay vì Never Expire mặc định).
3. Sử dụng cơ chế **S3 Pre-signed URL** để trình duyệt tải ảnh trực tiếp lên S3, giảm tải dung lượng truyền tải và thời gian thực thi của Lambda.
4. Xây dựng và thực thi định kỳ script `scripts/cleanup_resources.sh` để dọn sạch các tệp ảnh kiểm thử tạm thời trong vùng cách ly `/failed-uploads/`.

---

## 5. Kế hoạch Dọn dẹp Tài nguyên (Resource Cleanup)

Nhóm đã xây dựng tệp lệnh `scripts/cleanup_resources.sh` để quản lý việc dọn dẹp tài nguyên trên AWS:
1. **Dọn dẹp trong quá trình thực hành:** Xóa toàn bộ ảnh kiểm thử trong thư mục `/failed-uploads/` và kiểm tra xác nhận không có máy chủ EC2 hay NAT Gateway nào đang chạy ngầm.
2. **Kế hoạch sau khi kết thúc môn học:** Sau khi hoàn tất buổi vấn đáp và bảo vệ đồ án, nhóm sẽ thực thi các lệnh hủy tài nguyên để giải phóng hoàn toàn hạ tầng trên AWS Learner Lab:

    aws rekognition delete-collection --collection-id student-face-collection --region us-east-1
    aws s3 rb s3://student-attendance-rekognition-24110256 --force --region us-east-1
    aws dynamodb delete-table --table-name Students --region us-east-1
    aws dynamodb delete-table --table-name AttendanceRecords --region us-east-1
    aws dynamodb delete-table --table-name AttendanceManualReview --region us-east-1

---

## 6. Tổng kết & Đánh giá Đồ án

- **Kết quả đạt được:**
  - Hoàn thành đầy đủ các yêu cầu kỹ thuật của đề tài theo đúng tiến độ 4 tuần được giao.
  - Hệ thống vận hành ổn định, xử lý linh hoạt nhờ cơ chế dự phòng 2 tầng và bảo đảm an toàn dữ liệu cá nhân theo quy định.
  - Có đầy đủ minh chứng thực tế trên AWS Console, mã nguồn chuẩn hóa trên GitHub, tài liệu IaC CloudFormation và video demo trực quan.
- **Bài học kinh nghiệm:**
  - Nắm vững nguyên lý hoạt động của kiến trúc Serverless Event-driven và cách phối hợp giữa các dịch vụ S3, Lambda, Rekognition, DynamoDB và API Gateway.
  - Rèn luyện kỹ năng kiểm soát bảo mật, phân quyền IAM theo nguyên tắc đặc quyền tối thiểu (Least Privilege) với `LabRole`.
  - Kỹ năng tối ưu hóa chi phí vận hành dịch vụ điện toán đám mây trong các bài toán thực tế.
