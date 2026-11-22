"""Score gates for the video lane and the outside-search lane."""

# A video passage covers the question only when its lane score reaches this value.
VIDEO_COVERAGE_THRESHOLD = 0.34

# An outside source stays in the external lane only when its lane score reaches this value.
EXTERNAL_KEEP_THRESHOLD = 0.34

# Video passages sent to the model after the video lane is reranked.
VIDEO_PASSAGE_LIMIT = 4

# Outside sources sent to the model after the external lane is reranked.
EXTERNAL_SOURCE_LIMIT = 3
