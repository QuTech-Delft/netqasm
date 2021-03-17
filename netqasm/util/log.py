import inspect
import os
from typing import Optional


class HostLine:
    def __init__(self, filename, lineno):
        self.filename = filename
        self.lineno = lineno

    def __str__(self):
        return str(self.lineno)


class LineTracker:
    def __init__(self, log_config):
        """
        Parameters
        ----------
        log_config : :class:`~.sdk.config.LogConfig`
        """
        self._track_lines = log_config.track_lines
        if not self._track_lines:
            return
        if log_config.app_dir is None:
            raise RuntimeError("Cannot create Linetracker because app_dir is None")

        self.app_dir = os.path.abspath(log_config.app_dir)

        lib_dirs = log_config.lib_dirs
        if lib_dirs is None:
            lib_dirs = []
        self.lib_dirs = [os.path.abspath(dir) for dir in lib_dirs]

    def _get_file_from_frame(self, frame):
        return os.path.abspath(frame.f_code.co_filename)

    def get_line(self) -> Optional[HostLine]:
        if not self._track_lines:
            return None

        frame = inspect.currentframe()
        assert frame is not None

        frame_found = False
        while not frame_found:
            frame_file = self._get_file_from_frame(frame)

            # first check if it's coming from one of the lib directories
            for lib_dir in self.lib_dirs:
                if frame_file.startswith(lib_dir):
                    frame_found = True
                    break

            # check in app directory itself
            if frame_file.startswith(self.app_dir):
                frame_found = True

            if frame_found:
                break

            frame = frame.f_back
            if frame is None:
                raise RuntimeError(f"No frame found in directory {self.app_dir}")

        filename = os.path.abspath(frame.f_code.co_filename)
        return HostLine(filename, frame.f_lineno)
