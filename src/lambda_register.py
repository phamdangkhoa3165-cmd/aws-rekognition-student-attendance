import json
import urllib.parse
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')

COLLECTION_ID = 'student-face-collection'
STUDENTS_TABLE = 'Students'

def lambda_handler(event, context):
    """
    Kích hoạt khi có ảnh tải lên /registered-faces/.
    Định dạng tên file ảnh: MSSV_HoTen.jpg (Ví dụ: 24110256_PhamDangKhoa.jpg)
    """
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        
        if key.endswith('/') or not key.startswith('registered-faces/'):
            continue
            
        filename = key.split('/')[-1]
        raw_name = filename.rsplit('.', 1)[0]
        parts = raw_name.split('_', 1)
        student_id = parts[0]
        full_name = parts[1] if len(parts) > 1 else "Unknown"

        try:
            # 1. Trích xuất vector đặc trưng và nạp vào Collection
            response = rekognition_client.index_faces(
                CollectionId=COLLECTION_ID,
                Image={'S3Object': {'Bucket': bucket, 'Name': key}},
                ExternalImageId=student_id,
                MaxFaces=1,
                QualityFilter="AUTO",
                DetectionAttributes=['DEFAULT']
            )

            face_records = response.get('FaceRecords', [])
            if not face_records:
                print(f"[CẢNH BÁO] Không tìm thấy khuôn mặt hợp lệ trong ảnh: {key}")
                return {'statusCode': 400, 'body': 'Không phát hiện khuôn mặt'}

            face_id = face_records[0]['Face']['FaceId']

            # 2. Lưu mapping MSSV, FaceId vào DynamoDB
            table = dynamodb.Table(STUDENTS_TABLE)
            table.put_item(
                Item={
                    'StudentId': student_id,
                    'FullName': full_name,
                    'FaceId': face_id,
                    'S3ImageKey': key,
                    'RegisteredAt': datetime.now().isoformat()
                }
            )
            print(f"[THÀNH CÔNG] Đã đăng ký sinh viên: {student_id} - FaceId: {face_id}")

        except ClientError as e:
            print(f"[LỖI HỆ THỐNG] Lỗi khi xử lý Rekognition/DynamoDB: {str(e)}")
            raise e

    return {'statusCode': 200, 'body': json.dumps('Đăng ký khuôn mặt thành công')}
