import os
import re
import shutil
import subprocess

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

def get_encoder_label() -> str:
    if _HW_ENCODER:
        return _HW_ENCODER["label"]
    return "CPU (libx264)"


class ProcessingTask:
    def __init__(self, lesson_id: int, lesson_title: str, source_file: str,
                 course_storage_path: str, qualities: list[str]):
        self.lesson_id = lesson_id
        self.lesson_title = lesson_title
        self.source_file = source_file
        self.course_storage_path = course_storage_path.rstrip("/")
        self.qualities = qualities  # e.g. ["1080p", "720p"]


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

    def __init__(self, tasks: list[ProcessingTask], parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self._cancelled = False

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
        for task_idx, task in enumerate(self.tasks):
            if self._cancelled:
                break
            for quality in task.qualities:
                if self._cancelled:
                    break
                try:
                    self._process_one(task_idx, task, quality)
                except Exception as e:
                    self.task_error.emit(task_idx, quality, str(e))

        self.all_done.emit()

    def _process_one(self, task_idx: int, task: ProcessingTask, quality: str):
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

        # 2. Delete old from R2
        self.task_progress.emit(task_idx, quality, "deleting", 0)
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=r2_key)
        except Exception:
            pass  # OK if it doesn't exist
        self.task_progress.emit(task_idx, quality, "deleting", 100)

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
