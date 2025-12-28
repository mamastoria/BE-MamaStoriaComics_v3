"""
Google Cloud Storage Service
Handles file upload/download operations with Google Cloud Storage
"""
from google.cloud import storage
from google.oauth2 import service_account
from typing import Optional, BinaryIO
import os
from datetime import timedelta

from app.core.config import settings


class GoogleStorageService:
    """Service for Google Cloud Storage operations"""
    
    def __init__(self):
        """Initialize GCS client"""
        # Check if credentials file exists
        credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        
        if credentials_path and os.path.exists(credentials_path):
            # Use service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            self.client = storage.Client(
                project=settings.GOOGLE_PROJECT_ID,
                credentials=credentials
            )
        else:
            # Use Application Default Credentials (for Cloud Run)
            self.client = storage.Client(project=settings.GOOGLE_PROJECT_ID)
        
        self.bucket_name = settings.GOOGLE_BUCKET_NAME
        self.bucket = self.client.bucket(self.bucket_name)
    
    def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        content_type: Optional[str] = None,
        make_public: bool = True
    ) -> str:
        """
        Upload file to GCS
        
        Args:
            file_content: File content as bytes
            destination_path: Path in bucket (e.g., 'comics/123.jpg')
            content_type: MIME type (e.g., 'image/jpeg')
            make_public: Whether to make file publicly accessible
            
        Returns:
            Public URL of uploaded file
        """
        blob = self.bucket.blob(destination_path)
        
        # Upload file
        blob.upload_from_string(
            file_content,
            content_type=content_type
        )
        
        # Make public if requested
        if make_public:
            blob.make_public()
        
        return self.get_public_url(destination_path)
    
    def upload_from_file(
        self,
        file_obj: BinaryIO,
        destination_path: str,
        content_type: Optional[str] = None,
        make_public: bool = True
    ) -> str:
        """
        Upload file from file object
        
        Args:
            file_obj: File-like object
            destination_path: Path in bucket
            content_type: MIME type
            make_public: Whether to make file publicly accessible
            
        Returns:
            Public URL of uploaded file
        """
        blob = self.bucket.blob(destination_path)
        
        # Upload from file object
        blob.upload_from_file(
            file_obj,
            content_type=content_type
        )
        
        # Make public if requested
        if make_public:
            blob.make_public()
        
        return self.get_public_url(destination_path)
    
    def download_file(self, source_path: str) -> bytes:
        """
        Download file from GCS
        
        Args:
            source_path: Path in bucket
            
        Returns:
            File content as bytes
        """
        blob = self.bucket.blob(source_path)
        return blob.download_as_bytes()
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from GCS
        
        Args:
            file_path: Path in bucket
            
        Returns:
            True if deleted successfully
        """
        try:
            blob = self.bucket.blob(file_path)
            blob.delete()
            return True
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in GCS
        
        Args:
            file_path: Path in bucket
            
        Returns:
            True if file exists
        """
        blob = self.bucket.blob(file_path)
        return blob.exists()
    
    def get_public_url(self, file_path: str) -> str:
        """
        Get public URL for file
        
        Args:
            file_path: Path in bucket
            
        Returns:
            Public URL string
        """
        return f"https://storage.googleapis.com/{self.bucket_name}/{file_path}"
    
    def generate_signed_url(
        self,
        file_path: str,
        expiration_minutes: int = 60
    ) -> str:
        """
        Generate signed URL for private file access
        
        Args:
            file_path: Path in bucket
            expiration_minutes: URL expiration time in minutes
            
        Returns:
            Signed URL string
        """
        blob = self.bucket.blob(file_path)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )
        
        return url
    
    def list_files(self, prefix: Optional[str] = None) -> list:
        """
        List files in bucket
        
        Args:
            prefix: Optional prefix to filter files
            
        Returns:
            List of file paths
        """
        blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
        return [blob.name for blob in blobs]
    
    def get_file_metadata(self, file_path: str) -> dict:
        """
        Get file metadata
        
        Args:
            file_path: Path in bucket
            
        Returns:
            Dict with file metadata
        """
        blob = self.bucket.blob(file_path)
        blob.reload()
        
        return {
            "name": blob.name,
            "size": blob.size,
            "content_type": blob.content_type,
            "created": blob.time_created,
            "updated": blob.updated,
            "public_url": self.get_public_url(file_path) if blob.public_url else None
        }
