# AWS Rekognition Student Face Attendance System (Serverless Architecture)

Đồ án môn học: **Điện toán đám mây (Cloud Computing)** – Học kỳ 1, Năm học 2026–2027  
Đơn vị đào tạo: **Trường Đại học Công nghệ Kỹ thuật TP. Hồ Chí Minh (HCM-UTE)**  
**Giảng viên hướng dẫn:** ThS. Huỳnh Xuân Phụng  

### Nhóm sinh viên thực hiện:
- **Phạm Đăng Khoa** – MSSV: **24110256**  
- **Huỳnh Quảng Tín** – MSSV: **24110353**  

---

## 1. Giới thiệu tổng quan
Hệ thống điểm danh sinh viên tự động ứng dụng trí tuệ nhân tạo (AI/ML) theo mô hình phi máy chủ (**AWS Serverless**) triển khai thực tế trên nền tảng **AWS Learner Lab** (Region `us-east-1`). Hệ thống giải quyết bài toán điểm danh lớp học bằng cách đối soát khuôn mặt từ ảnh chụp tập thể lớp với kho vector đặc trưng sinh viên, kết hợp cơ chế dự phòng đa tầng (**2-Tier Fallback Mechanism**) và bộ kiểm soát quyền riêng tư bằng kỹ thuật (**Privacy & Quota Guardrails**).

---

## 2. Kiến trúc hệ thống mở rộng (System Architecture - Tuần 3)

![Sơ đồ kiến trúc hệ thống](docs/architecture_diagram.jpg)

### Các thành phần dịch vụ AWS cốt lõi:
1. **Tầng Giao diện & Cổng API (Client & API Gateway Layer):**
   - **Web Client (`frontend/index.html`):** Giao diện quản trị hỗ trợ tra cứu dữ liệu điểm danh, phê duyệt danh sách chờ Fallback và tải ảnh lên S3 kèm hộp kiểm cam kết quyền riêng tư.
   - **Amazon API Gateway (`student-attendance-api` - ID: `x6b3w242ib`):** REST API chuẩn Regional tại `us-east-1`, cấu hình resource `/attendance` (hỗ trợ các phương thức `GET`, `POST`, `OPTIONS`), kích hoạt **Lambda Proxy Integration** và thiết lập **Throttling** (Rate: 10 req/s, Burst: 20 req/s).
2. **Tầng Lưu trữ & Kích hoạt sự kiện (Amazon S3):**
   - Bucket: `student-attendance-rekognition-24110256` kích hoạt **Block All Public Access: ON** 100% kết hợp cấu hình CORS.
   - Thư mục `/registered-faces/`: Tiếp nhận ảnh chân dung sinh viên $\rightarrow$ kích hoạt S3 Event Trigger gọi `RegisterFaceFunction`.
   - Thư mục `/class-photos/`: Tiếp nhận ảnh chụp lớp học $\rightarrow$ kích hoạt S3 Event Trigger gọi `AttendanceCheckFunction`.
   - Thư mục `/failed-uploads/`: Vùng cách ly tự động các tệp ảnh lỗi hỏng định dạng hoặc lỗi hệ thống (Fallback 2).
   - Tải ảnh an toàn từ trình duyệt Web thông qua **S3 Pre-signed URL** (tự động hết hạn sau 300 giây).
3. **Tầng Xử lý phi máy chủ (AWS Lambda - Runtime Python 3.12, LabRole):**
   - **`RegisterFaceFunction`:** Đọc ảnh từ `/registered-faces/`, gọi API Rekognition `IndexFaces` nạp vector và lưu thông tin vào DynamoDB `Students`.
   - **`AttendanceCheckFunction`:** Đọc ảnh từ `/class-photos/`, gọi Rekognition `SearchFacesByImage` (ngưỡng tương đồng $\ge 85\%$) để ghi nhận có mặt, hoặc kích hoạt Fallback Mechanism khi không khớp/lỗi tệp.
   - **`GetAttendanceAPI`:** Xử lý request từ API Gateway để truy vấn danh sách điểm danh, cấp S3 Pre-signed URL (kiểm tra consent và quota khuôn mặt) và hỗ trợ giảng viên duyệt tay Fallback (`MANUAL_APPROVE`).
