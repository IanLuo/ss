from configure.configure import Configure
from .interface.file_exporter import FileExporter
from .interface.content_generator import ContentGenerator

_TEMPLATE_FILE = 'templates/sdk.nix.template'

class SdkGenerator(ContentGenerator, FileExporter):
    def __init__(self, configure: Configure):
        self.configure = configure

    def generate(self) -> str:
        # TODO:
        return '' 

