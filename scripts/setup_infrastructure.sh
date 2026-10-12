#!/bin/bash
# AWS Infrastructure Provisioning Script for Face Attendance System
# Region: us-east-1 | Account Role: LabRole
REGION="us-east-1"
BUCKET_NAME="student-attendance-rekognition-24110256"
COLLECTION_ID="student-face-collection"

echo "=== 1. TẠO S3 BUCKET VÀ CÁC THƯ MỤC NGHIỆP VỤ + DỰ PHÒNG ==="
aws s3api create-bucket --bucket $BUCKET_NAME --region $REGION
aws s3api put-public-access-block --bucket $BUCKET_NAME \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Tạo các folder chức năng
aws s3api put-object --bucket $BUCKET_NAME --key "registered-faces/"
aws s3api put-object --bucket $BUCKET_NAME --key "class-photos/"
aws s3api put-object --bucket $BUCKET_NAME --key "failed-uploads/"

echo "=== 2. TẠO CÁC BẢNG DYNAMODB (CHẾ ĐỘ ON-DEMAND) ==="
# Bảng lưu thông tin sinh viên đăng ký
aws dynamodb create-table \
    --table-name Students \
    --attribute-definitions AttributeName=StudentId,AttributeType=S \
    --key-schema AttributeName=StudentId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region $REGION

# Bảng lưu kết quả điểm danh chính thức
aws dynamodb create-table \
    --table-name AttendanceRecords \
    --attribute-definitions AttributeName=ClassDate,AttributeType=S AttributeName=StudentId,AttributeType=S \
    --key-schema AttributeName=ClassDate,KeyType=HASH AttributeName=StudentId,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region $REGION

# Bảng dự phòng (Fallback Table) cho các trường hợp cần rà soát bằng tay
aws dynamodb create-table \
    --table-name AttendanceManualReview \
    --attribute-definitions AttributeName=ReviewId,AttributeType=S \
    --key-schema AttributeName=ReviewId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region $REGION

echo "=== 3. KHỞI TẠO REKOGNITION FACE COLLECTION ==="
aws rekognition create-collection --collection-id $COLLECTION_ID --region $REGION

echo "Khởi tạo hạ tầng thành công!"
