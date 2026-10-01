from ..._vendor.ble_labels.tags.minew154 import Minew154Driver


def encode_image(image, preset):
    return Minew154Driver().prepare_image(image)
