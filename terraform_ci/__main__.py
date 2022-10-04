import os

from .terraform import TfCLI
from .pipeline import ActionPipeline
from .config import Settings

if __name__ == "__main__":
    settings = Settings().config

    os.chdir(settings.working_directory)

    TfCLI.set_version(version=settings.terraform.version)
    TfCLI.set_token(host=settings.terraform.host, token=settings.terraform.token)

    if settings.mode == "plan":
        (
            ActionPipeline(settings)
            .format()
            .init()
            .imports()
            .plan()
            .scan()
            .report()
        )
    else:
        (
            ActionPipeline(settings)
            .init()
            .plan()
            .apply()
            .report()
        )
