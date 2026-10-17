# AWS Rekognition Student Face Attendance System (Serverless Architecture)

Đồ án môn học: **Điện toán đám mây (Cloud Computing)** – Học kỳ 1, Năm học 2026–2027  
Đơn vị: **Trường Đại học Công nghệ Kỹ thuật TP. Hồ Chí Minh (HCM-UTE)**  
**Giảng viên hướng dẫn:** ThS. Huỳnh Xuân Phụng 

### Nhóm sinh viên thực hiện:
- **Phạm Đăng Khoa** – MSSV: **24110256**
- **Huỳnh Quảng Tín** – MSSV: **24110353**

---

## 1. Giới thiệu tổng quan
Hệ thống điểm danh sinh viên tự động ứng dụng trí tuệ nhân tạo (AI/ML) theo kiến trúc **Serverless** triển khai trên nền tảng **AWS Learner Lab** (Region `us-east-1`). Hệ thống giải quyết bài toán điểm danh lớp học bằng cách tự động trích xuất đặc trưng khuôn mặt sinh viên khi đăng ký và đối soát trực tiếp từ ảnh chụp tập thể lớp học, kết hợp cơ chế dự phòng (**Fallback Mechanism**) đa tầng đảm bảo tính liên tục và chính xác.

---

## 2. Kiến trúc hệ thống (System Architecture)

![Sơ đồ kiến trúc hệ thống](docs/architecture_diagram.jpg)

### Các dịch vụ AWS cốt lõi:
1. **Hạ tầng mạng & Bảo mật (VPC & IAM):**
   - **VPC (`student-attendance-vpc` - `10.0.0.0/16`):** Gồm 2 Public Subnets và Internet Gateway.
   - **AWS IAM (`LabRole`):** Toàn bộ hàm Lambda và dịch vụ thực thi dưới quyền `LabRole` có sẵn của AWS Learner Lab (tuân thủ nguyên tắc không tạo IAM User/Role mới).
2. **Lưu trữ & Kích hoạt sự kiện (Amazon S3):**
   - Bucket: `student-attendance-rekognition-24110256` (Chế độ **Block All Public Access**).
   - `/registered-faces/`: Lưu ảnh chân dung sinh viên đăng ký $\rightarrow$ kích hoạt S3 Event Notification gọi `RegisterFaceFunction`.
   - `/class-photos/`: Lưu ảnh chụp lớp học $\rightarrow$ kích hoạt S3 Event Notification gọi `AttendanceCheckFunction`.
   - `/failed-uploads/`: Thư mục cách ly tự động các tệp ảnh bị lỗi định dạng hoặc lỗi hệ thống (Fallback 2).
3. **Xử lý phi máy chủ (AWS Lambda - Runtime Python 3.12):**
   - **Lambda 1 (`RegisterFaceFunction`):** Đọc ảnh từ `/registered-faces/`, gọi API `IndexFaces` nạp vector vào Rekognition Collection và lưu thông tin sinh viên vào bảng `Students`.
   - **Lambda 2 (`AttendanceCheckFunction`):** Đọc ảnh từ `/class-photos/`, gọi API `SearchFacesByImage` (ngưỡng `85%`), ghi nhận có mặt vào bảng `AttendanceRecords` hoặc kích hoạt **Fallback Mechanism** nếu không khớp/lỗi.
   - **Lambda 3 (`GetAttendanceAPI`):** Truy vấn danh sách điểm danh theo ngày và hỗ trợ giảng viên xác nhận thủ công (Manual Override) các bản ghi từ bảng dự phòng `AttendanceManualReview`.
4. **Trí tuệ nhân tạo (Amazon Rekognition):**
   - Collection ID: `student-face-collection` (Chỉ lưu trữ vector đặc trưng khuôn mặt, không lưu ảnh gốc).
5. **Cơ sở dữ liệu NoSQL (Amazon DynamoDB - Chế độ On-Demand):**
   - Bảng `Students`: Partition Key `StudentId` (String) – Lưu thông tin sinh viên và `FaceId`.
   - Bảng `AttendanceRecords`: Partition Key `ClassDate` (String), Sort Key `StudentId` (String) – Lưu kết quả điểm danh chính thức.
   - Bảng `AttendanceManualReview`: Partition Key `ReviewId` (String) – Lưu danh sách chờ rà soát của cơ chế Fallback.

---

