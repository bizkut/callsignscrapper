"""
JSON storage module for MCMC Amateur Radio Station assignments.
Supports incremental updates with checkpoint/resume.
"""
import json
from datetime import datetime
from pathlib import Path

# Use /app/data in Docker, otherwise local directory
DATA_DIR = Path("/app/data") if Path("/app/data").exists() else Path(__file__).parent
ASSIGNMENTS_FILE = DATA_DIR / "callsigns.json"
CHECKPOINT_FILE = DATA_DIR / "checkpoint.json"
HISTORY_FILE = DATA_DIR / "scrape_history.json"


def _load_json(filepath, default=None):
    """Load JSON file, return default if not exists."""
    if default is None:
        default = {}
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return default
    return default


def _save_json(filepath, data):
    """Save data to JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def init_database():
    """Initialize the data directory."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Data directory: {DATA_DIR}")


def clear_assignments():
    """Clear all existing assignments."""
    _save_json(ASSIGNMENTS_FILE, {"assignments": [], "metadata": {"created_at": datetime.now().isoformat()}})
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
    print("Cleared existing assignments and checkpoint")


def get_assignments_data():
    """Get the full assignments data structure."""
    return _load_json(ASSIGNMENTS_FILE, {
        "assignments": [],
        "metadata": {"created_at": datetime.now().isoformat()}
    })


def upsert_assignments_batch(assignments):
    """
    Insert or update multiple assignment records.
    Returns tuple of (added_count, updated_count).
    """
    data = get_assignments_data()
    existing = data.get("assignments", [])
    
    # Create a lookup by call_sign
    by_callsign = {a["call_sign"]: i for i, a in enumerate(existing)}
    
    added = 0
    updated = 0
    now = datetime.now().isoformat()
    
    for row_number, holder, call_sign, assign_no, expiry in assignments:
        record = {
            "row_number": row_number,
            "assignment_holder": holder,
            "call_sign": call_sign,
            "assign_no": assign_no,
            "expiry_date": expiry,
        }
        
        if call_sign in by_callsign:
            # Update existing
            idx = by_callsign[call_sign]
            existing[idx].update(record)
            existing[idx]["last_updated_at"] = now
            updated += 1
        else:
            # Add new
            record["first_seen_at"] = now
            record["last_updated_at"] = now
            existing.append(record)
            by_callsign[call_sign] = len(existing) - 1
            added += 1
    
    data["assignments"] = existing
    data["metadata"]["last_updated"] = now
    data["metadata"]["total_count"] = len(existing)
    
    _save_json(ASSIGNMENTS_FILE, data)
    
    return added, updated


def get_assignment_count():
    """Get the total number of assignments."""
    data = get_assignments_data()
    return len(data.get("assignments", []))


def get_all_assignments():
    """Get all assignments."""
    data = get_assignments_data()
    return data.get("assignments", [])


# Scrape session tracking

def start_scrape_session():
    """Start a new scrape session and return its ID."""
    history = _load_json(HISTORY_FILE, {"sessions": []})
    session_id = len(history["sessions"]) + 1
    history["sessions"].append({
        "id": session_id,
        "started_at": datetime.now().isoformat(),
        "status": "running"
    })
    _save_json(HISTORY_FILE, history)
    return session_id


def update_scrape_session(session_id, records_found, records_added, records_updated, last_page):
    """Update scrape session with current progress."""
    history = _load_json(HISTORY_FILE, {"sessions": []})
    for session in history["sessions"]:
        if session["id"] == session_id:
            session.update({
                "records_found": records_found,
                "records_added": records_added,
                "records_updated": records_updated,
                "last_page": last_page
            })
            break
    _save_json(HISTORY_FILE, history)


def complete_scrape_session(session_id, records_found, records_added, records_updated, last_page=0, status="completed"):
    """Mark a scrape session as complete."""
    history = _load_json(HISTORY_FILE, {"sessions": []})
    for session in history["sessions"]:
        if session["id"] == session_id:
            session.update({
                "completed_at": datetime.now().isoformat(),
                "records_found": records_found,
                "records_added": records_added,
                "records_updated": records_updated,
                "last_page": last_page,
                "status": status
            })
            break
    _save_json(HISTORY_FILE, history)


# Checkpoint functions

def save_checkpoint(session_id, last_page, records_scraped):
    """Save checkpoint for resume capability."""
    _save_json(CHECKPOINT_FILE, {
        "session_id": session_id,
        "last_page": last_page,
        "records_scraped": records_scraped,
        "updated_at": datetime.now().isoformat()
    })


def get_checkpoint():
    """Get the last checkpoint for resume. Returns (session_id, last_page, records_scraped) or None."""
    if not CHECKPOINT_FILE.exists():
        return None
    data = _load_json(CHECKPOINT_FILE, None)
    if data:
        return (data["session_id"], data["last_page"], data["records_scraped"])
    return None


def clear_checkpoint():
    """Clear the checkpoint after successful completion."""
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()


if __name__ == "__main__":
    init_database()
    print(f"Total assignments: {get_assignment_count()}")
    
    checkpoint = get_checkpoint()
    if checkpoint:
        print(f"Checkpoint: session={checkpoint[0]}, page={checkpoint[1]}, records={checkpoint[2]}")
