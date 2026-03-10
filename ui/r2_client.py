import os

import boto3
from botocore.config import Config
from PyQt6.QtCore import QObject, pyqtSignal, QThread


class _PresignThread(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, s3_client, bucket: str, key: str, parent=None):
        super().__init__(parent)
        self.s3_client = s3_client
        self.bucket = bucket
        self.key = key

    def run(self):
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": self.key},
                ExpiresIn=3600,
            )
            self.result.emit(url)
        except Exception as e:
            self.error.emit(str(e))


class R2Client(QObject):
    url_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._threads = []
        self.bucket = os.environ.get("R2_BUCKET_NAME", "")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("R2_ENDPOINT_URL", ""),
            aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY", ""),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def generate_url(self, storage_path: str, filename: str = ""):
        key = storage_path.lstrip("/")
        thread = _PresignThread(self.s3, self.bucket, key, self)
        thread.result.connect(self.url_ready.emit)
        thread.error.connect(self.error.emit)
        thread.finished.connect(lambda: self._threads.remove(thread))
        self._threads.append(thread)
        thread.start()
