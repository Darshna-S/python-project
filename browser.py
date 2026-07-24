from datetime import datetime
from database import log_event


class BrowserMonitor:

    def __init__(self, candidate_id):

        self.candidate_id = candidate_id

        self.browser_active = True

        self.focus_loss_count = 0

        self.last_focus_loss_time = "None"

    def focus_lost(self):

        if self.browser_active:

            self.browser_active = False

            self.focus_loss_count += 1

            self.last_focus_loss_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            log_event(
                self.candidate_id,
                "Browser Focus Lost",
                self.last_focus_loss_time,
                "Candidate switched away from exam window"
            )

    def focus_regained(self):

        if not self.browser_active:

            self.browser_active = True

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            log_event(
                self.candidate_id,
                "Browser Focus Regained",
                now,
                "Candidate returned to exam window"
            )