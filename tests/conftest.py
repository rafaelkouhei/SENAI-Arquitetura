import sys
from pathlib import Path

# As fitness functions moram em tools/ e são importadas pelos testes.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
