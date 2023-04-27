from kubernetes import client, config, watch

config.incluster_config.load_incluster_config()

api = client.CoreV1Api()
w = watch.Watch()

label_selector = "type=app"
namespace = "default"

for event in w.stream(
    api.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
):
    pod = event["object"]
    print(f"METADATA: {pod.metadata}", flush=True)
    print(f"EVENT_TYPE: {event['type']}", flush=True)
