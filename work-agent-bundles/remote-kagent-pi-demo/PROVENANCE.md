# Source provenance

Pi UI and SDK source are a snapshot of durable-pi, upstream https://github.com/disler/durable-pi at baseline aa8bf021c112eac2d498e5757d4315559df8ab80 plus the current native integration changes. File checksums describe the actual bundled overlay, not a published upstream commit.

Runtime chat, task/approval translation, GitOps workflow and rollback service come from the verified local adapter. The portable rollback service removes the Jev monitor and parameterizes repository, image, cluster and namespace scope. Synthetic classification is implemented separately in classifier.py.

Protobuf definitions come from the sanitized pi-durable-comparison-fixture showcase shim. They implement kagent.api.v1alpha1 and lf.a2a.v1, tested against native kagent 1.0.0-alpha11. The shim uses proto3-compatible syntax. Do not assume these APIs exist on kagent 0.x. Runtime packages are locked to grpcio/grpcio-tools 1.78.0 and protobuf 6.33.5.

No runtime configuration, kubeconfig, token, Secret manifest, home-lab database, native context or captured customer data is copied into this bundle.
