# AWS Rekognition Student Face Attendance System (Serverless Architecture)

Đồ án môn học: **Điện toán đám mây (Cloud Computing)** - Học kỳ 1, Năm học 2026-2027  
Trường Đại học Sư phạm Kỹ thuật TP. Hồ Chí Minh (HCMUTE)  
**Giảng viên hướng dẫn:** ThS. Huỳnh Xuân Phụng  

### Nhóm sinh viên thực hiện:
- **Phạm Đăng Khoa** - MSSV: 24110256
- **Huỳnh Quảng Tín** - MSSV: 24110353

---

## 1. Tổng quan đề tài
Xây dựng hệ thống điểm danh sinh viên tự động ứng dụng AI/ML theo mô hình Serverless trên AWS (Region `us-east-1`). Hệ thống tự động so khớp khuôn mặt từ ảnh chụp tập thể lớp học với kho vector đặc trưng sinh viên đã đăng ký nhằm tối ưu hóa thời gian và độ chính xác trong điểm danh.

---

## 2. Kiến trúc hệ thống
Hệ thống kết hợp các dịch vụ Serverless cốt lõi:
- **Amazon S3:** Lưu trữ ảnh đăng ký ban đầu (`/registered-faces/`), ảnh lớp học (`/class-photos/`) và ảnh cách ly khi lỗi (`/failed-uploads/`).
- **Amazon Rekognition:** Quản lý Vector Collection (`student-face-collection`) và thực thi nhận diện khuôn mặt (`IndexFaces`, `SearchFacesByImage`).
- **AWS Lambda:** Xử lý logic nghiệp vụ phi máy chủ, gán quyền thực thi qua `LabRole`.
- **Amazon DynamoDB:** Quản trị cơ sở dữ liệu NoSQL ở chế độ On-demand gồm 3 bảng (`Students`, `AttendanceRecords`, `AttendanceManualReview`).
- **Amazon CloudWatch:** Ghi log hệ thống và cảnh báo lỗi.

---

## 3. Chính sách Quyền riêng tư (Privacy & Data Compliance)
- **Tôn trọng quyền riêng tư:** Dự án chỉ sử dụng hình ảnh của thành viên trong nhóm và các cá nhân đã trực tiếp đồng ý cho phép sử dụng phục vụ nghiên cứu học tập.
- **Quy mô an toàn:** Số lượng khuôn mặt lưu trữ dưới 50 khuôn mặt (tuân thủ giới hạn tối đa 1.000 khuôn mặt theo yêu cầu đồ án).
- **Bảo mật dữ liệu:** S3 Bucket được kích hoạt tính năng **Block All Public Access** 100%, không mở public ra Internet; chỉ các hàm Lambda nội bộ được ủy quyền qua `LabRole` mới có quyền truy cập dữ liệu.

---

## 4. Cơ chế Dự phòng (Fallback Mechanism)
Để khắc phục bài toán nhận diện thực tế và tránh làm gián đoạn buổi điểm danh, hệ thống thiết kế cơ chế Fallback 2 tầng:

### a. Cơ chế Fallback nhận diện (Recognition Fallback)
- **Nguyên nhân kích hoạt:** Sinh viên bị khuất mặt, thiếu sáng, góc nghiêng hoặc độ tin cậy so khớp dưới ngưỡng 85% (`Confidence < 85%`).
- **Hành động xử lý:** Hệ thống không dừng phiên hay báo lỗi đỏ, mà tự động ghi nhận bản ghi vào bảng DynamoDB `AttendanceManualReview` với trạng thái `PENDING_MANUAL_REVIEW`.
- **Giải pháp xử lý:** Giảng viên đối chiếu ảnh gốc để xác nhận bằng tay trên hệ thống hoặc sinh viên được phép điểm danh bổ sung bằng hình thức xác nhận MSSV.

### b. Cơ chế Fallback sự cố hạ tầng (System Fault-Tolerance Fallback)
- **Nguyên nhân kích hoạt:** Tải lên tệp ảnh hỏng, định dạng không được hỗ trợ hoặc dịch vụ Rekognition bị giới hạn băng thông (Throttling/Rate Limit).
- **Hành động xử lý:** Khối ngoại lệ `try...except ClientError` trong Lambda tự động di chuyển tệp ảnh lỗi sang thư mục cách ly `/failed-uploads/` trên S3 để giải phóng luồng xử lý cho các ảnh khác, đồng thời ghi lại mã lỗi chi tiết vào DynamoDB và CloudWatch Logs.

---

## 5. Cấu trúc thư mục mã nguồn
```text
├── README.md                      # Tài liệu tổng quan, Privacy Policy & Fallback Mechanism
├── scripts/
│   └── setup_infrastructure.sh    # Script AWS CLI khởi tạo toàn bộ hạ tầng nền tảng
├── src/
│   ├── lambda_register.py         # Hàm Lambda đăng ký khuôn mặt (IndexFaces)
│   └── lambda_attendance.py       # Hàm Lambda điểm danh (Tích hợp Fallback Mechanism)
└── docs/
    └── architecture_diagram.png   # Sơ đồ kiến trúc hệ thống chi tiết
