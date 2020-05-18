import inspect


class LineTracker:
    # for_socket: True if tracking a (Thread)Socket, False otherwise
    def __init__(self, track_lines=True, for_socket=False):
        self._track_lines = track_lines
        if not self._track_lines:
            return
        # Get the file-name of the calling host application
        frame = inspect.currentframe()
        level = 2 if for_socket else 3
        for _ in range(level):
            frame = frame.f_back
        self._calling_filename = self._get_file_from_frame(frame)

    def _get_file_from_frame(self, frame):
        return str(frame).split(',')[1][7:-1]

    def get_line(self):
        if not self._track_lines:
            return None
        frame = inspect.currentframe()
        while True:
            if self._get_file_from_frame(frame) == self._calling_filename:
                break
            frame = frame.f_back
        else:
            raise RuntimeError(f"Different calling file than {self._calling_filename}")
        return frame.f_lineno
