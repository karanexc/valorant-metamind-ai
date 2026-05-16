import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.api.vlr_client import get_events

events = get_events()

print("Total events:", len(events))
print("\nSample events:\n")

for e in events[:5]:
    print(e)