4. **Tầng AI & Cơ sở dữ liệu (AI/ML & Database Layer):**
   - **Amazon Rekognition:** Quản lý Vector Collection `student-face-collection` (chỉ lưu vector toán học, không lưu ảnh gốc).
   - **Amazon DynamoDB (On-Demand Mode):** Gồm 3 bảng:
     - `Students` (PK: `StudentId`): Thông tin sinh viên và mã vector `FaceId`.
     - `AttendanceRecords` (PK: `ClassDate`, SK: `StudentId`): Nhật ký điểm danh chính thức.
     - `AttendanceManualReview` (PK: `ReviewId`): Hàng đợi duyệt dự phòng của cơ chế Fallback.
5. **Tầng Giám sát & Quản trị (Amazon CloudWatch & IAM):**
   - **CloudWatch Logs:** Chuẩn hóa Log Groups cho 3 hàm Lambda với thời hạn lưu trữ **Retention = 14 days** nhằm tối ưu chi phí.
   - **CloudWatch Alarm (`FaceAttendance-Lambda-Errors-Alarm`):** Cảnh báo tự động khi hàm xử lý điểm danh phát sinh lỗi ($Errors \ge 1$ trong chu kỳ 5 phút).
   - **CloudWatch Dashboard (`FaceAttendance-Monitoring-Dashboard`):** Bảng theo dõi trực quan các chỉ số `Invocations`, `Duration`, `Errors` của hệ thống.
   - **AWS IAM (`LabRole`):** Toàn bộ dịch vụ chạy dưới quyền thực thi có sẵn của AWS Learner Lab.

---

## 3. Chính sách Quyền riêng tư & Kỹ thuật Kiểm soát Giới hạn (Privacy & Quota Guardrails)
Tuân thủ nghiêm ngặt yêu cầu đề tài và chỉ đạo của GVHD:
- **Xác thực sự đồng ý (Consent Verification Gate):** Hệ thống chỉ thu thập và xử lý hình ảnh của thành viên nhóm hoặc cá nhân đã đồng ý cung cấp. Trên giao diện Web và trong hàm `GetAttendanceAPI`, việc cấp Pre-signed URL upload ảnh yêu cầu cờ `privacy_consent == True`. Nếu người dùng không tích chọn xác nhận, API trả về mã lỗi `400 Bad Request (PRIVACY_CONSENT_REQUIRED)`.
- **Thực thi giới hạn khuôn mặt bằng Code (Face Quota Enforcement):**
  - Giới hạn an toàn thử nghiệm: $\le 50$ khuôn mặt.
  - Giới hạn tối đa toàn hệ thống: $\le 1.000$ khuôn mặt.
  - Trước khi cấp Pre-signed URL đăng ký ảnh thẻ mới, Lambda tự động gọi `rekognition_client.describe_collection()` để kiểm tra chỉ số `FaceCount`. Nếu số lượng chạm ngưỡng, API lập tức chặn và trả về `403 Forbidden (FACE_QUOTA_EXCEEDED)`.
- **Bảo mật dữ liệu lưu trữ:** S3 Bucket duy trì thiết lập **Block All Public Access: ON**. Không mở bất kỳ quyền truy cập công khai nào ra Internet.
- **Quy chuẩn Tagging:** Toàn bộ tài nguyên trên AWS đều được gắn thẻ: `Project: FaceAttendance` và `Owner: Khoa-Tin`.

---

## 4. Cơ chế Dự phòng (2-Tier Fallback Mechanism)
Hệ thống thiết lập cơ chế xử lý dự phòng 2 tầng tại [`src/lambda_attendance.py`](src/lambda_attendance.py) và [`src/lambda_get_attendance.py`](src/lambda_get_attendance.py):

