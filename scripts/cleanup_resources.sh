#!/bin/bash
# ==============================================================================
# SCRIPT DỌN DẸP TÀI NGUYÊN CUỐI KỲ (RESOURCE CLEANUP)
# Đề tài: Nhận diện khuôn mặt điểm danh sinh viên với Amazon Rekognition
# Sinh viên: Phạm Đăng Khoa (24110256) - Huỳnh Quảng Tín (24110353)
# Region: us-east-1
# ==============================================================================

REGION="us-east-1"
BUCKET_NAME="student-attendance-rekognition-24110256"
COLLECTION_ID="student-face-collection"

echo "=== [1/4] Kiểm tra và xóa các tệp ảnh kiểm thử tạm trong thư mục cách ly failed-uploads/ ==="
aws s3 rm s3://$BUCKET_NAME/failed-uploads/ --recursive --region $REGION

echo "=== [2/4] Kiểm tra danh sách EC2 / NAT Gateway (Đảm bảo không phát sinh phí ngầm) ==="
aws ec2 describe-instances --region $REGION --query "Reservations[*].Instances[*].[InstanceId,State.Name]" --output table
aws ec2 describe-nat-gateways --region $REGION --query "NatGateways[*].[NatGatewayId,State]" --output table

echo "=== [3/4] Thống kê dung lượng S3 Bucket và trạng thái Rekognition Collection hiện tại ==="
aws s3 ls s3://$BUCKET_NAME --recursive --human-readable --summarize --region $REGION
aws rekognition describe-collection --collection-id $COLLECTION_ID --region $REGION

echo "=== [4/4] Lệnh xóa toàn bộ tài nguyên sau khi kết thúc chấm điểm báo cáo cuối kỳ ==="
echo "# Khi hoàn tất vấn đáp cuối kỳ, bỏ comment các lệnh dưới đây để xóa hoàn toàn:"
echo "# aws rekognition delete-collection --collection-id $COLLECTION_ID --region $REGION"
echo "# aws s3 rb s3://$BUCKET_NAME --force --region $REGION"
echo "# aws dynamodb delete-table --table-name Students --region $REGION"
echo "# aws dynamodb delete-table --table-name AttendanceRecords --region $REGION"
echo "# aws dynamodb delete-table --table-name AttendanceManualReview --region $REGION"
echo "=== Hoàn tất kiểm tra và dọn dẹp tài nguyên tạm! ==="
