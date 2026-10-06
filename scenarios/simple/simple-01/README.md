# simple-01

`webapp` can read only the dummy `deployer-credential` reference. Ground Truth
models that reference as an opaque credential artifact for `deployer`, which can
read only `production-db-secret`. The benchmark never extracts or uses a real
ServiceAccount token.

The alternate branch grants `webapp` pod creation and `pods/exec`; the
`resource_control` artifact connects C to F. ConfigMap read (E) succeeds without
contributing to the goal. No `nodes/proxy` role exists, so D is denied and is an
unresolved candidate. The `hound_rbac.json`, entry-point and asset files are
CAPRA inputs; `ground_truth.yaml` is never passed to CAPRA or RedAgent.
