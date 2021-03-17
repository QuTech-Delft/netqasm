import os
import sys


class ProgressBar:
    def __init__(self, maxitr: int):
        self.maxitr: int = maxitr
        self.itr: int = 0
        try:
            self.cols = os.get_terminal_size().columns
        except (OSError, AttributeError):
            self.cols = 60
        print("")
        self.update()

    def increase(self) -> None:
        self.itr += 1
        self.update()

    def update(self) -> None:
        cols = self.cols - 8
        assert self.itr <= self.maxitr
        ratio = float(self.itr) / self.maxitr
        procent = int(ratio * 100)
        progress = "=" * int(cols * ratio)
        sys.stdout.write("\r")
        sys.stdout.write("[%*s] %d%%" % (-cols, progress, procent))
        sys.stdout.flush()
        pass

    def close(self) -> None:
        print("")
