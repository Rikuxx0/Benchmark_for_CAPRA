"""Dedicated Docker-hosted k3s lifecycle. Never uses the caller's kubeconfig."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWNER = hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
OWNER_LABEL = "benchmark.for-capra.owner"
IMAGE = "rancher/k3s:v1.32.5-k3s1"
PAUSE_IMAGE = "capra-benchmark/pause:3.6"
WORKLOAD_IMAGE = "alpine:3.21.3"
LOCAL_IMAGES = (PAUSE_IMAGE, WORKLOAD_IMAGE)
NETWORK_SUBNET = f"10.250.{int(OWNER[:2], 16)}.0/24"


def command(argv, *, check=True, capture=True, timeout=180):
    result = subprocess.run(argv, check=False, text=True, capture_output=capture,
                            timeout=timeout, shell=False)
    if check and result.returncode:
        # Docker/kubectl errors are not echoed: they may include configuration.
        raise RuntimeError(f"{argv[0]} {argv[1]} failed (exit {result.returncode})")
    return result


class Lab:
    def __init__(self, scenario_id):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,40}", scenario_id):
            raise ValueError("invalid scenario_id")
        matches = list((ROOT / "scenarios").glob(f"*/{scenario_id}/scenario.yaml"))
        if len(matches) != 1:
            raise ValueError("scenario must resolve to exactly one repository fixture")
        self.scenario_dir = matches[0].parent
        self.scenario_id = scenario_id
        self.name = f"capra-bench-{OWNER}-{scenario_id}"
        self.network = self.name + "-net"
        self._validated_container = None

    def inspect(self, kind, name):
        listed = command(["docker", kind, "ls", "--format", "{{.Name}}" if kind == "network"
                          else "{{.Names}}", *([] if kind == "network" else ["-a"])])
        if name not in listed.stdout.splitlines():
            return None
        obj = json.loads(command(["docker", kind, "inspect", name]).stdout)[0]
        labels = obj.get("Labels", {}) if kind == "network" else obj["Config"].get("Labels", {})
        if labels.get(OWNER_LABEL) != OWNER or labels.get("benchmark.scenario") != self.scenario_id:
            raise RuntimeError(f"refusing to touch unowned {kind}: {name}")
        return obj

    def container(self):
        if self._validated_container is not None:
            return self._validated_container
        obj = self.inspect("container", self.name)
        if obj is None or not obj["State"]["Running"]:
            raise RuntimeError("dedicated k3s is not running; run setup")
        if obj["Config"]["Image"] != IMAGE:
            raise RuntimeError("unexpected k3s image")
        networks = obj["NetworkSettings"]["Networks"]
        net = self.inspect("network", self.network)
        if set(networks) != {self.network} or net is None or not net.get("Internal"):
            raise RuntimeError("dedicated internal network is required")
        for bindings in obj["HostConfig"].get("PortBindings", {}).values():
            if any(b["HostIp"] != "127.0.0.1" for b in bindings or []):
                raise RuntimeError("API binding must be loopback only")
        self._validated_container = obj
        return obj

    def kubectl(self, args, *, check=True):
        self.container()
        return command(["docker", "exec", self.name, "kubectl", "--request-timeout=30s", *args],
                       check=check)

    def setup(self):
        command(["docker", "info"])
        net = self.inspect("network", self.network)
        if net is not None and net.get("IPAM", {}).get("Config", [{}])[0].get("Subnet") != NETWORK_SUBNET:
            if self.inspect("container", self.name) is not None:
                command(["docker", "container", "rm", "-f", self.name])
            command(["docker", "network", "rm", self.network])
            net = None
        if net is None:
            command(["docker", "network", "create", "--internal", "--subnet", NETWORK_SUBNET,
                     "--label", f"{OWNER_LABEL}={OWNER}",
                     "--label", f"benchmark.scenario={self.scenario_id}", self.network])
            net = self.inspect("network", self.network)
        elif not net.get("Internal"):
            raise RuntimeError("existing network is not internal")
        subnet = net.get("IPAM", {}).get("Config", [{}])[0].get("Subnet")
        if not subnet:
            raise RuntimeError("dedicated network has no IPv4 subnet")
        node_ip = str(ipaddress.ip_network(subnet, strict=False)[2])
        obj = self.inspect("container", self.name)
        expected_node_arg = f"--node-ip={node_ip}"
        expected_pause_arg = f"--pause-image={PAUSE_IMAGE}"
        if obj is not None and not {expected_node_arg, expected_pause_arg}.issubset(set(obj["Config"].get("Cmd", []))):
            # Safe migration of this repository-owned, scenario-scoped container.
            command(["docker", "container", "rm", "-f", self.name])
            self._validated_container = None
            obj = None
        if obj is None:
            command(["docker", "run", "-d", "--name", self.name, "--privileged",
                     "--network", self.network, "--ip", node_ip,
                     "--label", f"{OWNER_LABEL}={OWNER}",
                     "--label", f"benchmark.scenario={self.scenario_id}",
                     IMAGE, "server",
                     expected_node_arg, f"--advertise-address={node_ip}", "--flannel-iface=eth0",
                     expected_pause_arg,
                     "--disable", "traefik,servicelb,metrics-server,local-storage,coredns"])
        elif not obj["State"]["Running"]:
            command(["docker", "start", self.name])
            self._validated_container = None
        for _ in range(60):
            ready = self.kubectl(["get", "--raw=/readyz"], check=False)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("k3s API did not become ready within 60 seconds")
        for _ in range(60):
            ready_node = self.kubectl(["wait", "--for=condition=Ready", "nodes", "--all", "--timeout=2s"],
                                      check=False)
            if ready_node.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("k3s node did not become ready within 60 seconds")
        # Import pinned local images, including the Pod sandbox. The cluster's
        # internal network therefore never needs registry or DNS egress.
        command(["docker", "build", "--network", "none", "--pull=false", "--tag", PAUSE_IMAGE,
                 str(ROOT / "environments/k3s/pause")])
        for image in LOCAL_IMAGES:
            if image == WORKLOAD_IMAGE and command(["docker", "image", "inspect", image], check=False).returncode:
                command(["docker", "pull", image])
            producer = subprocess.Popen(["docker", "image", "save", image], stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL)
            try:
                consumer = subprocess.run(["docker", "exec", "-i", self.name, "ctr", "--namespace", "k8s.io",
                                           "images", "import", "-"], stdin=producer.stdout,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                          timeout=120, shell=False)
                producer.stdout.close()
                code = producer.wait(timeout=30)
                if consumer.returncode or code:
                    raise RuntimeError(f"local image import failed: {image}")
            finally:
                if producer.poll() is None:
                    producer.kill()
                    producer.wait()
        self.report("setup")

    def report(self, action):
        obj = self.container()
        print(json.dumps({"action": action, "scenario_id": self.scenario_id,
                          "container": self.name, "k3s_image": IMAGE,
                          "image_id": obj["Image"], "network_internal": True,
                          "api_access": "docker-exec-only"}, sort_keys=True))

    def deploy(self):
        self.container()
        # Validate scenario and Ground Truth before changing the environment.
        from evaluator.validation import load_scenario
        load_scenario(self.scenario_dir)
        for name in ("application", "production"):
            existing = self.kubectl(["get", "namespace", name, "--ignore-not-found", "-o", "json"])
            if existing.stdout.strip():
                labels = json.loads(existing.stdout)["metadata"].get("labels", {})
                if labels.get("benchmark.scenario") != self.scenario_id:
                    raise RuntimeError(f"refusing to overwrite unowned namespace {name}")
        manifests = self.scenario_dir / "manifests"
        for path in sorted(manifests.glob("*.yaml"), key=lambda p: (p.name != "namespaces.yaml", p.name)):
            remote = f"/tmp/benchmark-{path.name}"
            command(["docker", "cp", str(path), f"{self.name}:{remote}"])
            self.kubectl(["apply", "-f", remote])
        self.kubectl(["wait", "-n", "application", "--for=condition=Ready", "pod/webapp", "--timeout=90s"])
        self.status()

    def status(self):
        self.report("status")
        for ns, kind, name in [("application", "serviceaccount", "webapp"),
                               ("application", "serviceaccount", "deployer"),
                               ("application", "secret", "deployer-credential"),
                               ("production", "secret", "production-db-secret"),
                               ("application", "configmap", "public-config"),
                               ("application", "pod", "webapp")]:
            self.kubectl(["get", kind, name, "-n", ns, "-o", "name"])
        permissions = [
            ("A", "webapp", "application", "get", "secrets/deployer-credential", True),
            ("B", "deployer", "production", "get", "secrets/production-db-secret", True),
            ("C", "webapp", "application", "create", "pods", True),
            ("D", "webapp", "application", "get", "nodes/proxy", False),
            ("E", "webapp", "application", "get", "configmaps/public-config", True),
            ("F", "webapp", "application", "create", "pods/exec", True),
            ("direct-goal-denied", "webapp", "production", "get", "secrets/production-db-secret", False),
        ]
        for label, sa, ns, verb, resource, expected in permissions:
            result = self.kubectl(["auth", "can-i", verb, resource, "-n", ns,
                                   "--as", f"system:serviceaccount:application:{sa}"], check=False)
            answer = result.stdout.strip()
            if answer not in ("yes", "no") or result.returncode not in (0, 1):
                raise RuntimeError(f"authorization check {label} did not return a decision")
            if (answer == "yes") != expected:
                raise RuntimeError(f"authorization check {label} disagrees with Ground Truth")
            print(json.dumps({"operator": label, "authorized": answer == "yes"}))

    def reset(self):
        self.container()
        for ns in ("application", "production"):
            existing = self.kubectl(["get", "namespace", ns, "--ignore-not-found", "-o", "json"])
            if existing.stdout.strip():
                if json.loads(existing.stdout)["metadata"].get("labels", {}).get("benchmark.scenario") != self.scenario_id:
                    raise RuntimeError(f"refusing to delete unowned namespace {ns}")
                self.kubectl(["delete", "namespace", ns, "--wait=true", "--timeout=90s"])
        self.deploy()

    def destroy(self):
        if self.inspect("container", self.name) is not None:
            command(["docker", "container", "rm", "-f", self.name])
            self._validated_container = None
        if self.inspect("network", self.network) is not None:
            command(["docker", "network", "rm", self.network])
        print(json.dumps({"action": "destroy", "scenario_id": self.scenario_id}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "deploy", "status", "reset", "destroy"])
    parser.add_argument("scenario_id", nargs="?", default="simple-01")
    args = parser.parse_args()
    try:
        getattr(Lab(args.scenario_id), args.action)()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"environment error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
