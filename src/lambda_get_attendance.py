import json
import boto3
from datetime import datetime
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')

STUDENTS_TABLE = 'Students'
ATTENDANCE_TABLE = 'AttendanceRecords'
MANUAL_REVIEW_TABLE = 'AttendanceManualReview'

def lambda_handler(event, context):
    """
    Xử lý 2 tác vụ:
    1. GET: Truy vấn danh sách điểm danh theo ngày + danh sách chờ duyệt Fallback.
    2. POST (Fallback Manual Approve): Cho phép giảng viên duyệt tay sinh viên từ bảng Fallback sang bảng chính.
    """
    action = event.get('action', 'GET_ATTENDANCE')
    class_date = event.get('class_date', datetime.now().strftime('%Y-%m-%d'))

    att_table = dynamodb.Table(ATTENDANCE_TABLE)
    review_table = dynamodb.Table(MANUAL_REVIEW_TABLE)
    student_table = dynamodb.Table(STUDENTS_TABLE)

    try:
        # Tác vụ 1: Lấy báo cáo điểm danh và danh sách Fallback trong ngày
        if action == 'GET_ATTENDANCE':
            att_res = att_table.query(
                KeyConditionExpression=Key('ClassDate').eq(class_date)
            )
            review_res = review_table.scan()
            students_res = student_table.scan()

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'classDate': class_date,
                    'totalRegisteredStudents': len(students_res.get('Items', [])),
                    'presentCount': len(att_res.get('Items', [])),
                    'attendanceList': att_res.get('Items', []),
                    'fallbackReviewList': review_res.get('Items', [])
                }, ensure_ascii=False)
            }

        # Tác vụ 2: Giảng viên xác nhận thủ công cho trường hợp Fallback (Manual Override)
        elif action == 'MANUAL_APPROVE':
            review_id = event.get('review_id')
            student_id = event.get('student_id')
            now_iso = datetime.now().isoformat()

            # Ghi nhận có mặt vào bảng chính với cờ MANUAL_FALLBACK_APPROVED
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

            # Cập nhật trạng thái đã xử lý bên bảng Fallback
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
                'body': json.dumps({'message': f'Đã duyệt điểm danh thủ công cho MSSV {student_id}'}, ensure_ascii=False)
            }

    except ClientError as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
