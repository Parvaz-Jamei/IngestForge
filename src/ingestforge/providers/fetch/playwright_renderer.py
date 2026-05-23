class PlaywrightRenderer:
    def render(self, url: str) -> str:
        raise RuntimeError(
            "Playwright renderer is optional; install ingestforge[playwright] and enable explicitly"
        )