## 3. Chính sách Quyền riêng tư (Privacy & Compliance)
- **Tôn trọng quyền riêng tư:** Dự án chỉ sử dụng hình ảnh của các thành viên trong nhóm và những cá nhân đã trực tiếp đồng ý cung cấp hình ảnh phục vụ học tập, nghiên cứu.
- **Giới hạn dữ liệu:** Quy mô kiểm thử dưới 50 khuôn mặt (tuân thủ chặt chẽ giới hạn $\le 1.000$ khuôn mặt của đề tài).
- **Bảo mật lưu trữ:** S3 Bucket chặn 100% truy cập công khai (`BlockPublicAcls=true`, `RestrictPublicBuckets=true`); chỉ các hàm Lambda nội bộ mới có quyền đọc/ghi thông qua `LabRole`.
- **Quản trị tài nguyên (Tagging):** Toàn bộ tài nguyên trên AWS được gắn thẻ chuẩn hóa `Project: FaceAttendance` và `Owner: Khoa-Tin`.

---

## 4. Cơ chế Dự phòng (2-Tier Fallback Mechanism)
Để đảm bảo quy trình điểm danh không bị gián đoạn trong môi trường lớp học thực tế, hệ thống triển khai cơ chế Fallback 2 cấp độ tại [`src/lambda_attendance.py`](src/lambda_attendance.py) và [`src/lambda_get_attendance.py`](src/lambda_get_attendance.py):

### Cấp độ 1: Recognition Fallback (Xử lý khi AI không nhận diện được hoặc độ tin cậy thấp)
- **Điều kiện kích hoạt:** Khuôn mặt trong ảnh lớp học bị che khuất, góc nghiêng, thiếu sáng, chưa đăng ký hoặc độ tương đồng `Similarity < 85%`.
- **Xử lý tự động:** Hàm `AttendanceCheckFunction` không hủy phiên mà tự động tạo bản ghi vào bảng DynamoDB `AttendanceManualReview` với trạng thái `PENDING_MANUAL_REVIEW` kèm đường dẫn ảnh gốc.
- **Khắc phục (Manual Override):** Giảng viên sử dụng chức năng `MANUAL_APPROVE` trên `GetAttendanceAPI` để duyệt tay sinh viên vào bảng điểm danh chính thức (`VerificationType = MANUAL_FALLBACK_APPROVED`) hoặc cho phép sinh viên xác nhận bổ sung bằng MSSV.

### Cấp độ 2: System Fault-Tolerance Fallback (Xử lý lỗi tệp hỏng hoặc sự cố hạ tầng)
- **Điều kiện kích hoạt:** Tệp tải lên bị hỏng định dạng (`InvalidImageFormatException`), ảnh không chứa khuôn mặt hợp lệ hoặc dịch vụ bị giới hạn băng thông (`ProvisionedThroughputExceededException` / Throttling).
- **Xử lý tự động:** Khối `try...except ClientError` bắt ngoại lệ, tự động sao chép tệp lỗi sang thư mục cách ly `/failed-uploads/` trên S3 và xóa tệp ở thư mục chính để tránh nghẽn hàng đợi sự kiện, đồng thời ghi mã lỗi chi tiết vào bảng `AttendanceManualReview` (`Status = SYSTEM_ERROR_ISOLATED`) và Amazon CloudWatch Logs.

---

## 5. Tiến độ thực hiện & Kết quả Kiểm thử (Tuần 1 & Tuần 2)

### Tiến độ theo tuần:
- [x] **Tuần 1:** Tìm hiểu dịch vụ, thiết kế sơ đồ kiến trúc, dựng nền tảng VPC, kiểm tra IAM `LabRole`, tạo S3 Bucket (3 folders), 3 bảng DynamoDB, khởi tạo Rekognition Collection qua CLI và thiết kế Fallback Mechanism.
- [x] **Tuần 2:** Triển khai 3 hàm AWS Lambda (`RegisterFaceFunction`, `AttendanceCheckFunction`, `GetAttendanceAPI`), cấu hình S3 Event Notifications và hoàn thành 5 kịch bản kiểm thử từng thành phần (Component Testing).
- [ ] **Tuần 3:** Tích hợp Amazon API Gateway, xây dựng Web Client xem kết quả điểm danh, cấu hình giám sát CloudWatch Alarms & bảo mật.
- [ ] **Tuần 4:** Kiểm thử tổng thể (End-to-End), tối ưu chi phí, dọn dẹp tài nguyên, hoàn thiện báo cáo và video demo.

### Bảng kết quả kiểm thử từng thành phần (Tuần 2):

