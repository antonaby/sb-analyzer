from enum import Enum


class VideoSource(Enum):
  tiktok = "tiktok"
  youtube_shorts = "youtube_shorts"
  instagram_reels = "instagram_reels"
  other = "other"


class MetaSource(Enum):
  title = "title"
  description = "description"
  hashtag = "hashtag"
  frame_content_type = "frame_content_type"
  frame_style = "frame_style"
  frame_quality = "frame_quality"
  topic = "topic"


class AnnotationKind(Enum):
  frame = "frame"
  frame_object = "frame_object"
  frame_action = "frame_action"
  frame_environment = "frame_environment"
  frame_summary = "frame_summary"
  frame_logo = "frame_logo"
  label = "label"
  synopsis = "synopsis"
  action = "action"
  transcription = "transcription"


class VideoProcessingKind(Enum):
  summarizing = "summarizing"
  categorization = "categorization"
