import inspect
from netqasm.logging import get_netqasm_logger

logger = get_netqasm_logger()


class LineTracker:
    # level: int, How many levels 'up' (in the call hierarchy) the host app is
    def __init__(self, level, track_lines=True):
        self._track_lines = track_lines
        if not self._track_lines:
            return
        # Get the file-name of the calling host application
        # TODO better way to do this?
        frame = inspect.currentframe()
        for _ in range(level):
            frame = frame.f_back
            if frame is None:
                break
        self._calling_filename = self._get_file_from_frame(frame)

    def _get_file_from_frame(self, frame):
        if frame is not None:
            return str(frame).split(',')[1][7:-1]
        else:
            return None

    def get_line(self):
        if not self._track_lines:
            return None
        if self._calling_filename is None:
            logger.warning("Did not find the correct calling filename")
            return None
        frame = inspect.currentframe()
        while True:
            if self._get_file_from_frame(frame) == self._calling_filename:
                break
            frame = frame.f_back
        else:
            raise RuntimeError(f"Different calling file than {self._calling_filename}")
        return frame.f_lineno
