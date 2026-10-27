import os
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

DEFAULT_SAFE_FACE_LIMIT = int(os.environ.get('TEST_SAFE_FACE_LIMIT', 50))
HARD_MAX_FACE_LIMIT = 1000

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'OPTIONS,GET,POST'
}

def get_collection_face_count():
    try:
        res = rekognition_client.describe_collection(CollectionId=COLLECTION_ID)
        return res.get('FaceCount', 0)
    except ClientError:
        return 0

def lambda_handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps({'message': 'CORS OK'})}

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
                    'httpStatus': 200,
                    'classDate': class_date,
                    'privacyCompliance': {
                        'policy': 'Chỉ sử dụng ảnh của thành viên nhóm hoặc người đã đồng ý cung cấp.',
                        'currentFaceCount': current_faces,
                        'testFaceLimit': DEFAULT_SAFE_FACE_LIMIT,
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

        elif action == 'GET_UPLOAD_URL':
            privacy_consent = payload.get('privacy_consent', False)
            upload_type = payload.get('upload_type', 'class-photos')
            file_name = payload.get('file_name', f'photo_{int(datetime.now().timestamp())}.jpg')
            effective_limit = int(payload.get('quota_limit', DEFAULT_SAFE_FACE_LIMIT))

            # Kịch bản chặn 1: Chưa xác nhận đồng ý quyền riêng tư -> Trả về HTTP 400
            if not privacy_consent or str(privacy_consent).lower() != 'true':
                return {
                    'statusCode': 400,
                    'headers': CORS_HEADERS,
                    'body': json.dumps({
                        'httpStatus': 400,
                        'error': 'PRIVACY_CONSENT_REQUIRED',
                        'message': 'HTTP 400 Bad Request - Từ chối cấp Pre-signed URL: Bạn bắt buộc phải tích xác nhận có sự đồng ý của người trong ảnh.'
                    }, ensure_ascii=False)
                }

            # Kịch bản chặn 2: Chạm hoặc vượt ngưỡng Quota khuôn mặt -> Trả về HTTP 403
            if upload_type == 'registered-faces' and (current_faces >= effective_limit or current_faces >= HARD_MAX_FACE_LIMIT):
                return {
                    'statusCode': 403,
                    'headers': CORS_HEADERS,
                    'body': json.dumps({
                        'httpStatus': 403,
                        'error': 'FACE_QUOTA_EXCEEDED',
                        'currentFaceCount': current_faces,
                        'appliedQuotaLimit': effective_limit,
                        'hardMaxLimit': HARD_MAX_FACE_LIMIT,
                        'message': f'HTTP 403 Forbidden - Từ chối đăng ký: Số khuôn mặt hiện tại trong Collection ({current_faces}) đã chạm/vượt ngưỡng giới hạn cho phép ({effective_limit} / tối đa {HARD_MAX_FACE_LIMIT}).'
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
                ExpiresIn=300
            )

            return {
                'statusCode': 200,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'httpStatus': 200,
                    'uploadUrl': presigned_url,
                    'objectKey': object_key,
                    'expiresInSeconds': 300,
                    'currentFaceCount': current_faces,
                    'appliedQuotaLimit': effective_limit
                }, ensure_ascii=False)
            }

        elif action == 'MANUAL_APPROVE':
            review_id = payload.get('review_id')
            student_id = payload.get('student_id')
            now_iso = datetime.now().isoformat()

            if not student_id:
                return {'statusCode': 400, 'headers': CORS_HEADERS, 'body': json.dumps({'error': 'Thiếu MSSV (student_id)'}, ensure_ascii=False)}

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
                'body': json.dumps({'httpStatus': 200, 'message': f'Đã xác nhận điểm danh thủ công cho MSSV {student_id}'}, ensure_ascii=False)
            }

        return {'statusCode': 400, 'headers': CORS_HEADERS, 'body': json.dumps({'error': f'Action không hợp lệ: {action}'})}

    except ClientError as e:
        return {'statusCode': 500, 'headers': CORS_HEADERS, 'body': json.dumps({'error': str(e)})}
