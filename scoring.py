try:
    import pandas as pd
except Exception:
    pd = None


EVENT_WEIGHTS = {
    "Face Not Detected": 5,
    "Browser Focus Lost": 10,
    "Browser Tab Switch": 10,
    "Multiple Faces Detected": 15,
}


def calculate_risk_label(score):
    if score >= 75:
        return "Low Risk"
    elif score >= 50:
        return "Medium Risk"
    else:
        return "High Risk"


def calculate_face_presence_ratio(total_detected_seconds, total_session_seconds):
    try:
        detected = float(total_detected_seconds or 0)
        total = float(total_session_seconds or 0)
    except (TypeError, ValueError):
        return 0.0

    if total <= 0:
        return 0.0

    ratio = (detected / total) * 100
    ratio = max(0.0, min(100.0, ratio))
    return round(ratio, 2)


def calculate_weighted_score(events):
    """
    Calculate weighted integrity score using Pandas or plain Python.
    Safely handles sqlite3.Row, dicts, DataFrames, and objects.
    """
    if pd is not None:
        if isinstance(events, pd.DataFrame):
            df = events.copy()
        elif not events:
            df = pd.DataFrame(columns=["event_type"])
        else:
            records = []
            for event in events:
                if isinstance(event, dict):
                    records.append(event)
                elif hasattr(event, "keys"):
                    records.append({k: event[k] for k in event.keys()})
                elif hasattr(event, "__dict__"):
                    records.append(event.__dict__)
                else:
                    try:
                        records.append(dict(event))
                    except Exception:
                        records.append({})
            df = pd.DataFrame(records)

        if "event_type" not in df.columns:
            df["event_type"] = ""

        df["weight"] = (
            df["event_type"]
            .fillna("")
            .astype(str)
            .str.strip()
            .map(EVENT_WEIGHTS)
            .fillna(0)
        )

        suspicious_df = df[df["weight"] > 0].copy()
        total_penalty = int(suspicious_df["weight"].sum())
        suspicious_event_count = len(suspicious_df)
    else:
        event_types = []
        if events:
            for event in events:
                if isinstance(event, dict):
                    e_type = event.get("event_type", "")
                elif hasattr(event, "keys"):
                    e_type = event["event_type"] if "event_type" in event.keys() else ""
                else:
                    e_type = getattr(event, "event_type", "")
                event_types.append(str(e_type).strip())

        weights = [EVENT_WEIGHTS.get(e, 0) for e in event_types]
        total_penalty = int(sum(weights))
        suspicious_event_count = sum(1 for w in weights if w > 0)

    # Initial score starting at 100
    score = 100 - total_penalty

    # Strictly normalize score within [0, 100] (never goes below 0)
    score = max(0, min(100, score))
    risk_label = calculate_risk_label(score)

    return {
        "score": int(score),
        "penalty": total_penalty,
        "total_penalty": total_penalty,
        "suspicious_event_count": suspicious_event_count,
        "risk_label": risk_label,
        "risk_level": risk_label,
    }


def calculate_complete_score(events, total_detected_seconds, total_session_seconds):
    result = calculate_weighted_score(events)
    face_presence_ratio = calculate_face_presence_ratio(
        total_detected_seconds,
        total_session_seconds
    )
    result["face_presence_ratio"] = face_presence_ratio
    return result