import json
from urllib.request import Request, urlopen
from urllib.parse import quote
import base64

from PyQt6.QtCore import QObject, pyqtSignal, QThread


class _FetchThread(QThread):
    result = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, url: str, auth_header: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.auth_header = auth_header

    def run(self):
        try:
            req = Request(self.url)
            req.add_header("Authorization", self.auth_header)
            req.add_header("User-Agent", "VideoCourseManager/1.0")
            req.add_header("Accept", "application/json")
            with urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.result.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class ApiClient(QObject):
    instructors_loaded = pyqtSignal(list)
    courses_loaded = pyqtSignal(list)
    course_detail_loaded = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, base_url: str, username: str = "admin", password: str = "password", parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._auth_header = f"Basic {credentials}"
        self._threads = []

    def _get(self, path: str, callback):
        url = f"{self.base_url}{path}"
        thread = _FetchThread(url, self._auth_header, self)
        thread.result.connect(callback)
        thread.error.connect(self.error.emit)
        thread.finished.connect(lambda: self._threads.remove(thread))
        self._threads.append(thread)
        thread.start()

    def fetch_instructors(self, search: str = ""):
        path = "/v1/internal/instructors"
        if search:
            path += f"?search={quote(search)}"
        self._get(path, lambda data: self.instructors_loaded.emit(data.get("data", [])))

    def fetch_courses(self, instructor_id: int):
        path = f"/v1/internal/instructors/{instructor_id}/courses"
        self._get(path, lambda data: self.courses_loaded.emit(data.get("data", [])))

    def fetch_course_detail(self, course_id: int):
        path = f"/v1/internal/courses/{course_id}"
        self._get(path, lambda data: self.course_detail_loaded.emit(data.get("data", {})))
