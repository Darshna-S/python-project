import unittest
from scoring import calculate_weighted_score, calculate_complete_score


class TestScoring(unittest.TestCase):
    def test_no_suspicious_events(self):
        events = []
        result = calculate_weighted_score(events)
        self.assertEqual(result["penalty"], 0)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["risk_label"], "Low Risk")
        self.assertEqual(result["suspicious_event_count"], 0)

    def test_one_face_not_detected(self):
        events = [{"event_type": "Face Not Detected"}]
        result = calculate_weighted_score(events)
        self.assertEqual(result["penalty"], 5)
        self.assertEqual(result["score"], 95)
        self.assertEqual(result["risk_label"], "Low Risk")
        self.assertEqual(result["suspicious_event_count"], 1)

    def test_one_browser_focus_lost(self):
        events = [{"event_type": "Browser Focus Lost"}]
        result = calculate_weighted_score(events)
        self.assertEqual(result["penalty"], 10)
        self.assertEqual(result["score"], 90)
        self.assertEqual(result["risk_label"], "Low Risk")
        self.assertEqual(result["suspicious_event_count"], 1)

    def test_multiple_suspicious_events(self):
        events = [
            {"event_type": "Face Not Detected"},
            {"event_type": "Face Not Detected"},
            {"event_type": "Browser Focus Lost"},
            {"event_type": "Browser Tab Switch"},
            {"event_type": "Multiple Faces Detected"},
        ]
        result = calculate_weighted_score(events)
        self.assertEqual(result["penalty"], 45)
        self.assertEqual(result["score"], 55)
        self.assertEqual(result["risk_label"], "Medium Risk")
        self.assertEqual(result["suspicious_event_count"], 5)

    def test_score_never_negative(self):
        events = [{"event_type": "Multiple Faces Detected"}] * 20
        result = calculate_weighted_score(events)
        self.assertGreaterEqual(result["score"], 0)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["risk_label"], "High Risk")

    def test_face_presence_ratio(self):
        events = []
        result = calculate_complete_score(events, 540, 600)
        self.assertEqual(result["face_presence_ratio"], 90.0)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["risk_label"], "Low Risk")


if __name__ == '__main__':
    unittest.main()
