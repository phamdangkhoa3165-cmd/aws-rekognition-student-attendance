import json
import boto3
from datetime import datetime
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = 'student-attendance-rekognition-24110256'
COLLECTION_ID = 'student-face-collection'
STUDENTS_TABLE = 'Students'
ATTENDANCE_TABLE = 'AttendanceRecords'
MANUAL_REVIEW_TABLE = 'AttendanceManualReview'

# Quy định giới hạn quyền riêng tư của đề tài
TEST_SAFE_FACE_LIMIT = 50    # Giới hạn sản phẩm dự kiến (<= 50 khuôn mặt)
HARD_MAX_FACE_LIMIT = 1000   # Giới hạn tối đa của đề tài (<= 1.000 khuôn mặt)

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'OPTIONS,GET,POST'
}

def get_collection_face_count():
    """Kiểm tra số lượng vector khuôn mặt đang lưu trong Rekognition Collection"""
    try:
        res = rekognition_client.describe_collection(CollectionId=COLLECTION_ID)
        return res.get('FaceCount', 0)
    except ClientError:
        return 0

def lambda_handler(event, context):
    # 1. Xử lý CORS Preflight request từ trình duyệt Web
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps({'message': 'CORS OK'})}

    # 2. Đọc tham số từ cả API Gateway Proxy (GET/POST) và Lambda Test Event
    payload = {}
    if event.get('queryStringParameters'):
        payload.update(event['queryStringParameters'])
    if event.get('body'):
        body_parsed = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        if isinstance(body_parsed, dict):
            payload.update(body_parsed)
    if not payload and isinstance(event, dict):
        payload = event

    action = payload.get('action', 'GET_ATTENDANCE')
    class_date = payload.get('class_date', datetime.now().strftime('%Y-%m-%d'))

    att_table = dynamodb.Table(ATTENDANCE_TABLE)
    review_table = dynamodb.Table(MANUAL_REVIEW_TABLE)
    student_table = dynamodb.Table(STUDENTS_TABLE)

    try:
        current_faces = get_collection_face_count()

        # === TÁC VỤ 1: TRA CỨU KẾT QUẢ ĐIỂM DANH, FALLBACK & TRẠNG THÁI PRIVACY ===
        if action == 'GET_ATTENDANCE':
            att_res = att_table.query(
                KeyConditionExpression=Key('ClassDate').eq(class_date)
            )
            review_res = review_table.scan()
            students_res = student_table.scan()

            return {
                'statusCode': 200,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'classDate': class_date,
                    'privacyCompliance': {
                        'policy': 'Chỉ sử dụng ảnh của thành viên nhóm hoặc người đã đồng ý cung cấp.',
                        'currentFaceCount': current_faces,
                        'testFaceLimit': TEST_SAFE_FACE_LIMIT,
                        'hardMaxFaceLimit': HARD_MAX_FACE_LIMIT,
                        's3PublicAccessBlocked': True
                    },
                    'totalRegisteredStudents': len(students_res.get('Items', [])),
                    'presentCount': len(att_res.get('Items', [])),
                    'registeredStudents': students_res.get('Items', []),
                    'attendanceList': att_res.get('Items', []),
                    'fallbackReviewList': review_res.get('Items', [])
                }, ensure_ascii=False)
            }

        # === TÁC VỤ 2: CẤP PRE-SIGNED URL UPLOAD ẢNH (CÓ KIỂM SOÁT QUYỀN RIÊNG TƯ) ===
        elif action == 'GET_UPLOAD_URL':
            privacy_consent = payload.get('privacy_consent', False)
            upload_type = payload.get('upload_type', 'class-photos')
            file_name = payload.get('file_name', f'photo_{int(datetime.now().timestamp())}.jpg')

            # Chặn nếu người dùng chưa xác nhận sự đồng ý quyền riêng tư
            if not privacy_consent or str(privacy_consent).lower() != 'true':
                return {
                    'statusCode': 400,
                    'headers': CORS_HEADERS,
                    'body': json.dumps({
                        'error': 'PRIVACY_CONSENT_REQUIRED',
                        'message': 'Từ chối cấp quyền tải ảnh: Bạn bắt buộc phải xác nhận ảnh có sự đồng ý của người trong ảnh.'
                    }, ensure_ascii=False)
                }

            # Chặn nếu vượt quá giới hạn khuôn mặt cho phép
            if upload_type == 'registered-faces' and current_faces >= TEST_SAFE_FACE_LIMIT:
                return {
                    'statusCode': 403,
                    'headers': CORS_HEADERS,
                    'body': json.dumps({
                        'error': 'FACE_QUOTA_EXCEEDED',
                        'message': f'Từ chối đăng ký: Số khuôn mặt ({current_faces}) đã chạm giới hạn an toàn ({TEST_SAFE_FACE_LIMIT} / tối đa {HARD_MAX_FACE_LIMIT}).'
                    }, ensure_ascii=False)
                }

            folder = 'registered-faces' if upload_type == 'registered-faces' else 'class-photos'
            object_key = f"{folder}/{file_name}"

            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': BUCKET_NAME,
                    'Key': object_key,
                    'ContentType': 'image/jpeg'
                },
                ExpiresIn=300  # URL tự hủy sau 5 phút để bảo mật
            )

            return {
                'statusCode': 200,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'uploadUrl': presigned_url,
                    'objectKey': object_key,
                    'expiresInSeconds': 300,
                    'currentFaceCount': current_faces
                }, ensure_ascii=False)
            }

        # === TÁC VỤ 3: GIẢNG VIÊN DUYỆT TAY CÁC TRƯỜNG HỢP FALLBACK ===
        elif action == 'MANUAL_APPROVE':
            review_id = payload.get('review_id')
            student_id = payload.get('student_id')
            now_iso = datetime.now().isoformat()

            if not student_id:
                return {'statusCode': 400, 'headers': CORS_HEADERS, 'body': json.dumps({'error': 'Thiếu mã số sinh viên (student_id)'}, ensure_ascii=False)}

            att_table.put_item(
                Item={
                    'ClassDate': class_date,
                    'StudentId': student_id,
                    'AttendanceTime': now_iso,
                    'Status': 'PRESENT',
                    'Confidence': '100.0 (Manual)',
                    'SourceImage': 'manual-override',
                    'VerificationType': 'MANUAL_FALLBACK_APPROVED'
                }
            )

            if review_id:
                review_table.update_item(
                    Key={'ReviewId': review_id},
                    UpdateExpression="SET #s = :val, ApprovedStudentId = :sid, UpdatedAt = :t",
                    ExpressionAttributeNames={'#s': 'Status'},
                    ExpressionAttributeValues={
                        ':val': 'RESOLVED_MANUAL_PRESENT',
                        ':sid': student_id,
                        ':t': now_iso
                    }
                )

            return {
                'statusCode': 200,
                'headers': CORS_HEADERS,
                'body': json.dumps({'message': f'Đã xác nhận điểm danh thủ công cho MSSV {student_id}'}, ensure_ascii=False)
            }

        return {'statusCode': 400, 'headers': CORS_HEADERS, 'body': json.dumps({'error': f'Action không hợp lệ: {action}'})}

    except ClientError as e:
        return {'statusCode': 500, 'headers': CORS_HEADERS, 'body': json.dumps({'error': str(e)})}
