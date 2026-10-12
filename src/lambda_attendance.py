import json
import urllib.parse
import boto3
import uuid
from datetime import datetime
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')

COLLECTION_ID = 'student-face-collection'
ATTENDANCE_TABLE = 'AttendanceRecords'
MANUAL_REVIEW_TABLE = 'AttendanceManualReview'
CONFIDENCE_THRESHOLD = 85.0  # Ngưỡng tin cậy chuẩn

def lambda_handler(event, context):
    """
    Kích hoạt khi có ảnh chụp lớp học tải lên /class-photos/
    Tích hợp Cơ chế Dự phòng (Fallback Mechanism) 2 tầng:
    1. Recognition Fallback: Nếu không khớp hoặc độ tin cậy < 85%, đưa vào hàng đợi duyệt tay (AttendanceManualReview).
    2. System Fault-Tolerance Fallback: Nếu file hỏng hoặc lỗi phân tích, cách ly sang /failed-uploads/ và ghi log sự cố.
    """
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])

        if key.endswith('/') or not key.startswith('class-photos/'):
            continue

        class_date = datetime.now().strftime('%Y-%m-%d')
        attendance_time = datetime.now().isoformat()
        att_table = dynamodb.Table(ATTENDANCE_TABLE)
        review_table = dynamodb.Table(MANUAL_REVIEW_TABLE)

        try:
            # 1. Gọi Rekognition tìm kiếm các khuôn mặt từ ảnh chụp lớp
            response = rekognition_client.search_faces_by_image(
                CollectionId=COLLECTION_ID,
                Image={'S3Object': {'Bucket': bucket, 'Name': key}},
                FaceMatchThreshold=CONFIDENCE_THRESHOLD,
                MaxFaces=50
            )

            matched_faces = response.get('FaceMatches', [])

            # === NHÁNH XỬ LÝ CHÍNH: Nhận diện thành công >= 85% ===
            if matched_faces:
                for match in matched_faces:
                    student_id = match['Face'].get('ExternalImageId', 'UNKNOWN')
                    confidence = str(round(match['Similarity'], 2))

                    att_table.put_item(
                        Item={
                            'ClassDate': class_date,
                            'StudentId': student_id,
                            'AttendanceTime': attendance_time,
                            'Status': 'PRESENT',
                            'Confidence': confidence,
                            'SourceImage': key,
                            'VerificationType': 'AI_AUTOMATIC'
                        }
                    )
                    print(f"[ĐIỂM DANH] MSSV: {student_id} - Độ khớp: {confidence}%")

            # === FALLBACK 1 (RECOGNITION FALLBACK): Không tìm thấy khuôn mặt hợp lệ trong Collection ===
            else:
                print(f"[FALLBACK KÍCH HOẠT] Ảnh {key} không có khuôn mặt nào đạt ngưỡng {CONFIDENCE_THRESHOLD}%.")
                review_id = str(uuid.uuid4())
                review_table.put_item(
                    Item={
                        'ReviewId': review_id,
                        'ClassDate': class_date,
                        'SourceImage': key,
                        'Status': 'PENDING_MANUAL_REVIEW',
                        'FallbackReason': 'NO_FACE_MATCH_OR_LOW_CONFIDENCE',
                        'CreatedAt': attendance_time,
                        'Instructions': 'Giảng viên đối soát ảnh lớp hoặc sinh viên xác thực bổ sung qua MSSV.'
                    }
                )

        # === FALLBACK 2 (SYSTEM FAULT-TOLERANCE FALLBACK): Xử lý ngoại lệ file hỏng/lỗi hạ tầng ===
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"[HỆ THỐNG GẶP SỰ CỐ] Mã lỗi: {error_code} - {str(e)}")

            # Cách ly ảnh lỗi sang thư mục failed-uploads/ để không làm nghẽn luồng xử lý
            failed_key = key.replace('class-photos/', 'failed-uploads/')
            try:
                s3_client.copy_object(
                    Bucket=bucket,
                    CopySource={'Bucket': bucket, 'Key': key},
                    Key=failed_key
                )
                s3_client.delete_object(Bucket=bucket, Key=key)
            except Exception as copy_err:
                print(f"Lỗi khi di chuyển file: {str(copy_err)}")

            # Ghi log sự cố vào bảng ManualReview
            review_table.put_item(
                Item={
                    'ReviewId': str(uuid.uuid4()),
                    'ClassDate': class_date,
                    'SourceImage': failed_key,
                    'Status': 'SYSTEM_ERROR_ISOLATED',
                    'ErrorCode': error_code,
                    'ErrorMessage': str(e),
                    'CreatedAt': attendance_time
                }
            )

    return {'statusCode': 200, 'body': json.dumps('Xử lý điểm danh hoàn tất (Kèm Fallback Mechanism)')}
