import re

class Converter:
    def get_dict(self, source_metadata):
        return source_metadata
class Mapper:
    def get_metadata(self, key, source_metadata):
        if key.lower() == "dc-title":
            matches = re.findall(
                r"<dc:title[^>]*>(.*)</dc:title>",
                source_metadata
            )
            return matches
        return None
class BuildConfig:
    CONVERTER = Converter
    MAPPER = Mapper
