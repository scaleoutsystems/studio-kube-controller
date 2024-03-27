from kubernetes import client, config, watch

import os
import requests

STUDIO_SERVICE_NAME = os.environ.get("STUDIO_SERVICE_NAME", None)
STUDIO_SERVICE_PORT = os.environ.get("STUDIO_SERVICE_PORT", None)
APP_STATUS_ENDPOINT = os.environ.get("APP_STATUS_ENDPOINT", None)
APP_STATUSES_ENDPOINT = os.environ.get("APP_STATUSES_ENDPOINT", None)

BASE_URL = f"http://{STUDIO_SERVICE_NAME}:{STUDIO_SERVICE_PORT}"
APP_STATUS_URL = f"{BASE_URL}/{APP_STATUS_ENDPOINT}"
APP_STATUSES_URL = f"{BASE_URL}/{APP_STATUSES_ENDPOINT}"

print(f"STUDIO_SERVICE_NAME: {STUDIO_SERVICE_NAME}", flush=True)
print(f"STUDIO_SERVICE_PORT: {STUDIO_SERVICE_PORT}", flush=True)
print(f"APP_STATUS_ENDPOINT: {APP_STATUS_ENDPOINT}", flush=True)
print(f"APP_STATUSES_ENDPOINT: {APP_STATUSES_ENDPOINT}", flush=True)

K8S_STATUS_MAP = {
    "CrashLoopBackOff": "Error",
    "Completed": "Retrying...",
    "ContainerCreating": "Created",
    "PodInitializing": "Pending",
}

config.incluster_config.load_incluster_config()

api = client.CoreV1Api()
w = watch.Watch()

label_selector = "type=app"
namespace = "default"

latest_status = {}


def sync_all_statuses():
    values = ""

    for pod in api.list_namespaced_pod(
        namespace=namespace, label_selector=label_selector
    ).items:
        status = pod.status.phase
        release = pod.metadata.labels["release"]

        values += f"{release}:{status},"

    data = {"values": values}

    print(f"DATA: {data}", flush=True)
    print("Syncing all statuses...", flush=True)

    post(APP_STATUSES_URL, data=data)


def init_event_listener():
    for event in w.stream(
        api.list_namespaced_pod,
        namespace=namespace,
        label_selector=label_selector,
    ):
        pod = event["object"]

        status = get_status(pod)

        print(f"Synchronizing status: {status}", flush=True)

        # status = pod.status.phase
        release = pod.metadata.labels["release"]

        event_type = event["type"]

        if latest_status.get(release) == status:
            print("Status not changed, skipping...")

        latest_status[release] = status

        if event_type != "DELETED":
            print(f"EVENT_TYPE: {event_type}", flush=True)
            print(f"STATUS: {status}", flush=True)

            data = {
                "release": release,
                "status": status,
            }

            post(APP_STATUS_URL, data=data)


def get_status(pod):
    """
    Returns the status of a pod by looping through each container
    and checking the status.
    """
    container_statuses = pod.status.container_statuses

    if container_statuses is not None:
        for container_status in container_statuses:
            state = container_status.state

            if state is not None:
                terminated = state.terminated

                if terminated is not None:
                    reason = terminated.reason
                    return mapped_status(reason)

                waiting = state.waiting

                if waiting is not None:
                    reason = waiting.reason
                    return mapped_status(reason)
        else:
            running = state.running
            ready = container_status.ready
            if running and ready:
                return "Running"
            else:
                return "Pending"

    return pod.status.phase


def mapped_status(reason: str) -> str:
    return K8S_STATUS_MAP.get(reason, reason)


def post(url: str, data: dict):
    try:
        response = requests.post(url, data=data, verify=False)

        print(f"RESPONSE STATUS CODE: {response.status_code}")
        print(f"RESPONSE TEXT: {response.text}")

    except requests.exceptions.RequestException:
        print("Service did not respond.")


if __name__ == "__main__":
    print("Starting event listener...", flush=True)

    sync_all_statuses()
    init_event_listener()
