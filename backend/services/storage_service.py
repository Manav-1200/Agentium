import os
import io
import uuid
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Optional, BinaryIO
from pathlib import Path

logger = logging.getLogger(__name__)

class StorageService:
    """Service for interacting with S3/MinIO object storage."""
    
    def __init__(self):
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL")
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "agentium-media")
        
        # Determine if we should use path style (usually True for MinIO)
        # S3_FORCE_PATH_STYLE helps local MinIO or similar compatible stores
        self.force_path_style = os.getenv("S3_FORCE_PATH_STYLE", "true").lower() == "true"

        # Initialize the S3 client using botocore logic wrapped by boto3
        session = boto3.session.Session()
        self.client = session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=boto3.session.Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'} if self.force_path_style else {}
            )
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure the target bucket exists, creating it if necessary."""
        try:
            # Avoid full list if possible by using head_bucket
            try:
                self.client.head_bucket(Bucket=self.bucket_name)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                # 404 means the bucket does not exist, 403 means we don't have permission to check
                if error_code == '404':
                    if self.region == 'us-east-1':
                        self.client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    logger.info(f"Created bucket {self.bucket_name}.")
                else:
                    logger.warning(f"Unable to verify bucket {self.bucket_name} access: {e}")
        except Exception as e:
            logger.error(f"Error ensuring bucket {self.bucket_name} exists: {e}")

    def upload_file(self, file_obj: BinaryIO, object_name: str, content_type: str = "application/octet-stream") -> Optional[str]:
        """
        Upload a file to an S3 bucket and return the persistent url.

        :param file_obj: File-like object to upload
        :param object_name: Destination S3 object name (e.g. users/{user_id}/file.jpg)
        :param content_type: MIME type of the file
        :return: Public URL if successful, else None
        """
        try:
            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_name,
                ExtraArgs={'ContentType': content_type}
            )
            return self.get_url(object_name)
        except ClientError as e:
            logger.error(f"Failed to upload {object_name}: {e}")
            return None

    def get_url(self, object_name: str) -> str:
        """
        Constructs the permanent public/internal url to the object.
        Depending on the S3 provider (AWS vs MinIO), this formats the URL automatically.
        """
        if self.endpoint_url is not None:
            base_url = self.endpoint_url.rstrip("/")
            if self.force_path_style:
                return f"{base_url}/{self.bucket_name}/{object_name}"
            else:
                return f"https://{self.bucket_name}.{base_url.replace('https://', '').replace('http://', '')}/{object_name}"
            
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_name}"

    def generate_presigned_url(self, object_name: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL to share an S3 object.
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {object_name}: {e}")
            return None

    def delete_file(self, object_name: str) -> bool:
        """
        Delete a file from the bucket.
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {object_name}: {e}")
            return False

    def list_files(self, prefix: str) -> list:
        """List files with a given prefix (e.g. user directory)."""
        try:
            response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            return response.get('Contents', [])
        except ClientError as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return []

# Global instance
storage_service = StorageService()
