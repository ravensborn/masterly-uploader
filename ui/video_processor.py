import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config
from PySide6.QtCore import QObject, Signal, QThread

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def _detect_hw_encoder() -> dict | None:
    """Detect available GPU encoder. Returns encoder config dict or None."""
    try:
        result = subprocess.run(
            [FFMPEG, "-encoders"], capture_output=True, text=True, timeout=5,
        )
        encoders = result.stdout
    except Exception:
        return None

    # Prefer NVENC (NVIDIA), then AMF (AMD), then QSV (Intel)
    if "h264_nvenc" in encoders:
        return {"codec": "h264_nvenc", "hwaccel": "cuda", "label": "NVIDIA NVENC", "extra": ["-preset", "p4", "-cq", "23"]}
    if "h264_amf" in encoders:
        return {"codec": "h264_amf", "hwaccel": "auto", "label": "AMD AMF", "extra": ["-quality", "balanced", "-qp_i", "23", "-qp_p", "23"]}
    if "h264_qsv" in encoders:
        return {"codec": "h264_qsv", "hwaccel": "qsv", "label": "Intel Quick Sync", "extra": ["-preset", "medium", "-global_quality", "23"]}
    return None


_HW_ENCODER = _detect_hw_encoder()

# GPU encoders handle ~3 concurrent sessions; CPU uses half the cores
MAX_WORKERS = 3 if _HW_ENCODER else max(1, (os.cpu_count() or 2) // 2)

def get_encoder_label() -> str:
    if _HW_ENCODER:
        return _HW_ENCODER["label"]
    return "CPU (libx264)"


class ProcessingTask:
    def __init__(self, lesson_id: int, lesson_title: str, source_file: str,
                 course_storage_path: str, qualities: list[str],
                 video_ids: dict[str, int] | None = None):
        self.lesson_id = lesson_id
        self.lesson_title = lesson_title
        self.source_file = source_file
        self.course_storage_path = course_storage_path.rstrip("/")
        self.qualities = qualities  # e.g. ["1080p", "720p"]
        self.video_ids = video_ids or {}  # quality -> video_id


QUALITY_MAP = {
    "1080p": {"height": 1080},
    "720p": {"height": 720},
}


class ProcessingWorker(QThread):
    # (task_index, quality, stage, progress_pct)
    # stage: "encoding", "deleting", "uploading", "done", "error"
    task_progress = Signal(int, str, str, int)
    # (task_index, quality, error_message)
    task_error = Signal(int, str, str)
    # emitted when GPU fails and we fall back to CPU
    encoder_fallback = Signal()
    # overall done
    all_done = Signal()

    def __init__(self, tasks: list[ProcessingTask], api_base_url: str = "", api_auth_header: str = "", parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self._cancelled = False
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

    def cancel(self):
        self._cancelled = True

    def run(self):
        # Build all jobs: (task_idx, task, quality)
        jobs = []
        for task_idx, task in enumerate(self.tasks):
            for quality in task.qualities:
                jobs.append((task_idx, task, quality))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {}
            for job in jobs:
                if self._cancelled:
                    break
                future = pool.submit(self._process_one, *job)
                futures[future] = job

            for future in as_completed(futures):
                task_idx, task, quality = futures[future]
                try:
                    future.result()
                except Exception as e:
                    self.task_error.emit(task_idx, quality, str(e))

        self.all_done.emit()

    def _process_one(self, task_idx: int, task: ProcessingTask, quality: str):
        if self._cancelled:
            return

        height = QUALITY_MAP.get(quality, {}).get("height", 1080)
        r2_key = f"{task.course_storage_path}/{task.lesson_id}_{quality}.mp4"
        filename = f"{task.lesson_id}_{quality}.mp4"

        # 1. Encode with ffmpeg
        self.task_progress.emit(task_idx, quality, "encoding", 0)
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)

        duration = self._get_duration(task.source_file)

        # Try GPU encoding first, fall back to CPU
        gpu_cmd = self._build_ffmpeg_cmd(task.source_file, height, output_path, use_gpu=True)
        cpu_cmd = self._build_ffmpeg_cmd(task.source_file, height, output_path, use_gpu=False)

        returncode, error_detail = self._run_ffmpeg(gpu_cmd if gpu_cmd != cpu_cmd else cpu_cmd, task_idx, quality, duration)

        # If GPU failed, retry with CPU
        if returncode != 0 and gpu_cmd != cpu_cmd:
            self.encoder_fallback.emit()
            self.task_progress.emit(task_idx, quality, "encoding", 0)
            returncode, error_detail = self._run_ffmpeg(cpu_cmd, task_idx, quality, duration)

        if returncode != 0:
            raise RuntimeError(f"ffmpeg exit code {returncode}:\n{error_detail}")

        self.task_progress.emit(task_idx, quality, "encoding", 100)

        if self._cancelled:
            return

        # 2. Delete old from R2
        self.task_progress.emit(task_idx, quality, "deleting", 0)
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=r2_key)
        except Exception:
            pass  # OK if it doesn't exist
        self.task_progress.emit(task_idx, quality, "deleting", 100)

        if self._cancelled:
            return

        # 3. Upload to R2
        self.task_progress.emit(task_idx, quality, "uploading", 0)
        file_size = os.path.getsize(output_path)
        uploaded = [0]

        def upload_callback(bytes_transferred):
            uploaded[0] += bytes_transferred
            if file_size > 0:
                pct = min(int(uploaded[0] / file_size * 100), 99)
                self.task_progress.emit(task_idx, quality, "uploading", pct)

        self.s3.upload_file(
            output_path, self.bucket, r2_key,
            Callback=upload_callback,
        )
        self.task_progress.emit(task_idx, quality, "uploading", 100)

        # Cleanup converted file
        try:
            os.remove(output_path)
        except OSError:
            pass

        # 4. Update video upload status via API
        video_id = task.video_ids.get(quality)
        print(f"[DEBUG] Lesson {task.lesson_id} quality={quality} video_id={video_id} video_ids={task.video_ids}")
        print(f"[DEBUG] api_base_url={self._api_base_url} auth_header={'set' if self._api_auth_header else 'empty'}")
        if video_id and self._api_base_url and self._api_auth_header:
            try:
                self._patch_video(video_id, int(duration))
                print(f"[DEBUG] PATCH success for video {video_id}")
            except Exception as e:
                print(f"[DEBUG] PATCH failed for video {video_id}: {e}")
                self.task_error.emit(task_idx, quality, f"Upload OK but API update failed: {e}")
        else:
            print(f"[DEBUG] Skipping PATCH: video_id={video_id}, base_url={bool(self._api_base_url)}, auth={bool(self._api_auth_header)}")

        self.task_progress.emit(task_idx, quality, "done", 100)

    def _build_ffmpeg_cmd(self, source: str, height: int, output: str, use_gpu: bool = True) -> list[str]:
        if use_gpu and _HW_ENCODER:
            hw = _HW_ENCODER
            return [
                FFMPEG, "-y", "-hwaccel", hw["hwaccel"],
                "-i", source,
                "-vf", f"scale=-2:{height}",
                "-c:v", hw["codec"], *hw["extra"],
                "-c:a", "aac", "-b:a", "128k",
                output,
            ]
        return [
            FFMPEG, "-y",
            "-i", source,
            "-vf", f"scale=-2:{height}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output,
        ]

    def _run_ffmpeg(self, cmd: list[str], task_idx: int, quality: str, duration: float) -> tuple[int, str]:
        proc = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
            universal_newlines=True,
        )

        stderr_lines = []
        for line in proc.stderr:
            stderr_lines.append(line)
            if self._cancelled:
                proc.kill()
                return (-1, "Cancelled")
            match = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", line)
            if match and duration > 0:
                h, m, s, cs = match.groups()
                current = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
                pct = min(int(current / duration * 100), 99)
                self.task_progress.emit(task_idx, quality, "encoding", pct)

        proc.wait()
        error_detail = "".join(stderr_lines[-10:]).strip()
        return (proc.returncode, error_detail)

    def _patch_video(self, video_id: int, duration: int):
        url = f"{self._api_base_url}/v1/internal/videos/{video_id}"
        body = json.dumps({"is_uploaded": True, "duration": duration}).encode()
        req = Request(url, data=body, method="POST")
        req.add_header("Authorization", self._api_auth_header)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "VideoCourseManager/1.0")
        with urlopen(req) as resp:
            resp.read()

    def _get_duration(self, filepath: str) -> float:
        try:
            result = subprocess.run(
                [FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", filepath],
                capture_output=True, text=True,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0
