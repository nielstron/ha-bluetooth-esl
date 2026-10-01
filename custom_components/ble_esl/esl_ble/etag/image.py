from ..._vendor.ble_labels.tags.etag213 import quantize


def encode_image(image, preset):
    """Quantize now; firmware read in the session selects column direction."""
    return quantize(image)