### Cấp độ 1: Recognition Fallback (Xử lý khi AI nhận diện không khớp hoặc độ tin cậy thấp)
- **Điều kiện kích hoạt:** Khuôn mặt bị mờ, góc nghiêng, thiếu sáng, sinh viên chưa đăng ký hoặc độ tương đồng $Similarity < 85\%$.
- **Xử lý tự động:** Hàm Lambda ghi nhận bản ghi vào bảng `AttendanceManualReview` với trạng thái `PENDING_MANUAL_REVIEW` và lưu đường dẫn ảnh gốc.
- **Khắc phục:** Giảng viên đối chiếu ảnh gốc trực tiếp trên Web Dashboard và bấm nút **Duyệt tay MSSV** (`MANUAL_APPROVE`) để chuyển sinh viên sang bảng chính thức với cờ `VerificationType = MANUAL_FALLBACK_APPROVED`.

### Cấp độ 2: System Fault-Tolerance Fallback (Xử lý lỗi tệp hỏng hoặc sự cố hạ tầng)
- **Điều kiện kích hoạt:** Tải lên tệp ảnh hỏng định dạng (`InvalidImageFormatException`), vượt dung lượng hoặc Rekognition bị giới hạn tần suất (Rate Limit/Throttling).
- **Xử lý tự động:** Khối `try...except ClientError` trong Lambda tự động di chuyển tệp lỗi sang thư mục cách ly `/failed-uploads/` trên S3 để giải phóng luồng xử lý, đồng thời ghi log mã lỗi vào bảng `AttendanceManualReview` (`Status = SYSTEM_ERROR_ISOLATED`) và phát tín hiệu cảnh báo lên CloudWatch Logs.

---

## 5. Tiến độ thực hiện & Kết quả Kiểm thử (Roadmap)

### Bảng theo dõi tiến độ tổng thể:
- [x] **Tuần 1:** Thiết kế sơ đồ kiến trúc Serverless, khởi tạo VPC, kiểm tra IAM `LabRole`, tạo S3 Bucket (3 thư mục), 3 bảng DynamoDB On-demand, khởi tạo Rekognition Collection bằng AWS CLI và thiết kế Fallback Mechanism.
- [x] **Tuần 2:** Triển khai 3 hàm AWS Lambda (`RegisterFaceFunction`, `AttendanceCheckFunction`, `GetAttendanceAPI`), cấu hình S3 Event Triggers và kiểm thử thành công 5 kịch bản thành phần (TC-01 đến TC-05).
- [x] **Tuần 3:** Tích hợp Amazon API Gateway (CORS, Throttling), xây dựng Web Client Dashboard, thực thi kỹ thuật bảo mật quyền riêng tư & hạn mức 1.000 khuôn mặt, cấu hình CloudWatch (Logs retention, Alarm, Dashboard) và viết template CloudFormation IaC.
- [ ] **Tuần 4:** Kiểm thử toàn trình (End-to-End Testing), đánh giá tối ưu chi phí (Cost Optimization), dọn dẹp tài nguyên, hoàn thiện tài liệu báo cáo tổng kết và video demo ($\le 10$ phút).

### Bảng kết quả kiểm thử chức năng Tuần 2 & Tuần 3:

