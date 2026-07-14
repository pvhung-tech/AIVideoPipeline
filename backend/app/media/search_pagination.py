from app.media.models import MediaSearchItem, MediaSearchQuery, MediaType


def calculateResultCounts(query: MediaSearchQuery) -> dict[MediaType, int]:
    counts = {mediaType: 0 for mediaType in query.mediaTypes}
    start = query.offset % len(query.mediaTypes)
    for index in range(query.limit):
        counts[query.mediaTypes[(start + index) % len(query.mediaTypes)]] += 1
    return counts


def calculateTypeOffsets(query: MediaSearchQuery) -> dict[MediaType, int]:
    cycle = query.offset // len(query.mediaTypes)
    start = query.offset % len(query.mediaTypes)
    return {
        mediaType: cycle + (1 if index < start else 0)
        for index, mediaType in enumerate(query.mediaTypes)
    }


def mergeTypeItems[Item: MediaSearchItem](
    query: MediaSearchQuery,
    items: dict[MediaType, list[Item]],
) -> tuple[Item, ...]:
    positions = {mediaType: 0 for mediaType in query.mediaTypes}
    merged: list[Item] = []
    start = query.offset % len(query.mediaTypes)
    while len(merged) < query.limit:
        added = False
        for step in range(len(query.mediaTypes)):
            mediaType = query.mediaTypes[(start + step) % len(query.mediaTypes)]
            position = positions[mediaType]
            if position < len(items[mediaType]):
                merged.append(items[mediaType][position])
                positions[mediaType] += 1
                added = True
                if len(merged) == query.limit:
                    break
        start = 0
        if not added:
            break
    return tuple(merged)
