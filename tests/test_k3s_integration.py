from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_manifests_contain_only_dummy_secrets_and_denied_nodes_proxy():
    secret_docs = list(yaml.safe_load_all((ROOT / "scenarios/simple/simple-01/manifests/secrets.yaml").read_text()))
    assert all("dummy-only" in next(iter(item["stringData"].values())) for item in secret_docs)
    roles = (ROOT / "scenarios/simple/simple-01/manifests/roles.yaml").read_text()
    assert "nodes/proxy" not in roles
    assert 'resources: ["pods/exec"]' in roles


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_K3S_INTEGRATION") != "1", reason="set RUN_K3S_INTEGRATION=1 after deploy")
def test_deployed_local_k3s_rbac_state():
    result = subprocess.run([str(ROOT / "environments/k3s/status.sh"), "simple-01"],
                            cwd=ROOT, text=True, capture_output=True, shell=False)
    assert result.returncode == 0, result.stderr
    assert '"operator": "D", "authorized": false' in result.stdout
    assert '"operator": "A", "authorized": true' in result.stdout
    assert '"operator": "B", "authorized": true' in result.stdout
    assert '"operator": "F", "authorized": true' in result.stdout
