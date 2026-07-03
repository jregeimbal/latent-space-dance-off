from rich.progress import SpinnerColumn


class CustomSpinnerColumn(SpinnerColumn):
    def __init__(self, style="green", speed=1.0, finished_text=None, table_column=None):
        super().__init__(
            spinner_name="dots",
            style=style,
            speed=speed,
            finished_text=finished_text,
            table_column=table_column,
        )
        self.spinner.frames = ["◤", "▀", "◥", "▐", "◢", "▂", "◣", "▌"]
        self.spinner.interval = 120
