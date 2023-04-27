from kubernetes import client, config, watch


def init_event_listener():
    config.incluster_config.load_incluster_config()

    api = client.CoreV1Api()
    w = watch.Watch()

    label_selector = "type=app"
    namespace = "default"

    for event in w.stream(api.list_namespaced_pod, namespace=namespace, label_selector=label_selector):
        pod = event["object"]
        status = pod.status.phase
        release = pod.metadata.labels["release"]
        print(f"EVENT_TYPE: {event['type']}", flush=True)
        print(f"STATUS: {status}", flush=True)
        send_status_to_rest_api(release, status)

def send_status_to_rest_api(release, status):
    """
    TODO: Send the updated status phase to studio REST-API endpoint
    """
    print(f"UPDATE: {release} to {status}", flush=True)

if __name__ == '__main__':
    init_event_listener()