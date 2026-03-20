import json
import os
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from PySide6.QtCore import QThread, Signal


class SyncWorker(QThread):
    """Check R2 for existing video files and update the API for any that exist but aren't marked as uploaded."""
    # (lesson_title, quality, status) - status: "found", "missing", "updated", "error", "skipped"
    progress = Signal(str, str, str)
    # (updated_count, skipped_count, missing_count, error_count)
    finished_result = Signal(int, int, int, int)

    def __init__(self, groups_data: list[dict], course_storage_path: str,
                 api_base_url: str, api_auth_header: str, parent=None):
        super().__init__(parent)
        self.groups_data = groups_data
        self.course_storage_path = course_storage_path.rstrip("/")
        self._api_base_url = api_base_url.rstrip("/")
        self._api_auth_header = api_auth_header

        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("R2_ENDPOINT_URL", ""),
            aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY", ""),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.bucket = os.environ.get("R2_BUCKET_NAME", "")

    def run(self):
        updated = 0
        skipped = 0
        missing = 0
        errors = 0

        for group in self.groups_data:
            for lesson in group.get("lessons", []):
                lesson_id = lesson.get("id", 0)
                lesson_title = self._localized(lesson.get("title", ""))
                videos = lesson.get("videos", [])

                for video in videos:
                    quality = video.get("quality", "")
                    video_id = video.get("id")
                    is_uploaded = video.get("is_uploaded", False)
                    duration = video.get("duration", 0)

                    if not video_id or not quality:
                        continue

                    if is_uploaded:
                        self.progress.emit(lesson_title, quality, "skipped")
                        skipped += 1
                        continue

                    # Check if file exists on R2
                    r2_key = f"{self.course_storage_path}/{lesson_id}_{quality}.mp4"
                    if self._file_exists(r2_key):
                        self.progress.emit(lesson_title, quality, "found")
                        try:
                            self._update_video(video_id, int(duration))
                            self.progress.emit(lesson_title, quality, "updated")
                            updated += 1
                        except Exception as e:
                            self.progress.emit(lesson_title, quality, f"error: {e}")
                            errors += 1
                    else:
                        self.progress.emit(lesson_title, quality, "missing")
                        missing += 1

        self.finished_result.emit(updated, skipped, missing, errors)

    def _file_exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def _update_video(self, video_id: int, duration: int):
        url = f"{self._api_base_url}/v1/internal/videos/{video_id}"
        body = json.dumps({"is_uploaded": True, "duration": duration}).encode()
        req = Request(url, data=body, method="POST")
        req.add_header("Authorization", self._api_auth_header)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "VideoCourseManager/1.0")
        with urlopen(req) as resp:
            resp.read()

    @staticmethod
    def _localized(val):
        if isinstance(val, dict):
            return val.get("en") or val.get("ar") or next(iter(val.values()), "")
        return str(val) if val else ""
