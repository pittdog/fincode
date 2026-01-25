import json
import dataclasses
from datetime import datetime
from pathlib import Path
from typing import Any

def save_test_result(name: str, data: Any):
    """Save test result to JSON with timestamp."""
    results_dir = Path(__file__).parent.parent / "test-results"
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.json"
    filepath = results_dir / filename
    
    def serialize(obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if hasattr(obj, "__dict__"):
            return {k: serialize(v) for k, v in obj.__dict__.items()}
        if isinstance(obj, list):
            return [serialize(x) for x in obj]
        if isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        return obj

    with open(filepath, "w") as f:
        json.dump(serialize(data), f, indent=2, default=str)
    print(f"\nSaved live data to: {filename}")
