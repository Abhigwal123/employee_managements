"""
Cloud storage utilities for file management
"""

import os
import io
from typing import Optional, BinaryIO
from google.cloud import storage


class CloudStorageManager:
    """Manages cloud storage operations"""
    
    def __init__(self):
        self.bucket_name = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET")
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        
        if self.bucket_name and self.project_id:
            try:
                self.client = storage.Client(project=self.project_id)
                self.bucket = self.client.bucket(self.bucket_name)
            except Exception as e:
                print(f"Warning: Could not initialize Google Cloud Storage: {e}")
                self.client = None
                self.bucket = None
        else:
            self.client = None
            self.bucket = None
    
    def upload_file(
        self, 
        file_path: str, 
        cloud_path: str, 
        content_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload a file to cloud storage
        
        Args:
            file_path: Local file path
            cloud_path: Cloud storage path
            content_type: MIME type of the file
        
        Returns:
            Public URL if successful, None otherwise
        """
        if not self.bucket:
            return None
        
        try:
            blob = self.bucket.blob(cloud_path)
            
            if content_type:
                blob.content_type = content_type
            
            blob.upload_from_filename(file_path)
            blob.make_public()
            
            return blob.public_url
        except Exception as e:
            print(f"Error uploading file to cloud storage: {e}")
            return None
    
    def upload_file_object(
        self, 
        file_obj: BinaryIO, 
        cloud_path: str, 
        content_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload a file object to cloud storage
        
        Args:
            file_obj: File-like object
            cloud_path: Cloud storage path
            content_type: MIME type of the file
        
        Returns:
            Public URL if successful, None otherwise
        """
        if not self.bucket:
            return None
        
        try:
            blob = self.bucket.blob(cloud_path)
            
            if content_type:
                blob.content_type = content_type
            
            blob.upload_from_file(file_obj)
            blob.make_public()
            
            return blob.public_url
        except Exception as e:
            print(f"Error uploading file object to cloud storage: {e}")
            return None
    
    def download_file(self, cloud_path: str, local_path: str) -> bool:
        """
        Download a file from cloud storage
        
        Args:
            cloud_path: Cloud storage path
            local_path: Local file path
        
        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            return False
        
        try:
            blob = self.bucket.blob(cloud_path)
            blob.download_to_filename(local_path)
            return True
        except Exception as e:
            print(f"Error downloading file from cloud storage: {e}")
            return False
    
    def delete_file(self, cloud_path: str) -> bool:
        """
        Delete a file from cloud storage
        
        Args:
            cloud_path: Cloud storage path
        
        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            return False
        
        try:
            blob = self.bucket.blob(cloud_path)
            blob.delete()
            return True
        except Exception as e:
            print(f"Error deleting file from cloud storage: {e}")
            return False
    
    def get_public_url(self, cloud_path: str) -> Optional[str]:
        """
        Get public URL for a file in cloud storage
        
        Args:
            cloud_path: Cloud storage path
        
        Returns:
            Public URL if file exists, None otherwise
        """
        if not self.bucket:
            return None
        
        try:
            blob = self.bucket.blob(cloud_path)
            if blob.exists():
                return blob.public_url
            return None
        except Exception as e:
            print(f"Error getting public URL: {e}")
            return None
    
    def list_files(self, prefix: str = "") -> list:
        """
        List files in cloud storage with optional prefix
        
        Args:
            prefix: Prefix to filter files
        
        Returns:
            List of file paths
        """
        if not self.bucket:
            return []
        
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            print(f"Error listing files: {e}")
            return []


# Global storage manager instance
storage_manager = CloudStorageManager()


def upload_task_file(
    user_id: int, 
    task_id: str, 
    file_path: str, 
    file_type: str = "output"
) -> Optional[str]:
    """
    Upload a task file to cloud storage
    
    Args:
        user_id: User ID
        task_id: Task ID
        file_path: Local file path
        file_type: Type of file (input, output, chart)
    
    Returns:
        Public URL if successful, None otherwise
    """
    filename = os.path.basename(file_path)
    cloud_path = f"tasks/{user_id}/{task_id}/{file_type}_{filename}"
    
    # Determine content type based on file extension
    content_type = None
    if filename.endswith('.xlsx'):
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif filename.endswith('.xls'):
        content_type = 'application/vnd.ms-excel'
    elif filename.endswith('.png'):
        content_type = 'image/png'
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        content_type = 'image/jpeg'
    elif filename.endswith('.pdf'):
        content_type = 'application/pdf'
    
    return storage_manager.upload_file(file_path, cloud_path, content_type)


def upload_task_file_object(
    user_id: int, 
    task_id: str, 
    file_obj: BinaryIO, 
    filename: str, 
    file_type: str = "output"
) -> Optional[str]:
    """
    Upload a task file object to cloud storage
    
    Args:
        user_id: User ID
        task_id: Task ID
        file_obj: File-like object
        filename: Name of the file
        file_type: Type of file (input, output, chart)
    
    Returns:
        Public URL if successful, None otherwise
    """
    cloud_path = f"tasks/{user_id}/{task_id}/{file_type}_{filename}"
    
    # Determine content type based on file extension
    content_type = None
    if filename.endswith('.xlsx'):
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif filename.endswith('.xls'):
        content_type = 'application/vnd.ms-excel'
    elif filename.endswith('.png'):
        content_type = 'image/png'
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        content_type = 'image/jpeg'
    elif filename.endswith('.pdf'):
        content_type = 'application/pdf'
    
    return storage_manager.upload_file_object(file_obj, cloud_path, content_type)


def delete_task_files(user_id: int, task_id: str) -> bool:
    """
    Delete all files for a task from cloud storage
    
    Args:
        user_id: User ID
        task_id: Task ID
    
    Returns:
        True if successful, False otherwise
    """
    prefix = f"tasks/{user_id}/{task_id}/"
    files = storage_manager.list_files(prefix)
    
    success = True
    for file_path in files:
        if not storage_manager.delete_file(file_path):
            success = False
    
    return success


def get_task_file_url(user_id: int, task_id: str, filename: str, file_type: str = "output") -> Optional[str]:
    """
    Get public URL for a task file
    
    Args:
        user_id: User ID
        task_id: Task ID
        filename: Name of the file
        file_type: Type of file (input, output, chart)
    
    Returns:
        Public URL if file exists, None otherwise
    """
    cloud_path = f"tasks/{user_id}/{task_id}/{file_type}_{filename}"
    return storage_manager.get_public_url(cloud_path)
