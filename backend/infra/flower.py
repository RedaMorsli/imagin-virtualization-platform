from infra.k8s import apply_manifest

# Deploys a federated learning setup using Flower framework on Kubernetes.
def provision_flower_on_cluster(context: str, config: dict):
    if not context:
        raise ValueError("context is required")

    if not isinstance(config, dict):
        raise ValueError("config must be a dictionary")
    
    # Config parameters with defaults (aligning to Flower Docker quickstart)
    clients = int(config.get("clients", 2))
    if clients < 1:
        raise ValueError("clients must be at least 1")

    namespace = "flower"

    superlink_image = config.get("superlink_image", "flwr/superlink:1.25.0")
    supernode_image = config.get("supernode_image", "flwr/supernode:1.25.0")
    superexec_image = config.get("superexec_image", "flwr/superexec:1.25.0")

    superlink_resources = config.get("superlink_resources", {"cpu": "500m", "memory": "512Mi"})
    supernode_resources = config.get("supernode_resources", {"cpu": "500m", "memory": "512Mi"})
    superexec_resources = config.get("superexec_resources", {"cpu": "500m", "memory": "512Mi"})
    client_resources = config.get("client_resources", {"cpu": "500m", "memory": "512Mi"})

    # Ports follow the Flower Docker tutorial
    port_superlink_serverappio = int(config.get("superlink_serverappio_port", 9091))
    port_superlink_fleet = int(config.get("superlink_fleet_port", 9092))
    port_superlink_control = int(config.get("superlink_control_port", 9093))
    port_supernode_clientappio = int(config.get("supernode_clientappio_port", 9094))

    # Flower components modeled as K8s Deployments + Services
    manifest = {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": namespace},
            },
            # SuperLink (control plane)
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "flower-superlink",
                    "namespace": namespace,
                    "labels": {"app": "flower-superlink"},
                },
                "spec": {
                    "replicas": 1,
                    "selector": {"matchLabels": {"app": "flower-superlink"}},
                    "template": {
                        "metadata": {"labels": {"app": "flower-superlink"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "superlink",
                                    "image": superlink_image,
                                    "args": ["--insecure", "--isolation", "process"],
                                    "ports": [
                                        {"name": "serverappio", "containerPort": port_superlink_serverappio},
                                        {"name": "fleet", "containerPort": port_superlink_fleet},
                                        {"name": "control", "containerPort": port_superlink_control},
                                    ],
                                    "resources": {"requests": superlink_resources, "limits": superlink_resources},
                                }
                            ]
                        },
                    },
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": "flower-superlink",
                    "namespace": namespace,
                    "labels": {"app": "flower-superlink"},
                },
                "spec": {
                    "selector": {"app": "flower-superlink"},
                    "ports": [
                        {"name": "serverappio", "protocol": "TCP", "port": port_superlink_serverappio},
                        {"name": "fleet", "protocol": "TCP", "port": port_superlink_fleet},
                        {"name": "control", "protocol": "TCP", "port": port_superlink_control},
                    ],
                },
            },
            # SuperNode (data plane)
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "flower-supernode",
                    "namespace": namespace,
                    "labels": {"app": "flower-supernode"},
                },
                "spec": {
                    "replicas": 1,  # single partition for now
                    "selector": {"matchLabels": {"app": "flower-supernode"}},
                    "template": {
                        "metadata": {"labels": {"app": "flower-supernode"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "supernode",
                                    "image": supernode_image,
                                    "args": [
                                        "--insecure",
                                        "--superlink",
                                        f"flower-superlink:{port_superlink_fleet}",
                                        "--node-config",
                                        "partition-id=0 num-partitions=1",
                                        "--clientappio-api-address",
                                        f"0.0.0.0:{port_supernode_clientappio}",
                                        "--isolation",
                                        "process",
                                    ],
                                    "ports": [
                                        {"name": "clientappio", "containerPort": port_supernode_clientappio},
                                    ],
                                    "resources": {"requests": supernode_resources, "limits": supernode_resources},
                                }
                            ]
                        },
                    },
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": "flower-supernode",
                    "namespace": namespace,
                    "labels": {"app": "flower-supernode"},
                },
                "spec": {
                    "selector": {"app": "flower-supernode"},
                    "ports": [
                        {
                            "name": "clientappio",
                            "protocol": "TCP",
                            "port": port_supernode_clientappio,
                            "targetPort": port_supernode_clientappio,
                        }
                    ],
                },
            },
            # SuperExec for ServerApps
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "flower-superexec-server",
                    "namespace": namespace,
                    "labels": {"app": "flower-superexec-server"},
                },
                "spec": {
                    "replicas": 1,
                    "selector": {"matchLabels": {"app": "flower-superexec-server"}},
                    "template": {
                        "metadata": {"labels": {"app": "flower-superexec-server"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "superexec-serverapp",
                                    "image": superexec_image,
                                    "args": [
                                        "--insecure",
                                        "--plugin-type",
                                        "serverapp",
                                        "--appio-api-address",
                                        f"flower-superlink:{port_superlink_serverappio}",
                                    ],
                                    "resources": {"requests": superexec_resources, "limits": superexec_resources},
                                }
                            ]
                        },
                    },
                },
            },
            # SuperExec for ClientApps (scaled by clients)
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "flower-superexec-client",
                    "namespace": namespace,
                    "labels": {"app": "flower-superexec-client"},
                },
                "spec": {
                    "replicas": clients,
                    "selector": {"matchLabels": {"app": "flower-superexec-client"}},
                    "template": {
                        "metadata": {"labels": {"app": "flower-superexec-client"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "superexec-clientapp",
                                    "image": superexec_image,
                                    "args": [
                                        "--insecure",
                                        "--plugin-type",
                                        "clientapp",
                                        "--appio-api-address",
                                        f"flower-supernode:{port_supernode_clientappio}",
                                    ],
                                    "resources": {"requests": client_resources, "limits": client_resources},
                                }
                            ]
                        },
                    },
                },
            },
        ],
    }

    # Apply the manifest to the specified Kubernetes context
    apply_manifest(context, manifest)