| Mã Test | Thành phần kiểm thử | Đầu vào kiểm thử (Input) | Kết quả thực tế trên AWS (Actual Output) | Trạng thái |
| :---: | :--- | :--- | :--- | :---: |
| **TC-01** | **Lambda 1 + Rekognition `IndexFaces` + DynamoDB `Students`** | Upload ảnh `24110256_PhamDangKhoa.jpg` và `24110353_HuynhQuangTin.jpg` vào `registered-faces/` | S3 tự động kích hoạt Lambda 1; Rekognition sinh `FaceId`; bảng `Students` lưu chính xác MSSV, Họ tên và `FaceId`. | **PASS** |
| **TC-02** | **Lambda 2 + Rekognition `SearchFacesByImage` (Luồng chính)** | Upload ảnh lớp hợp lệ `att_success_khoa.jpg` vào `class-photos/` | Rekognition khớp khuôn mặt với `Confidence > 99%`; bảng `AttendanceRecords` ghi nhận `Status = PRESENT`, `VerificationType = AI_AUTOMATIC`. | **PASS** |
| **TC-03** | **Fallback 1 (Recognition Fallback)** | Upload ảnh người chưa đăng ký `att_unregistered_person.jpg` vào `class-photos/` | Không khớp ngưỡng 85%; Lambda 2 kích hoạt Fallback 1 ghi vào bảng `AttendanceManualReview` với trạng thái `PENDING_MANUAL_REVIEW`. | **PASS** |
| **TC-04** | **Fallback 2 (System Fault-Tolerance Fallback)** | Upload file hỏng định dạng `corrupted_image.jpg` vào `class-photos/` | Khối `except ClientError` bắt lỗi, tự động chuyển file sang `failed-uploads/` và ghi log `SYSTEM_ERROR_ISOLATED`. | **PASS** |
| **TC-05** | **Lambda 3 (`GetAttendanceAPI`)** | Gọi Test Event `GET_ATTENDANCE` và `MANUAL_APPROVE` từ [`tests/test_events.json`](tests/test_events.json) | Trả về HTTP 200 kèm JSON danh sách có mặt và cập nhật duyệt tay thành công bản ghi Fallback. | **PASS** |

---

## 6. Cấu trúc thư mục & Liên kết nhanh (Direct Links)

```text
aws-rekognition-student-attendance/
├── README.md                          # Tài liệu tổng quan, kiến trúc, Fallback & kết quả kiểm thử
├── docs/
│   └── architecture_diagram.jpg       # Sơ đồ kiến trúc hệ thống Serverless
├── scripts/
│   └── setup_infrastructure.sh        # Script AWS CLI khởi tạo S3, DynamoDB, Rekognition Collection
├── src/
│   ├── lambda_register.py             # Lambda 1: Đăng ký khuôn mặt sinh viên (IndexFaces)
│   ├── lambda_attendance.py           # Lambda 2: Điểm danh & xử lý Fallback 2 tầng (SearchFacesByImage)
│   └── lambda_get_attendance.py       # Lambda 3: API tra cứu điểm danh & duyệt tay Fallback
├── tests/
│   └── test_events.json               # Bộ JSON payload kiểm thử các hàm Lambda
└── evidence/
    ├── 01_vpc_overview.jpg            # Minh chứng Tuần 1: Hạ tầng mạng VPC
    ├── 02_iam_labrole.jpg             # Minh chứng Tuần 1: Quyền hạn IAM LabRole
    ├── 03_s3_bucket.jpg               # Minh chứng Tuần 1: S3 Bucket & 3 thư mục
    ├── 04_dynamodb_tables.jpg         # Minh chứng Tuần 1: 3 bảng DynamoDB Active
    ├── 05_rekognition_cli.jpg         # Minh chứng Tuần 1: Khởi tạo Rekognition Collection
    └── week2/                         # Thư mục minh chứng triển khai & kiểm thử Tuần 2
```

- **Mã nguồn Lambda:** [`src/lambda_register.py`](src/lambda_register.py) | [`src/lambda_attendance.py`](src/lambda_attendance.py) | [`src/lambda_get_attendance.py`](src/lambda_get_attendance.py)
- **Kịch bản kiểm thử JSON:** [`tests/test_events.json`](tests/test_events.json)
- **Script khởi tạo hạ tầng:** [`scripts/setup_infrastructure.sh`](scripts/setup_infrastructure.sh)
- **Minh chứng Tuần 1:** [`evidence/`](evidence/)
- **Minh chứng Tuần 2:** [`evidence/week2/`](evidence/week2/)
