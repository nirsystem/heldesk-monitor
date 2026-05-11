import os
import uuid
from flask import current_app


def upload_file(file, ticket_id):
    bucket = current_app.config.get('S3_BUCKET')
    if not bucket:
        return None
    try:
        import boto3
        s3 = boto3.client('s3', region_name=current_app.config.get('AWS_REGION', 'us-east-1'))
        ext = os.path.splitext(file.filename or '')[1]
        s3_key = f'tickets/{ticket_id}/{uuid.uuid4().hex}{ext}'
        s3.upload_fileobj(
            file, bucket, s3_key,
            ExtraArgs={'ContentType': file.content_type or 'application/octet-stream'}
        )
        return s3_key
    except Exception as e:
        current_app.logger.error(f'S3 upload failed: {e}')
        return None


def get_presigned_url(s3_key, expires=3600):
    bucket = current_app.config.get('S3_BUCKET')
    if not bucket or not s3_key:
        return '#'
    try:
        import boto3
        s3 = boto3.client('s3', region_name=current_app.config.get('AWS_REGION', 'us-east-1'))
        return s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=expires
        )
    except Exception:
        return '#'