| Mã Test | Thành phần kiểm thử | Dữ liệu đầu vào (Input) | Kết quả thực tế trên AWS (Actual Output) | Trạng thái |
| :---: | :--- | :--- | :--- | :---: |
| **TC-01** | **Lambda 1 + Rekognition `IndexFaces`** | Upload ảnh `24110256_PhamDangKhoa.jpg` vào `/registered-faces/` | S3 trigger Lambda 1; Rekognition sinh `FaceId`; bảng `Students` lưu MSSV, Họ tên, `FaceId`. | **PASS** |
| **TC-02** | **Lambda 2 + Rekognition `SearchFacesByImage`** | Upload ảnh điểm danh hợp lệ vào `/class-photos/` | Rekognition khớp khuôn mặt với $Similarity > 99\%$; bảng `AttendanceRecords` ghi nhận `Status = PRESENT`. | **PASS** |
| **TC-03** | **Fallback 1 (Recognition Fallback)** | Upload ảnh người chưa đăng ký vào `/class-photos/` | Độ khớp $< 85\%$; kích hoạt Fallback 1 ghi vào bảng `AttendanceManualReview` với trạng thái `PENDING_MANUAL_REVIEW`. | **PASS** |
| **TC-04** | **Fallback 2 (System Fault-Tolerance)** | Upload file hỏng định dạng `corrupted_image.jpg` vào `/class-photos/` | Khối `except ClientError` bắt lỗi, di chuyển file sang `/failed-uploads/` và ghi log `SYSTEM_ERROR_ISOLATED`. | **PASS** |
| **TC-05** | **Lambda 3 (`GetAttendanceAPI`)** | Gọi Test Event `GET_ATTENDANCE` và `MANUAL_APPROVE` | Trả về HTTP 200, danh sách điểm danh và cập nhật duyệt tay thành công bản ghi Fallback. | **PASS** |
| **TC-06** | **API Gateway + Pre-signed URL + S3 CORS** | Gửi POST request xin URL tải ảnh từ giao diện Web | API Gateway định tuyến thành công sang Lambda 3; sinh S3 Pre-signed URL; trình duyệt PUT ảnh trực tiếp lên S3 thành công. | **PASS** |
| **TC-07** | **Bảo mật Quyền riêng tư (Consent Check)** | Gửi yêu cầu tải ảnh khi bỏ chọn ô cam kết đồng ý | Lambda chặn xử lý, trả về mã lỗi HTTP 400 (`PRIVACY_CONSENT_REQUIRED`); không cấp Pre-signed URL. | **PASS** |
| **TC-08** | **Giám sát CloudWatch Alarm** | Gửi tệp lỗi kích hoạt chỉ số $Errors \ge 1$ trên Lambda | CloudWatch phát hiện lỗi và chuyển trạng thái `FaceAttendance-Lambda-Errors-Alarm` sang cảnh báo (In alarm). | **PASS** |

---

## 6. Cấu trúc thư mục & Danh mục liên kết trực tiếp (Direct Links)

```text
aws-rekognition-student-attendance/
├── README.md                          # Tài liệu tổng quan, kiến trúc, Fallback, Privacy & kiểm thử
├── docs/
│   └── architecture_diagram.jpg       # Sơ đồ kiến trúc hệ thống AWS Serverless
├── frontend/
│   └── index.html                     # Giao diện Web xem điểm danh, duyệt Fallback & tải ảnh
├── iac/
│   └── cloudformation_template.yaml   # Bản mẫu CloudFormation tự động hóa hạ tầng (IaC)
├── scripts/
│   └── setup_infrastructure.sh        # Script AWS CLI khởi tạo hạ tầng nền tảng
├── src/
│   ├── lambda_register.py             # Lambda 1: Đăng ký khuôn mặt sinh viên (IndexFaces)
│   ├── lambda_attendance.py           # Lambda 2: Điểm danh & Fallback 2 tầng (SearchFacesByImage)
│   └── lambda_get_attendance.py       # Lambda 3: API Gateway Proxy, Pre-signed URL & Quota check
├── tests/
│   └── test_events.json               # Bộ dữ liệu JSON payload kiểm thử các hàm Lambda
└── evidence/
    ├── 01_vpc_overview.jpg            # Minh chứng Tuần 1: Mạng VPC nền tảng
    ├── 02_iam_labrole.jpg             # Minh chứng Tuần 1: Quyền IAM LabRole
    ├── 03_s3_bucket.jpg               # Minh chứng Tuần 1: S3 Bucket & 3 thư mục
    ├── 04_dynamodb_tables.jpg         # Minh chứng Tuần 1: 3 bảng DynamoDB Active
    ├── 05_rekognition_cli.jpg         # Minh chứng Tuần 1: Khởi tạo Rekognition Collection
    ├── week2/                         # Thư mục 8 ảnh minh chứng triển khai Lambda & kiểm thử Tuần 2
    └── week3/                         # Thư mục 8 ảnh minh chứng API Gateway, Web, Privacy & CloudWatch
