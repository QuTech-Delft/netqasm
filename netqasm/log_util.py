import inspect
import os


class HostLine:
    def __init__(self, filename, lineno):
        self.filename = filename
        self.lineno = lineno

    def __str__(self):
        return str(self.lineno)


class LineTracker:
    def __init__(self, track_lines=True, app_dir=None, lib_dirs=[]):
        self._track_lines = track_lines
        if not self._track_lines:
            return
        if app_dir is None:
            raise RuntimeError("Cannot create Linetracker because app_dir is None")
        self.app_dir = app_dir
        self.lib_dirs = lib_dirs

    def _get_file_from_frame(self, frame):
        return frame.f_code.co_filename

    def get_line(self) -> HostLine:
        if not self._track_lines:
            return None

        frame = inspect.currentframe()
        frame_found = False
        while not frame_found:
            frame_file = self._get_file_from_frame(frame)

            # first check if it's coming from one of the lib directories
            for lib_dir in self.lib_dirs:
                if lib_dir in frame_file:
                    frame_found = True
                    break

            # check in app directory itself
            if self.app_dir in frame_file:
                frame_found = True

            if frame_found:
                break

            frame = frame.f_back
            if frame is None:
                raise RuntimeError(f"No frame found in directory {self.app_dir}")

        filename = os.path.abspath(frame.f_code.co_filename)
        return HostLine(filename, frame.f_lineno)
