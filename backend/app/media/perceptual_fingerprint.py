IMAGE_HASH_PREFIX = "dhash64-v1:"
VIDEO_HASH_PREFIX = "dhash64-sequence-v1:"
IMAGE_HAMMING_THRESHOLD = 8
VIDEO_AVERAGE_HAMMING_THRESHOLD = 8


def imageHammingDistance(first: str, second: str) -> int | None:
    if not first.startswith(IMAGE_HASH_PREFIX) or not second.startswith(
        IMAGE_HASH_PREFIX
    ):
        return None
    return _hamming(
        first.removeprefix(IMAGE_HASH_PREFIX),
        second.removeprefix(IMAGE_HASH_PREFIX),
    )


def videoAverageHammingDistance(first: str, second: str) -> float | None:
    if not first.startswith(VIDEO_HASH_PREFIX) or not second.startswith(
        VIDEO_HASH_PREFIX
    ):
        return None
    firstFrames = first.removeprefix(VIDEO_HASH_PREFIX).split(",")
    secondFrames = second.removeprefix(VIDEO_HASH_PREFIX).split(",")
    if len(firstFrames) != len(secondFrames):
        return None
    total = sum(
        _hamming(left, right)
        for left, right in zip(firstFrames, secondFrames, strict=True)
    )
    return total / len(firstFrames)


def _hamming(first: str, second: str) -> int:
    return (int(first, 16) ^ int(second, 16)).bit_count()
